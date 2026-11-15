"""Replies from Claude through the Message Batches API for every (item, condition) of one run.

docs/methodology.md, "Addendum: Claude extension". Three steps, each resumable, and one repair:

  count   input tokens per request from the count_tokens endpoint (free), with and without the
          images, for the smoke projection and the tokens per page
  submit  project the cost of the pending requests and submit, cut or wait (the budget rule)
  fetch   download ended batches: one row per reply; errored and expired requests are resubmitted
          by the next submit, up to `resubmissions` times, after which the row is a request_error
  adopt   log a batch whose create call timed out but which the server made anyway; submit
          refuses to run while such a batch may exist unlogged

Rows go to <run dir>/<benchmark>/gen/claude_<model>.jsonl in the vLLM row schema. The seed is
empty, since none is sent. Only text blocks reach `reply`; thinking text is never stored. The run
log, <run dir>/claude/<model>.log.jsonl, holds one record per count, batch (with its requests)
and result. The API key is read from the environment by the SDK and is never written anywhere.

No cache_control is sent. Cache tokens, if usage reports any, are added to prompt_tokens and
priced as input.
"""
import argparse
import base64
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from collections import defaultdict
from importlib import metadata

from codeimg import config
from codeimg.generate import append, read_rows

BENCHES = ("coderujb", "deveval")
FINISH = {"end_turn": "stop", "max_tokens": "length"}
# Billing, credit and spend-limit errors wait for credit and do not use up a resubmission. A spend
# limit can come back as a 400 with only a message, so the message is matched too.
ACCOUNT = re.compile(r"billing|credit|spend.?limit|usage limit", re.IGNORECASE)


def custom_id(key, attempt):
    """batch custom_ids allow only [a-zA-Z0-9_-]{1,64}, so item ids are hashed; the log maps back"""
    return hashlib.sha256(json.dumps([*key, attempt]).encode()).hexdigest()[:40]


def content(req, base_dir, images=True):
    out = []
    for p in req["parts"]:
        if p["type"] == "text":
            out.append({"type": "text", "text": p["text"]})
        elif images:
            with open(os.path.join(base_dir, p["path"]), "rb") as f:
                data = base64.b64encode(f.read()).decode()
            out.append({"type": "image", "source": {"type": "base64", "media_type": "image/png",
                                                    "data": data}})
    return out


def settings(m):
    """What is sent besides the message: no temperature, top_p, top_k, seed, system or cache."""
    return {"model": m["model"], "max_tokens": m["max_tokens"], "thinking": dict(m["thinking"]),
            "output_config": {"effort": m["effort"]}}


def params(m, req, base_dir):
    return {**settings(m), "messages": [{"role": "user", "content": content(req, base_dir)}]}


def cost(m, usage):
    tokens_in = (usage["input_tokens"] + (usage["cache_creation_input_tokens"] or 0)
                 + (usage["cache_read_input_tokens"] or 0))
    return (tokens_in * m["price_in"] + usage["output_tokens"] * m["price_out"]) / 1e6


def fail_reason(stop_reason, output_tokens, thinking_tokens, budget):
    """Reasons in the addendum's order; None means the reply goes to grading (no_reply is decided
    there, from the text). max_tokens replies are graded."""
    if stop_reason == "refusal":
        return "refusal"
    if budget is not None and output_tokens - (thinking_tokens or 0) > budget:
        return "over_budget"
    if stop_reason not in FINISH:
        return stop_reason
    return None


def account_error(etype, code, message):
    return etype == "billing_error" or bool(ACCOUNT.search(code or "")) or bool(
        ACCOUNT.search(message or ""))


