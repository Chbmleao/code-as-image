"""Replies from a running vLLM server for every (item, condition, run) in a requests file.

Run r is sent with seed r. Sampling is sent explicitly on every request (configs/experiment.toml).
Requests run concurrently; a single writer appends one row per reply to the output, so the file
never has two writers. Resumable: keys already in the output are skipped.

A 400 that says the prompt is too long or has too many images is an exclusion (docs/methodology.md
3.1) and is written as a row with `error`. Any other 400 means the pipeline built a bad request and
stops the job. Connection failures and 5xx are retried, then stop the job without writing a row, so
a resubmit picks the key up again.

--probe also writes <out>.probe.jsonl: per item, the prompt tokens of the image-condition message
with its images removed, so image tokens can be separated from the text part (UFM-19 note).
--seed-check also writes <out>.seedcheck.jsonl: one item at seed 0 twice and seed 1 once.
"""
import argparse
import base64
import json
import os
import re
import socket
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from importlib import metadata

from codeimg import config

EXCLUSION = re.compile(r"maximum context length|maximum model length|longer than the maximum"
                       r"|max_model_len|At most \d+ image", re.IGNORECASE)
RETRIES = 3


class StopJob(RuntimeError):
    pass


def key(row):
    return (row["id"], row["condition"], row["run"])


def content(req, base_dir, images=True):
    out = []
    for p in req["parts"]:
        if p["type"] == "text":
            out.append({"type": "text", "text": p["text"]})
        elif images:
            with open(os.path.join(base_dir, p["path"]), "rb") as f:
                url = "data:image/png;base64," + base64.b64encode(f.read()).decode()
            out.append({"type": "image_url", "image_url": {"url": url}})
    return out


