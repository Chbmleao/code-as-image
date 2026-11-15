"""What the Claude smoke measured, and the full run's cost projected from it (UFM-24).

  python scripts/claude_smoke.py --run-dir ~/UFMG/ufm9-claude/smoke --out results/claude/smoke

Reads the generation rows and run logs that `codeimg claude` wrote in the run dir. Writes
smoke.json and smoke.md. Tokens per page come from the count step: a request's input tokens minus
those of the same request without its images, over its image count.

The projection is the budget rule of the methodology addendum applied to the whole grid: per model,
the sum over (benchmark, condition) of the requests times the smoke's mean cost per request, times
1.1. It rests on 5 items per benchmark, so read it as an order of magnitude.
"""
import argparse
import json
import os
import statistics
import sys
from collections import defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
from codeimg import config

BENCHES = ("coderujb", "deveval")
CONDITIONS = ("text", "image10", "image12", "image14")
# items per benchmark and runs per cell in the full Claude run (methodology addendum)
ITEMS = {"coderujb": 136, "deveval": 859}
RUNS = 2


def read_jsonl(path):
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f]


def mean(xs):
    return round(statistics.mean(xs), 1) if xs else None


def pages(log):
    """Mean tokens per page, per (benchmark, condition) and overall."""
    cells, every = defaultdict(list), []
    for r in log:
        if r["kind"] == "count" and r["n_images"]:
            t = (r["input_tokens"] - r["text_part_tokens"]) / r["n_images"]
            cells[f"{r['request'][0]} {r['request'][2]}"].append(t)
            every.append(t)
    return {"all": mean(every), **{c: mean(v) for c, v in sorted(cells.items())}}


def account(log):
    """What the account answered: batches refused at creation and results refused for credit."""
    blocked = [r["error"] for r in log if r["kind"] == "batch" and r["decision"] == "blocked"]
    refused = [f"{r['error_type']}: {r['error_message']}" for r in log
               if r["kind"] == "result" and r.get("account_error")]
    return {"batches_blocked": blocked, "results_refused": refused,
            "blocked": bool(blocked or refused)}


def summarize(m, rows, log):
    out = {"model": m["model"], "rows": len(rows), "cells": {}}
    by_cell = defaultdict(list)
    for r in rows:
        by_cell[(r["benchmark"], r["condition"])].append(r)
    total = 0.0
    for b in BENCHES:
        for c in CONDITIONS:
            rs = by_cell.get((b, c), [])
            ok = [r for r in rs if r["fail_reason"] != "request_error"]
            costs = [r["cost_usd"] for r in ok]
            n = ITEMS[b] * RUNS
            per = statistics.mean(costs) if costs else None
            out["cells"][f"{b} {c}"] = {
                "replies": len(ok),
                "prompt_tokens": mean([r["prompt_tokens"] for r in ok]),
                "output_tokens": mean([r["output_tokens"] for r in ok]),
                "output_tokens_max": max((r["output_tokens"] for r in ok), default=None),
                "thinking_tokens": mean([r["thinking_tokens"] or 0 for r in ok]),
                "non_thinking_max": max((r["output_tokens"] - (r["thinking_tokens"] or 0)
                                         for r in ok), default=None),
                "refusals": sum(r["fail_reason"] == "refusal" for r in rs),
                "over_budget": sum(r["fail_reason"] == "over_budget" for r in rs),
                "max_tokens": sum(r["finish_reason"] == "length" for r in rs),
                "other_stop": sum(r["fail_reason"] not in (None, "refusal", "over_budget",
                                                           "request_error") for r in rs),
                "request_errors": len(rs) - len(ok),
                "cost_per_request_usd": round(per, 6) if per is not None else None,
                "full_requests": n,
                "full_projected_usd": round(1.1 * n * per, 2) if per is not None else None,
            }
            total += 1.1 * n * per if per is not None else 0.0
    ok = [r for r in rows if r["fail_reason"] != "request_error"]
    thinking = [r["thinking_tokens"] or 0 for r in ok]
    output = sum(r["output_tokens"] for r in ok)
    out.update(
        measured_usd=round(sum(r["cost_usd"] for r in ok), 4),
        projected_usd=round(sum(r["projected_usd"] for r in log
                                if r["kind"] == "batch" and r["batch_id"]), 4),
        full_projected_usd=round(total, 2),
        full_complete=all(v["cost_per_request_usd"] is not None for v in out["cells"].values()),
        replies_with_thinking=sum(t > 0 for t in thinking),
        thinking_share=round(sum(thinking) / output, 4) if output else None,
        output_below_thinking=sum(r["output_tokens"] < (r["thinking_tokens"] or 0) for r in ok),
        refusal_categories=sorted({(x.get("stop_details") or {}).get("category") or "none"
                                   for x in log if x["kind"] == "result"
                                   and x.get("stop_reason") == "refusal"}),
        returned_models=sorted({x["returned_model"] for x in log
                                if x["kind"] == "result" and x.get("returned_model")}),
        account=account(log))
    return out


def markdown(res):
    lines = ["# Claude smoke", "",
             f"Tokens per page (count_tokens, mean over pages): {res['tokens_per_page']['all']}",
             ""]
    for short, s in res["models"].items():
        partial = "" if s["full_complete"] else " (some cells have no measured cost)"
        lines += [f"## {short} ({s['model']})", ""]
        lines.append(f"{s['rows']} rows; measured cost ${s['measured_usd']}, projected "
                     f"${s['projected_usd']}; returned model ids {s['returned_models']}.")
        lines.append(f"Replies with thinking tokens: {s['replies_with_thinking']}; thinking share "
                     f"{s['thinking_share']}; replies with output below thinking tokens: "
                     f"{s['output_below_thinking']}.")
        lines.append(f"Account blocked: {s['account']['blocked']}.")
        lines += [f"Full run projection: ${s['full_projected_usd']}{partial}", ""]
        lines.append("| cell | replies | prompt | output (max) | thinking | refusal | over budget "
                     "| max_tokens | errors | $/request | full $ |")
        lines.append("|---|---|---|---|---|---|---|---|---|---|---|")
        for c, v in s["cells"].items():
            lines.append(f"| {c} | {v['replies']} | {v['prompt_tokens']} | {v['output_tokens']} "
                         f"({v['output_tokens_max']}) | {v['thinking_tokens']} | {v['refusals']} "
                         f"| {v['over_budget']} | {v['max_tokens']} | {v['request_errors']} "
                         f"| {v['cost_per_request_usd']} | {v['full_projected_usd']} |")
        lines.append("")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--out", required=True, help="output dir")
    args = ap.parse_args()
    run_dir = os.path.expanduser(args.run_dir)
    models = config.claude_models(config.load())
    logs = {s: read_jsonl(os.path.join(run_dir, "claude", f"{s}.log.jsonl")) for s in models}
    res = {"tokens_per_page": pages([r for log in logs.values() for r in log]), "models": {}}
    for short, m in models.items():
        rows = [r for b in BENCHES
                for r in read_jsonl(os.path.join(run_dir, b, "gen", f"claude_{short}.jsonl"))]
        if rows or logs[short]:
            res["models"][short] = summarize(m, rows, logs[short])
    os.makedirs(args.out, exist_ok=True)
    with open(os.path.join(args.out, "smoke.json"), "w") as f:
        json.dump(res, f, indent=2)
    with open(os.path.join(args.out, "smoke.md"), "w") as f:
        f.write(markdown(res))
    print(markdown(res))


if __name__ == "__main__":
    main()