class Run:
    """One model's requests, rows and run log in a run dir."""

    def __init__(self, cfg, short, run_dir):
        self.cfg, self.short, self.dir = cfg["claude"], short, run_dir
        self.m = config.claude_models(cfg)[short]
        self.requests = {b: read_rows(os.path.join(run_dir, b, "requests.jsonl")) for b in BENCHES}
        self.log_path = os.path.join(run_dir, "claude", f"{short}.log.jsonl")
        os.makedirs(os.path.dirname(self.log_path), exist_ok=True)
        for b in BENCHES:
            if self.requests[b]:
                os.makedirs(os.path.dirname(self.gen_path(b)), exist_ok=True)

    def gen_path(self, bench):
        return os.path.join(self.dir, bench, "gen", f"claude_{self.short}.jsonl")

    def base_dir(self, bench):
        return os.path.join(self.dir, bench)

    def log(self):
        return read_rows(self.log_path)

    def write_log(self, rec):
        with open(self.log_path, "a") as f:
            append(f, rec)

    def rows(self):
        return [r for b in BENCHES for r in read_rows(self.gen_path(b))]

    def done(self):
        return {(r["benchmark"], r["id"], r["condition"], r["run"]) for r in self.rows()}

    def state(self):
        """(attempts by custom_id, open batch records, counted failures per key).

        A batch record holds its requests, so one appended line makes a batch and its attempts
        known together."""
        log = self.log()
        batches = [r for r in log if r["kind"] == "batch" and r["batch_id"]]
        attempts = {a["custom_id"]: {**a, "batch_id": r["batch_id"]}
                    for r in batches for a in r["requests"]}
        ended = {r["batch_id"] for r in log if r["kind"] == "batch_end"}
        open_ = [r for r in batches if r["batch_id"] not in ended]
        failures = defaultdict(int)
        for r in log:
            if r["kind"] == "result" and r["counts"]:
                failures[tuple(r["key"])] += 1
        return attempts, open_, failures

    def pending(self, run):
        _, open_, failures = self.state()
        in_flight = {tuple(a["key"]) for b in open_ for a in b["requests"]}
        done = self.done()
        limit, out = self.cfg["resubmissions"], []
        for b in BENCHES:
            for q in self.requests[b]:
                k = (b, q["id"], q["condition"], run)
                if k not in done and k not in in_flight and failures[k] <= limit:
                    out.append((q, k))
        return out

    def counts(self):
        return {tuple(r["request"]): r for r in self.log() if r["kind"] == "count"}


def count(client, run):
    """Input tokens per request with and without its images; skips requests already counted."""
    have = run.counts()
    for b in BENCHES:
        for q in run.requests[b]:
            k = (b, q["id"], q["condition"])
            if k in have:
                continue
            n = {}
            for name, images in (("input_tokens", True), ("text_part_tokens", False)):
                if not images and not q["n_images"]:
                    n[name] = n["input_tokens"]
                    continue
                r = client.messages.count_tokens(
                    messages=[{"role": "user", "content": content(q, run.base_dir(b), images)}],
                    **{k2: v for k2, v in settings(run.m).items() if k2 != "max_tokens"})
                n[name] = r.input_tokens
            run.write_log({"kind": "count", "model": run.m["model"], "request": list(k),
                           "n_images": q["n_images"], **n})
            print("count", b, q["id"][:40], q["condition"], n, flush=True)


def estimates(run, todo, cost_rows):
    """Cost per request for each pending request, and the mean per (benchmark, condition).

    With cost_rows (the model's returned rows: the smoke until its first batch returns, then all of
    them) a request costs its cell's mean measured cost. Without, it is the smoke ceiling: counted
    input tokens plus max_tokens of output (decisions, 2026-11-14)."""
    measured = defaultdict(list)
    for r in cost_rows:
        if r.get("cost_usd") is not None:
            measured[(r["benchmark"], r["condition"])].append(r["cost_usd"])
    have = run.counts()
    per = []
    for q, k in todo:
        cell = (k[0], q["condition"])
        if cost_rows:
            if not measured[cell]:
                sys.exit(f"no measured cost for {cell}")
            per.append(sum(measured[cell]) / len(measured[cell]))
        else:
            if k[:3] not in have:
                sys.exit(f"no token count for {k[:3]}; run `count` first")
            per.append((have[k[:3]]["input_tokens"] * run.m["price_in"]
                        + run.m["max_tokens"] * run.m["price_out"]) / 1e6)
    cells = defaultdict(list)
    for (q, k), c in zip(todo, per):
        cells[f"{k[0]} {q['condition']}"].append(c)
    return per, {c: round(sum(v) / len(v), 6) for c, v in sorted(cells.items())}


