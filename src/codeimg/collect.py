"""One row per answer: passed, reason, and what is needed to analyse it.

Joins the generation rows with the answers stage and the grader output, and checks that the grid
is complete: every (model, item, condition, run) has exactly one generation row, and every answer
has exactly one grade. Any gap is listed and the exit code is nonzero.

The primary outcome is docs/methodology.md 3.1: CoderUJB passes when all target tests pass
(pass_trigger; the full-suite result is kept in `suite`), DevEval when all pytest ids pass.
"""
import argparse
import json
import sys
from collections import Counter

from codeimg import config
from codeimg.answers import answer_key, read_jsonl

UJB_SUITE = {"pass": "pass", "suite_fail": "suite_fail", "suite_timeout": "suite_timeout"}
DEV_REASON = {"Pass": "pass", "Error": "error", "TimeOut": "timeout"}


def grade_fields(bench, g):
    """(passed, reason, extra fields) from one grader row."""
    if bench == "coderujb":
        if g["pass_trigger"]:
            return True, "pass", {"suite": UJB_SUITE[g["stage"]], "pass_all": g["pass_all"]}
        return False, g["stage"], {"suite": None, "pass_all": False}
    return g["result"] == "Pass", DEV_REASON[g["result"]], {}


def collect(bench, models, requests, runs, gen_rows, answers, skipped, grades):
    """(rows, problems). runs is one count for every model or {model repo: count}."""
    key_field = "task_id" if bench == "coderujb" else "key"
    if isinstance(runs, int):
        runs = dict.fromkeys(models, runs)
    expected = {answer_key(m, q["id"], q["condition"], r)
                for m in models for q in requests for r in range(runs[m])}
    gen, problems = {}, []
    for g in gen_rows:
        k = answer_key(g["model"], g["id"], g["condition"], g["run"])
        if k in gen:
            problems.append(f"duplicate generation row {k}")
        gen[k] = g
    ans = {a[key_field]: a for a in answers}
    skip = {s[key_field]: s for s in skipped}
    grade = {}
    for g in grades:
        if g[key_field] in grade:
            problems.append(f"duplicate grade row {g[key_field]}")
        grade[g[key_field]] = g
    problems += [f"no generation row for {k}" for k in sorted(expected - gen.keys())]
    problems += [f"generation row outside the grid: {k}" for k in sorted(gen.keys() - expected)]
    problems += [f"grade row with no answer: {k}" for k in sorted(grade.keys() - ans.keys())]

    rows = []
    for k in sorted(gen.keys() & expected):
        g = gen[k]
        row = {"key": k, "model": g["model"], "benchmark": bench, "id": g["id"],
               "condition": g["condition"], "run": g["run"], "seed": g["seed"],
               "finish_reason": g.get("finish_reason"),
               "truncated": g.get("finish_reason") == "length",
               "prompt_tokens": g.get("prompt_tokens"), "output_tokens": g.get("output_tokens"),
               "n_images": g["n_images"], "gen_seconds": g["seconds"],
               "defines_target": None, "grade_seconds": None, "suite": None}
        if g.get("fail_reason"):
            # Claude (methodology addendum): a request_error is left out of scoring, the other
            # reasons fail before grading
            row.update(passed=None if g["fail_reason"] == "request_error" else False,
                       reason=g["fail_reason"], error=g.get("error"))
        elif g.get("error"):
            row.update(passed=False, reason="request_error", error=g["error"])
        elif k in skip:
            row.update(passed=False, reason="no_reply" if skip[k]["stage"] == "no_reply" else "no_code",
                       defines_target=False)
        elif k in ans:
            if k not in grade:
                problems.append(f"answer with no grade row: {k}")
                continue
            passed, reason, extra = grade_fields(bench, grade[k])
            row.update(passed=passed, reason=reason, defines_target=ans[k]["defines_target"],
                       grade_seconds=grade[k]["seconds"], **extra)
        else:
            problems.append(f"generation row with no answer or skipped row: {k}")
            continue
        rows.append(row)
    return rows, problems


def main(argv=None):
    ap = argparse.ArgumentParser(prog="codeimg collect", description=__doc__.split("\n")[0])
    ap.add_argument("--benchmark", required=True, choices=["coderujb", "deveval"])
    ap.add_argument("--requests", required=True)
    runs_arg = ap.add_mutually_exclusive_group()
    runs_arg.add_argument("--runs", type=int, help="default: experiment.runs")
    runs_arg.add_argument("--runs-from", help="D-study JSON with the runs per benchmark and model")
    ap.add_argument("--gen", nargs="+", required=True)
    ap.add_argument("--answers", required=True, help="dir with answers.jsonl and skipped.jsonl")
    ap.add_argument("--grades", nargs="+", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--claude", action="store_true", help="the [claude] models instead of [models]")
    args = ap.parse_args(argv)
    cfg = config.load()
    if args.claude:
        models = [m["model"] for m in config.claude_models(cfg).values()]
    else:
        models = [m["repo"] for m in cfg["models"].values()]
    runs = args.runs or cfg["experiment"]["runs"]
    if args.runs_from:
        try:
            runs = config.runs_from(args.runs_from, args.benchmark, models)
        except ValueError as e:
            sys.exit(str(e))
    rows, problems = collect(
        args.benchmark, models, read_jsonl(args.requests), runs,
        [r for p in args.gen for r in read_jsonl(p)],
        read_jsonl(f"{args.answers}/answers.jsonl"), read_jsonl(f"{args.answers}/skipped.jsonl"),
        [r for p in args.grades for r in read_jsonl(p)])
    with open(args.out, "w") as f:
        f.writelines(json.dumps(r) + "\n" for r in rows)
    print(f"{len(rows)} rows", dict(Counter(r["reason"] for r in rows)))
    for p in problems[:50]:
        print("problem:", p, file=sys.stderr)
    if problems:
        sys.exit(f"{len(problems)} problems")
