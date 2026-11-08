"""Checks the smoke run against the spec's cluster criteria and prints one line per check.

Run on the cluster with the ufm8 venv after collect has written <run>/<benchmark>/collected.jsonl:

  python scripts/check_smoke.py --run /snfs2/carlosleao/ufm9/smoke --local-requests DIR
      [--logs LOG...] --out results/smoke/checks.json

--local-requests holds <benchmark>/requests.jsonl rendered on the laptop, for the sha256 check.
--logs takes the generation and grading job logs, not the vLLM server logs, which print benign
tracebacks (compile-cache misses, the engine abort when the job stops the server).
"""
import argparse
import json
import os
import statistics
import sys
from collections import defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
from codeimg import config
from codeimg.collect import grade_fields

BENCHES = ("coderujb", "deveval")
UFM7 = "/snfs2/carlosleao/ufm7"


def read_jsonl(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f]


def check_grid(run, cfg, n_items):
    rows = {b: read_jsonl(f"{run}/{b}/collected.jsonl") for b in BENCHES}
    expected = n_items * len(cfg["models"]) * (1 + len(cfg["experiment"]["sizes"]))
    counts = {b: len(r) for b, r in rows.items()}
    return all(c == expected for c in counts.values()), f"rows per benchmark {counts}, expected {expected}", rows


def check_gen_errors(run, cfg):
    """Rows with an error; with no request_error expected, any is a failure."""
    errs = defaultdict(list)
    for b in BENCHES:
        for m in cfg["models"]:
            for r in read_jsonl(f"{run}/{b}/gen/{m}.jsonl"):
                if r.get("error"):
                    errs[m].append(f"{b} {r['id'][:16]} {r['condition']} {r['error'][:80]}")
    return not errs, f"{sum(map(len, errs.values()))} error rows {dict(errs)}"


def check_logs(logs):
    bad = []
    for p in logs:
        with open(p, errors="replace") as f:
            if "Traceback" in f.read():
                bad.append(p)
    return not bad, f"{len(logs)} logs, with Traceback: {bad}"


def check_images_reach_model(run, cfg):
    notes, ok = [], True
    for m in cfg["models"]:
        diffs = []
        for b in BENCHES:
            probe = {r["id"]: r["text_part_tokens"] for r in read_jsonl(f"{run}/{b}/gen/{m}.jsonl.probe.jsonl")}
            for r in read_jsonl(f"{run}/{b}/gen/{m}.jsonl"):
                if r["n_images"] and r.get("prompt_tokens"):
                    diffs.append((r["n_images"], r["prompt_tokens"] - probe[r["id"]]))
        positive = all(d > 0 for _, d in diffs)
        corr = statistics.correlation(*zip(*diffs)) if len(diffs) > 2 else float("nan")
        per_page = statistics.median(d / n for n, d in diffs) if diffs else None
        ok &= positive and corr > 0
        notes.append(f"{m}: all>0 {positive}, corr(pages, image tokens) {corr:.2f}, median tokens/page {per_page}")
    return ok, "; ".join(notes)


def check_gold(run):
    notes, ok = [], True
    for b in BENCHES:
        rows = read_jsonl(f"{run}/{b}/gold/grades.jsonl")
        failed = [r.get("task_id") or r.get("key") for r in rows if not grade_fields(b, r)[0]]
        ok &= len(rows) == 5 and not failed
        notes.append(f"{b}: {len(rows)} graded, failed {failed}")
    return ok, "; ".join(notes)


def check_regrade(run):
    """Moved graders vs the calibration grade_results.jsonl, on the same answers.

    The verdict must agree: CoderUJB's pass_trigger and, when it failed, the stage it failed at;
    DevEval's result. The CoderUJB full-suite stage after a pass is reported, not gated: it holds
    timing tests that flip under load (Lang StopWatchTest), and it is not the primary outcome.
    """
    notes, ok = [], True
    old_paths = {"coderujb": f"{UFM7}/coderujb/grade_results.jsonl",
                 "deveval": f"{UFM7}/deveval_calib/grade_results.jsonl"}
    for b, k in (("coderujb", "task_id"), ("deveval", "key")):
        new = read_jsonl(f"{run}/regrade/{b}_grades.jsonl")
        old = {r[k]: r for r in read_jsonl(old_paths[b])}
        diff, suite = [], []
        for r in new:
            o = old[r[k]]
            if b == "deveval":
                verdict = (r["result"],), (o["result"],)
            else:
                verdict = ((r["pass_trigger"], None if r["pass_trigger"] else r["stage"]),
                           (o["pass_trigger"], None if o["pass_trigger"] else o["stage"]))
                if r["pass_trigger"] and o["pass_trigger"] and r["stage"] != o["stage"]:
                    suite.append(f"{r[k][-12:]} {o['stage']}->{r['stage']}")
            if verdict[0] != verdict[1]:
                diff.append(r[k])
        ok &= len(new) == {"coderujb": 5, "deveval": 30}[b] and not diff
        notes.append(f"{b}: {len(new)} regraded, verdict differs {diff}"
                     + (f", suite stage flipped {suite}" if suite else ""))
    return ok, "; ".join(notes)