def chunks(run, todo):
    """Batches under the request and byte caps, each a list of (request, key, params)."""
    out, cur, size = [], [], 0
    for q, k in todo:
        p = params(run.m, q, run.base_dir(k[0]))
        n = len(json.dumps(p))
        if cur and (len(cur) >= run.cfg["batch_requests"] or size + n > run.cfg["batch_bytes"]):
            out.append(cur)
            cur, size = [], 0
        cur.append((q, k, p))
        size += n
    return out + [cur] if cur else out


def code_version():
    """HEAD and a hash of the uncommitted changes, untracked files included (decisions, Nov 14)."""
    def git(*a):
        return subprocess.run(["git", "-C", config.ROOT, *a], capture_output=True,
                              check=True).stdout
    try:
        h = hashlib.sha256(git("diff", "HEAD", "--binary"))
        untracked = git("ls-files", "--others", "--exclude-standard", "-z").decode().split("\0")
        for p in sorted(filter(None, untracked)):
            h.update(p.encode())
            with open(os.path.join(config.ROOT, p), "rb") as f:
                h.update(f.read())
        status = git("status", "--porcelain").strip()
        return {"commit": git("rev-parse", "HEAD").decode().strip(), "dirty": bool(status),
                "diff_sha256": h.hexdigest() if status else None}
    except (OSError, subprocess.CalledProcessError) as e:
        return {"commit": None, "error": repr(e)}


def sdk_version():
    try:
        return metadata.version("anthropic")
    except metadata.PackageNotFoundError:
        return None


def unknown_batches(client, run):
    """Batches created since a create call whose outcome is unknown that no run log here knows.

    Such a batch may exist and be billed, so nothing more is submitted until it is adopted."""
    log = run.log()
    resolved = {r["submitted_at"] for r in log if r["kind"] == "batch_resolved"}
    unsure = [r for r in log if r["kind"] == "batch" and r["decision"] == "create_unknown"
              and r["submitted_at"] not in resolved]
    if not unsure:
        return []
    log_dir, known = os.path.dirname(run.log_path), set()
    for p in os.listdir(log_dir):
        if p.endswith(".log.jsonl"):
            known |= {r["batch_id"] for r in read_rows(os.path.join(log_dir, p))
                      if r["kind"] == "batch" and r["batch_id"]}
    since = min(r["submitted_at"] for r in unsure) - 60
    return [b.id for b in client.messages.batches.list(limit=100).data
            if b.id not in known and b.created_at.timestamp() >= since]


def adopt(client, run, batch_id):
    """Logs an unknown batch as the last create call whose outcome was unknown."""
    log = run.log()
    resolved = {r["submitted_at"] for r in log if r["kind"] == "batch_resolved"}
    unsure = [r for r in log if r["kind"] == "batch" and r["decision"] == "create_unknown"
              and r["submitted_at"] not in resolved]
    if not unsure:
        sys.exit("no create call with an unknown outcome to adopt a batch for")
    rec = unsure[-1]
    batch = client.messages.batches.retrieve(batch_id)
    run.write_log({**rec, "batch_id": batch.id, "decision": rec["intended"], "adopted": True,
                   "created_at": str(batch.created_at), "expires_at": str(batch.expires_at)})
    for r in unsure:
        run.write_log({"kind": "batch_resolved", "submitted_at": r["submitted_at"]})