def post(url, body):
    """The parsed response, or ("excluded", message). Raises StopJob when retrying cannot help."""
    data = json.dumps(body).encode()
    for attempt in range(RETRIES + 1):
        req = urllib.request.Request(url, data, {"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=1800) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            msg = e.read().decode("utf-8", "replace")[:1000]
            if e.code == 400 and EXCLUSION.search(msg):
                return ("excluded", f"400 {msg}")
            if e.code < 500:
                raise StopJob(f"HTTP {e.code}: {msg}") from None
            err = f"HTTP {e.code}: {msg}"
        except (urllib.error.URLError, ConnectionError, socket.timeout, TimeoutError) as e:
            err = repr(e)
        if attempt < RETRIES:
            time.sleep(10 * 2 ** attempt)
    raise StopJob(f"gave up after {RETRIES} retries: {err}")


class Client:
    def __init__(self, url, repo, cfg, base_dir):
        self.url, self.repo, self.base_dir = url, repo, base_dir
        self.exp, self.sampling = cfg["experiment"], cfg["sampling"]

    def body(self, parts, seed, max_tokens):
        # no system message, as in calibration (benchmarks/shared/generate.py)
        return {"model": self.repo, "max_tokens": max_tokens, "seed": seed, **self.sampling,
                "messages": [{"role": "user", "content": parts}],
                "chat_template_kwargs": {"enable_thinking": False}}

    def reply(self, req, run):
        t0 = time.time()
        row = {"model": self.repo, "benchmark": req["benchmark"], "id": req["id"],
               "condition": req["condition"], "run": run, "seed": run, "n_images": req["n_images"]}
        r = post(self.url, self.body(content(req, self.base_dir), run, self.exp["max_tokens"]))
        if isinstance(r, tuple):
            row.update(reply=None, error=r[1])
        else:
            choice = r["choices"][0]
            # vLLM answers in-flight requests with "abort" when its engine dies; the partial
            # reply is not an output, and a written row would mark the key as done
            if choice["finish_reason"] == "abort":
                raise StopJob("vLLM aborted the request")
            row.update(reply=choice["message"]["content"] or "", finish_reason=choice["finish_reason"],
                       prompt_tokens=r["usage"]["prompt_tokens"],
                       output_tokens=r["usage"]["completion_tokens"], error=None)
        row["seconds"] = round(time.time() - t0, 2)
        return row

    def text_part_tokens(self, req):
        r = post(self.url, self.body(content(req, self.base_dir, images=False), 0, 1))
        return None if isinstance(r, tuple) else r["usage"]["prompt_tokens"]


def read_rows(path):
    if not os.path.exists(path):
        return []
    with open(path) as f:
        return [json.loads(line) for line in f]


def repair_tail(path):
    """Cut a last line left unfinished by a job killed mid-write, so the next job of a chain can
    read the file and its first append starts on a new line. The cut key is sent again."""
    if not os.path.exists(path):
        return
    with open(path, "rb+") as f:
        data = f.read()
        if not data or data.endswith(b"\n"):
            return
        start = data.rfind(b"\n") + 1
        try:
            json.loads(data[start:])
        except ValueError:
            print(f"warning: dropping an unfinished last line of {path}", file=sys.stderr)
            f.truncate(start)
        else:
            f.write(b"\n")


def append(f, row):
    f.write(json.dumps(row, ensure_ascii=False) + "\n")
    f.flush()


def run_grid(client, requests, runs, out_path, workers):
    repair_tail(out_path)
    done = {key(r) for r in read_rows(out_path)}
    todo = [(q, run) for q in requests for run in range(runs) if (q["id"], q["condition"], run) not in done]
    print(f"{len(todo)} requests to send, {len(done)} already done", flush=True)
    with open(out_path, "a") as out, ThreadPoolExecutor(workers) as pool:
        futures = [pool.submit(client.reply, q, run) for q, run in todo]
        try:
            for i, fut in enumerate(as_completed(futures), 1):
                row = fut.result()
                append(out, row)
                print(i, row["id"][:40], row["condition"], row["run"], row.get("prompt_tokens"),
                      row.get("output_tokens"), row.get("finish_reason") or row["error"][:60],
                      row["seconds"], flush=True)
        except StopJob:
            pool.shutdown(wait=False, cancel_futures=True)
            raise


def run_probes(client, requests, out_path):
    done = {r["id"] for r in read_rows(out_path)}
    with open(out_path, "a") as out:
        for q in requests:
            if q["condition"].startswith("image") and q["id"] not in done:
                done.add(q["id"])
                append(out, {"model": client.repo, "id": q["id"], "text_part_tokens": client.text_part_tokens(q)})


def run_seed_check(client, requests, out_path):
    if len(read_rows(out_path)) >= 3:
        return
    q = next(r for r in requests if r["condition"] == "text")
    with open(out_path, "w") as out:
        for tag, seed in (("a", 0), ("b", 0), ("c", 1)):
            row = client.reply(q, seed)
            append(out, {**row, "tag": tag})


def hf_revision(repo):
    ref = os.path.join(os.environ.get("HF_HOME", ""), "hub", "models--" + repo.replace("/", "--"),
                       "refs", "main")
    return open(ref).read().strip() if os.path.exists(ref) else None


def versions():
    out = {}
    for pkg in ("vllm", "torch", "transformers", "pillow"):
        try:
            out[pkg] = metadata.version(pkg)
        except metadata.PackageNotFoundError:
            out[pkg] = None
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(prog="codeimg generate", description=__doc__.split("\n")[0])
    ap.add_argument("--model", required=True, help="short name from configs/experiment.toml")
    ap.add_argument("--requests", required=True, help="requests.jsonl from codeimg prompts")
    ap.add_argument("--out", required=True, help="output JSONL, one per (model, benchmark)")
    ap.add_argument("--port", type=int, required=True)
    runs_arg = ap.add_mutually_exclusive_group()
    runs_arg.add_argument("--runs", type=int, help="default: experiment.runs")
    runs_arg.add_argument("--runs-from", help="D-study JSON with the runs per benchmark and model")
    ap.add_argument("--probe", action="store_true")
    ap.add_argument("--seed-check", action="store_true")
    args = ap.parse_args(argv)
    cfg = config.load()
    repo = cfg["models"][args.model]["repo"]
    requests = read_rows(args.requests)
    runs = args.runs or cfg["experiment"]["runs"]
    if args.runs_from:
        benchmarks = {q["benchmark"] for q in requests}
        if len(benchmarks) != 1:
            sys.exit(f"--runs-from needs one benchmark per requests file, got {sorted(benchmarks)}")
        try:
            runs = config.runs_from(args.runs_from, benchmarks.pop(), [repo])[repo]
        except ValueError as e:
            sys.exit(str(e))
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    client = Client(f"http://localhost:{args.port}/v1/chat/completions", repo, cfg,
                    os.path.dirname(os.path.abspath(args.requests)))
    meta = {"model": repo, "short": args.model, "requests": os.path.abspath(args.requests),
            "runs": runs, "seeds": list(range(runs)), "concurrency": cfg["experiment"]["concurrency"],
            "job_start": os.environ.get("CODEIMG_JOB_START"),
            "server_ready": os.environ.get("CODEIMG_SERVER_READY"), "start": time.time(),
            "hostname": socket.gethostname(), "gpu": os.environ.get("CODEIMG_GPU"),
            "code_dir": config.ROOT, "hf_revision": hf_revision(repo), "versions": versions(),
            "config": cfg}
    try:
        with urllib.request.urlopen(f"http://localhost:{args.port}/version", timeout=30) as r:
            meta["vllm_server"] = json.load(r)
    except OSError as e:
        meta["vllm_server"] = repr(e)
    try:
        if args.probe:
            run_probes(client, requests, args.out + ".probe.jsonl")
        if args.seed_check:
            run_seed_check(client, requests, args.out + ".seedcheck.jsonl")
        run_grid(client, requests, runs, args.out, cfg["experiment"]["concurrency"])
    except StopJob as e:
        print(f"stopping: {e}", file=sys.stderr)
        meta["stopped"] = str(e)
        sys.exit(1)
    finally:
        meta["end"] = time.time()
        # one meta file per job, so a resubmitted job does not overwrite the first one's record
        with open(f"{args.out}.meta.{os.environ.get('SLURM_JOB_ID', 'local')}.json", "w") as f:
            json.dump(meta, f, indent=1)