def check_seeds(run, cfg):
    notes, ok, repeat = [], True, {}
    for m in cfg["models"]:
        rows = {r["tag"]: r for r in read_jsonl(f"{run}/coderujb/gen/{m}.jsonl.seedcheck.jsonl")}
        differs = rows["c"]["reply"] != rows["a"]["reply"]
        repeat[m] = rows["a"]["reply"] == rows["b"]["reply"]
        ok &= differs
        notes.append(f"{m}: seed1 differs {differs}, seed0 repeats {repeat[m]}")
    return ok, "; ".join(notes), repeat


def check_render(run, local):
    notes, ok = [], True
    for b in BENCHES:
        sha = {}
        for name, d in (("cluster", run), ("local", local)):
            sha[name] = [(p["size"], p["pixels_sha256"]) for r in read_jsonl(f"{d}/{b}/requests.jsonl")
                         for p in r["parts"] if p["type"] == "image"]
        same = sha["cluster"] == sha["local"] and len(sha["local"]) > 0
        ok &= same
        notes.append(f"{b}: {len(sha['cluster'])} pages, same pixels {same}")
    return ok, "; ".join(notes)


def check_meta(run, cfg):
    missing = []
    for b in BENCHES:
        for m in cfg["models"]:
            metas = [f for f in os.listdir(f"{run}/{b}/gen") if f.startswith(f"{m}.jsonl.meta.")]
            if not metas:
                missing.append(f"{b}/{m}: no meta")
            for f in metas:
                with open(f"{run}/{b}/gen/{f}") as fh:
                    meta = json.load(fh)
                for k in ("versions", "hf_revision", "server_ready", "config", "vllm_server"):
                    if not meta.get(k) or (k == "versions" and not all(meta[k].values())):
                        missing.append(f"{b}/{f}: {k}")
    return not missing, f"missing {missing}"


def no_code_share(rows):
    out = {}
    for b, rs in rows.items():
        by = defaultdict(lambda: [0, 0])
        for r in rs:
            kind = "text" if r["condition"] == "text" else "image"
            by[(r["model"], kind)][0] += r["reason"] == "no_code"
            by[(r["model"], kind)][1] += 1
        out[b] = {f"{m} {k}": f"{n}/{t}" for (m, k), (n, t) in sorted(by.items())}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--local-requests", required=True)
    ap.add_argument("--logs", nargs="*", default=[])
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    cfg = config.load()
    n_items = len(read_jsonl(f"{args.run}/coderujb/requests.jsonl")) // (1 + len(cfg["experiment"]["sizes"]))
    results, rows, repeat = {}, {b: [] for b in BENCHES}, {}

    def run(name, fn):
        try:
            return fn()
        except (OSError, KeyError, ValueError) as e:
            results[name] = (False, f"could not check: {e!r}")
            return None

    def grid():
        nonlocal rows
        ok, note, rows = check_grid(args.run, cfg, n_items)
        results["grid"] = (ok, note)

    def seeds():
        ok, note, rep = check_seeds(args.run, cfg)
        repeat.update(rep)
        results["seeds"] = (ok, note)

    run("grid", grid)
    req_err = [r["key"] for rs in rows.values() for r in rs if r["reason"] == "request_error"]
    results["no_request_error"] = (not req_err, f"request_error keys {req_err}")
    checks = {"no_other_errors": lambda: check_gen_errors(args.run, cfg),
              "logs": lambda: check_logs(args.logs),
              "images_reach_model": lambda: check_images_reach_model(args.run, cfg),
              "gold": lambda: check_gold(args.run),
              "regrade": lambda: check_regrade(args.run),
              "render_sha": lambda: check_render(args.run, args.local_requests),
              "meta": lambda: check_meta(args.run, cfg)}
    for name, fn in checks.items():
        out = run(name, fn)
        if out is not None:
            results[name] = out
    run("seeds", seeds)
    for name, (ok, note) in results.items():
        print(f"{'PASS' if ok else 'FAIL'} {name}: {note}")
    shares = no_code_share(rows)
    print("no_code share (report only):", json.dumps(shares, indent=1))
    with open(args.out, "w") as f:
        json.dump({"checks": {k: {"pass": v[0], "note": v[1]} for k, v in results.items()},
                   "seed0_repeats": repeat, "no_code_share": shares}, f, indent=1)
    sys.exit(0 if all(v[0] for v in results.values()) else 1)


if __name__ == "__main__":
    main()