def submit(client, run, run_index, balance, cost_rows, yes, ceiling=False):
    """The budget rule: submit, cut to the largest count that fits, or wait. Returns the decision.

    Cost per request is measured on cost_rows plus the model's rows already in the run dir. The
    count_tokens ceiling is for the smoke only (decisions, 2026-11-14), so it must be asked for and
    is refused once measured costs exist."""
    cost_rows = list(cost_rows) + [r for r in run.rows() if r.get("cost_usd") is not None]
    if ceiling and cost_rows:
        sys.exit("measured costs exist, so the count_tokens ceiling does not apply")
    if not ceiling and not cost_rows:
        sys.exit("no measured cost: pass --cost-from with the smoke rows, or --ceiling for the "
                 "smoke")
    unknown = unknown_batches(client, run)
    if unknown:
        sys.exit(f"batches not in any run log: {unknown}; log the one this run created with "
                 "`adopt --batch ID` (cancel it in the Console first if it should not run)")
    todo = run.pending(run_index)
    if not todo:
        print("nothing pending")
        return None
    per, per_cell = estimates(run, todo, cost_rows)
    _, open_, _ = run.state()
    unbilled = sum(b["projected_usd"] for b in open_)
    remaining = balance - unbilled
    # the largest number of requests that fits is the cheapest ones first
    chosen, total = [], 0.0
    for i in sorted(range(len(todo)), key=lambda i: per[i]):
        if total + 1.1 * per[i] > remaining:
            break
        chosen.append(i)
        total += 1.1 * per[i]
    fits = len(chosen)
    decision = "submitted" if fits == len(todo) else "cut" if fits else "waited"
    projected_all = round(1.1 * sum(per), 4)
    print(f"{run.short} run {run_index}: {len(todo)} pending, projected ${projected_all}, "
          f"balance ${balance} minus ${round(unbilled, 4)} unbilled = ${round(remaining, 4)}; "
          f"{decision} ({fits} requests, ${round(total, 4)})")
    for c, v in per_cell.items():
        print(f"  {c}: ${v} per request")
    if not yes:
        print("dry run; pass --yes to act on this decision")
        return decision
    base = {"kind": "batch", "model": run.m["model"], "run": run_index, "balance_usd": balance,
            "purchased_zero": True, "auto_reload_off": True, "pending": len(todo),
            "projected_all_usd": projected_all, "cost_per_request_usd": per_cell,
            "cost_source": "measured" if cost_rows else "count_tokens ceiling",
            "decision": decision, "settings": settings(run.m),
            "anthropic_version": client.default_headers.get("anthropic-version"),
            "sdk": sdk_version(), "code": code_version(), "submitted_at": time.time()}
    if not fits:
        run.write_log({**base, "batch_id": None, "requests": [], "projected_usd": 0.0})
        return decision
    import anthropic

    attempts, _, _ = run.state()
    tries = defaultdict(int)
    for a in attempts.values():
        tries[tuple(a["key"])] += 1
    cost_of = {todo[i][1]: per[i] for i in chosen}
    # the SDK retries a timed-out POST by default, which could create a second, unlogged batch
    once = client.with_options(max_retries=0)
    for chunk in chunks(run, [todo[i] for i in sorted(chosen)]):
        reqs = [{"custom_id": custom_id(k, tries[k]), "key": list(k), "attempt": tries[k]}
                for _, k, _ in chunk]
        projected = round(1.1 * sum(cost_of[k] for _, k, _ in chunk), 6)
        try:
            batch = once.messages.batches.create(requests=[
                {"custom_id": a["custom_id"], "params": p} for a, (_, _, p) in zip(reqs, chunk)])
        except anthropic.APIStatusError as e:
            # the server answered, so no batch exists; a credit or spend-limit refusal here is
            # what the smoke must record
            blocked = account_error(e.type, e.error_code, e.api_message)
            run.write_log({**base, "batch_id": None, "requests": [], "projected_usd": 0.0,
                           "decision": "blocked" if blocked else "create_failed",
                           "error": f"{e.status_code} {e.type} {e.error_code}: {e.api_message}"})
            raise
        except anthropic.APIConnectionError as e:
            run.write_log({**base, "batch_id": None, "requests": reqs, "projected_usd": projected,
                           "decision": "create_unknown", "intended": decision,
                           "error": f"{type(e).__name__}: {e}"})
            raise
        run.write_log({**base, "batch_id": batch.id, "created_at": str(batch.created_at),
                       "expires_at": str(batch.expires_at), "requests": reqs,
                       "projected_usd": projected})
        print(f"batch {batch.id}: {len(chunk)} requests, projected ${projected}", flush=True)
    return decision


def result_row(run, q, key, msg):
    u = msg.usage
    thinking = u.output_tokens_details.thinking_tokens if u.output_tokens_details else None
    usage = {"input_tokens": u.input_tokens, "output_tokens": u.output_tokens,
             "thinking_tokens": thinking,
             "cache_creation_input_tokens": u.cache_creation_input_tokens,
             "cache_read_input_tokens": u.cache_read_input_tokens}
    budget = run.cfg["answer_budget"] if run.m["over_budget"] else None
    if budget is not None and thinking is None and u.output_tokens > budget:
        # the addendum defines non-thinking tokens from thinking_tokens; without it the rule
        # cannot be applied as written
        sys.exit(f"{msg.id}: {u.output_tokens} output tokens and no thinking_tokens in usage")
    reason = fail_reason(msg.stop_reason, u.output_tokens, thinking, budget)
    row = {"model": run.m["model"], "benchmark": key[0], "id": q["id"], "condition": q["condition"],
           "run": key[3], "seed": None, "n_images": q["n_images"],
           "reply": "".join(b.text for b in msg.content if b.type == "text"),
           "finish_reason": FINISH.get(msg.stop_reason, msg.stop_reason),
           "prompt_tokens": (u.input_tokens + (u.cache_creation_input_tokens or 0)
                             + (u.cache_read_input_tokens or 0)),
           "output_tokens": u.output_tokens, "thinking_tokens": thinking,
           "cost_usd": round(cost(run.m, usage), 8), "fail_reason": reason, "error": None,
           "seconds": None}
    detail = {"message_id": msg.id, "returned_model": msg.model, "usage": usage,
              "stop_reason": msg.stop_reason,
              "stop_details": msg.stop_details.to_dict() if msg.stop_details else None}
    return row, detail


def error_row(run, q, key, message):
    return {"model": run.m["model"], "benchmark": key[0], "id": q["id"],
            "condition": q["condition"], "run": key[3], "seed": None, "n_images": q["n_images"],
            "reply": None, "finish_reason": None, "prompt_tokens": None, "output_tokens": None,
            "thinking_tokens": None, "cost_usd": None, "fail_reason": "request_error",
            "error": message, "seconds": None}


def fetch(client, run, wait=False, poll=300):
    """Downloads every ended open batch. With wait, polls until none is open."""
    by_key = {(b, q["id"], q["condition"]): q for b in BENCHES for q in run.requests[b]}
    while True:
        attempts, open_, failures = run.state()
        logged = {r["custom_id"] for r in run.log() if r["kind"] == "result"}
        still_open = 0
        for rec in open_:
            batch = client.messages.batches.retrieve(rec["batch_id"])
            if batch.processing_status != "ended":
                still_open += 1
                print(f"batch {batch.id}: {batch.processing_status} "
                      f"{batch.request_counts.to_dict()}", flush=True)
                continue
            done = run.done()
            for res in client.messages.batches.results(batch.id):
                if res.custom_id in logged:
                    continue
                a = attempts[res.custom_id]
                key = tuple(a["key"])
                q = by_key[key[:3]]
                # resubmissions counts only the failed attempts that use up the limit; attempt
                # also counts those that waited for credit
                rec_out = {"kind": "result", "custom_id": res.custom_id, "batch_id": batch.id,
                           "key": list(key), "attempt": a["attempt"],
                           "resubmissions": failures[key], "type": res.result.type,
                           "counts": False}
                if res.result.type == "succeeded":
                    row, detail = result_row(run, q, key, res.result.message)
                    rec_out.update(detail)
                    if key not in done:
                        with open(run.gen_path(key[0]), "a") as f:
                            append(f, row)
                else:
                    err = res.result.error.error.to_dict() if res.result.type == "errored" else {}
                    etype, msg = err.get("type", res.result.type), err.get("message")
                    code = (err.get("details") or {}).get("error_code")
                    counts = res.result.type in ("errored", "expired") and not account_error(
                        etype, code, msg)
                    rec_out.update(error_type=etype, error_code=code, error_message=msg,
                                   counts=counts, account_error=account_error(etype, code, msg))
                    if counts:
                        failures[key] += 1
                    if failures[key] > run.cfg["resubmissions"] and key not in done:
                        with open(run.gen_path(key[0]), "a") as f:
                            append(f, error_row(run, q, key, f"{etype}: {msg}"))
                run.write_log(rec_out)
            run.write_log({"kind": "batch_end", "batch_id": batch.id,
                           "ended_at": str(batch.ended_at), "expires_at": str(batch.expires_at),
                           "request_counts": batch.request_counts.to_dict()})
            print(f"batch {batch.id}: ended {batch.request_counts.to_dict()}", flush=True)
        if not (wait and still_open):
            return still_open
        time.sleep(poll)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="codeimg claude", description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="step", required=True)
    for name in ("count", "submit", "fetch", "adopt"):
        p = sub.add_parser(name)
        p.add_argument("--model", required=True,
                       help="short name under [claude] in experiment.toml")
        p.add_argument("--run-dir", required=True, help="holds <benchmark>/requests.jsonl")
        if name == "submit":
            p.add_argument("--run", type=int, required=True, help="run number, one per submit")
            p.add_argument("--balance", type=float, required=True,
                           help="Console credit balance in US$, read just before submitting")
            p.add_argument("--purchased-zero", action="store_true", required=True,
                           help="the Console shows a purchased balance of $0")
            p.add_argument("--auto-reload-off", action="store_true", required=True,
                           help="the Console shows auto-reload off")
            p.add_argument("--cost-from", nargs="*", default=[],
                           help="the smoke's generation rows of this model, for cost per request")
            p.add_argument("--ceiling", action="store_true",
                           help="the smoke only: project from token counts and max_tokens")
            p.add_argument("--yes", action="store_true", help="act on the decision (else dry run)")
        if name == "fetch":
            p.add_argument("--wait", action="store_true")
        if name == "adopt":
            p.add_argument("--batch", required=True,
                           help="a batch that `submit` reported as not in any run log")
    args = ap.parse_args(argv)
    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("ANTHROPIC_API_KEY is not set")
    import anthropic

    cfg = config.load()
    client = anthropic.Anthropic()
    sent = client.default_headers.get("anthropic-version")
    if sent != cfg["claude"]["anthropic_version"]:
        sys.exit(f"the SDK sends anthropic-version {sent}, the config says "
                 f"{cfg['claude']['anthropic_version']}")
    run = Run(cfg, args.model, args.run_dir)
    if args.step == "count":
        count(client, run)
    elif args.step == "submit":
        cost_rows = [r for p in args.cost_from for r in read_rows(p)
                     if r["model"] == run.m["model"]]
        submit(client, run, args.run, args.balance, cost_rows, args.yes, args.ceiling)
    elif args.step == "adopt":
        adopt(client, run, args.batch)
    else:
        fetch(client, run, args.wait)
