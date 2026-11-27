"""Last-block sensitivity regrade of DevEval (UFM-35), a post hoc analysis added on 2026-11-26.

usage: uv run python scripts/last_block.py answers [--out scratch/ufm35]
       uv run python scripts/last_block.py grades --grades scratch/ufm35/grades.jsonl
       uv run python scripts/last_block.py report

extract in src/codeimg/answers/deveval.py grades the first fenced block that defines the target,
and some replies revise that block further down. `answers` finds every reply on the kept DevEval
items with 2 or more blocks in which body_via_ast finds the target and builds the answer from the
last of them, with deveval.answer's fields and re-indent. When that answer differs from the
first-block one, both go to the cluster in one job (keys last__<key> and first__<key>): flips are
counted within that job, and the first-block regrade measures drift against the main run. The
answers file holds reply code and stays in scratch; results/last_block/ holds ids and verdicts.
`grades` keeps the key, result and seconds of the grader output (its tail can quote reply code).
`report` puts the last-block verdicts into the main-run rows and computes each model's DevEval
gap both ways, as analysis.py computes the main gap. The main analysis keeps the first-block rule.
"""
import argparse
import csv
import glob
import json
import os
import sys
import warnings
from collections import Counter

from codeimg import config
from codeimg.analysis import dstudy as ds
from codeimg.analysis import inputs as inp
from codeimg.analysis import reliability as rel
from codeimg.analysis import report as rpt
from codeimg.analysis import stats as st
from codeimg.answers import answer_key
from codeimg.answers import deveval as dv
from codeimg.collect import DEV_REASON

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

B = "deveval"
OUT = os.path.join(ROOT, "results", "last_block")
SCRATCH = os.path.join(ROOT, "scratch", "ufm35")
ITEMS = os.path.join(ROOT, "scratch", "ufm7", "deveval", "data.jsonl")
GENS = [os.path.expanduser("~/UFMG/ufm9-open/*/deveval/gen/*.jsonl"),
        os.path.expanduser("~/UFMG/ufm9-claude/full/deveval/gen/*.jsonl")]
ANSWER_FIELDS = ("key", "model", "id", "condition", "run", "role")
GRADE_FIELDS = ("key", "result", "seconds")
PREFIXES = ("first", "last")


def defining_bodies(reply, name):
    """The body of each fenced block in which body_via_ast finds the target, in reply order."""
    found = [dv.body_via_ast(b, name) for b in dv.FENCE.findall(reply)]
    return [b for b in found if b is not None]


def last_block(g, it, key):
    """None for a reply with fewer than 2 defining blocks, else (role, first-block answer,
    last-block answer). role: `same` when both answers are equal, `no_code` when the last body is
    empty (deveval.answer's no_body, a fail), `graded` otherwise."""
    name = g["id"].split(".")[-1]
    with warnings.catch_warnings():
        # reply code often holds invalid escapes, which ast.parse warns about
        warnings.simplefilter("ignore", SyntaxWarning)
        bodies = defining_bodies(g["reply"] or "", name)
        if len(bodies) < 2:
            return None
        first, _ = dv.answer(g, it, key)
    if first is None:
        raise ValueError(f"{key}: the first defining block has an empty body")
    if not bodies[-1].strip():
        return "no_code", first, None
    last = {**first, "completion": dv.adjust_indent(bodies[-1], it["indent"]) + "\n"}
    return ("same" if last["completion"] == first["completion"] else "graded"), first, last


def collected(full=inp.FULL, claude_full=inp.CLAUDE_FULL):
    """(open rows, Claude rows) of the DevEval collected tables."""
    return tuple(ds.read_jsonl(os.path.join(d, f"{B}.collected.jsonl"))
                 for d in (full, claude_full))


def generations(patterns=GENS):
    for pattern in patterns:
        for path in sorted(glob.glob(pattern)):
            if not path.endswith(".probe.jsonl"):
                yield from ds.read_jsonl(path)


def kind(condition):
    return "text" if condition == "text" else "image"


def answers(args):
    rows = {r["key"]: r for part in collected() for r in part}
    items = dv.load_items(ITEMS)
    gone = set(rel.excluded(B))
    seen, skipped, picked, graded = {}, Counter(), [], []
    for g in generations():
        if g.get("error") or g.get("fail_reason"):
            skipped["error"] += 1
            continue
        key = answer_key(g["model"], g["id"], g["condition"], g["run"])
        if key not in rows:
            skipped["not collected"] += 1
            continue
        if key in seen:
            if seen[key] != g["reply"]:
                raise ValueError(f"{key}: two generation rows with different replies")
            continue
        seen[key] = g["reply"]
        if g["id"] in gone or not g["reply"]:
            continue
        got = last_block(g, items[g["id"]], key)
        if got is None:
            continue
        role, first, last = got
        picked.append({"key": key, "model": g["model"], "id": g["id"],
                       "condition": g["condition"], "run": g["run"], "role": role})
        if role == "graded":
            graded += [{**first, "key": f"first__{key}"}, {**last, "key": f"last__{key}"}]
    os.makedirs(args.out, exist_ok=True)
    path = os.path.join(args.out, "answers.jsonl")
    with open(path, "w", encoding="utf-8") as f:
        f.writelines(json.dumps(a) + "\n" for a in graded)
    print(f"{path}: {len(graded)} answers to grade")
    write_csv(os.path.join(OUT, "answers.csv"), ANSWER_FIELDS, picked)
    counts = Counter((inp.name(r["model"]), kind(r["condition"]), r["role"]) for r in picked)
    for (m, k, role), n in sorted(counts.items()):
        print(f"  {m} {k} {role}: {n}")
    print(f"  in scope {len(picked)}; skipped {dict(skipped)}")


def write_csv(path, fields, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    print(path)


def read_csv(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def grades(args):
    write_csv(os.path.join(OUT, "grades.csv"), GRADE_FIELDS, ds.read_jsonl(args.grades))


def verdicts(picked, grade_rows):
    """{key: {"first": passed, "last": passed}} from the job's grades, for every graded reply.
    Stops on a result the collector does not know, a duplicate, missing or unexpected grade."""
    expected = {f"{p}__{r['key']}" for r in picked if r["role"] == "graded" for p in PREFIXES}
    got = {}
    for g in grade_rows:
        if g["result"] not in DEV_REASON:
            raise ValueError(f"{g['key']}: unknown grade result {g['result']!r}")
        if g["key"] in got:
            raise ValueError(f"{g['key']}: graded twice")
        got[g["key"]] = g["result"] == "Pass"
    unexpected = sorted(got.keys() - expected)
    if unexpected:
        raise ValueError(f"{len(unexpected)} grade(s) not in answers.csv, first {unexpected[0]}")
    missing = sorted(expected - got.keys())
    if missing:
        raise ValueError(f"{len(missing)} of {len(expected)} grade(s) missing, first {missing[0]}")
    return {r["key"]: {p: got[f"{p}__{r['key']}"] for p in PREFIXES}
            for r in picked if r["role"] == "graded"}


def with_last(rows, picked, verdict):
    """rows with `passed` under the last-block rule: the job's last-block verdict for graded
    replies, a fail for no_code ones, unchanged otherwise."""
    fails = {r["key"] for r in picked if r["role"] == "no_code"}
    return [{**r, "passed": verdict[r["key"]]["last"]} if r["key"] in verdict
            else {**r, "passed": False} if r["key"] in fails else r for r in rows]


def gap_lines(tables):
    """{model name: test_row} of the DevEval main gap (image minus text, cluster t), from
    load_benchmark or load_claude outputs, as benchmark_gaps computes `main`."""
    out = {}
    for data in tables:
        y, sizes = st.scores(data), data["conditions"][1:]
        for m in data["models"]:
            out[inp.name(m)] = st.test_row(m, st.differences(y[m], sizes, "text"), data["projects"])
    return out


def load_tables(open_rows, claude_rows, cfg):
    models, design = inp.model_set(cfg), rel.design(B)
    return [inp.load_benchmark(B, open_rows, design, models, inp.conditions(cfg),
                               inp.grid_parts(B, cfg, models)),
            inp.load_claude(B, claude_rows, design, cfg)]


def check_committed(lines, gaps_files):
    """Stops unless the first-block estimates are the committed DevEval main gaps."""
    for path in gaps_files:
        with open(path) as f:
            main = json.load(f)["benchmarks"][B]["main"]
        for r in main:
            if inp.rounded(lines[r["model"]]["est"]) != r["est"]:
                raise ValueError(f"{path}: {r['model']} est {r['est']} is not the first-block "
                                 f"est {lines[r['model']]['est']}")


def tallies(picked, verdict, rows):
    """Per model and text/image: replies in scope, graded, no_code, flips within the job, drift of
    the job's first-block verdict from the main run, and truncated replies in scope."""
    by_key = {r["key"]: r for r in rows}
    out = {}
    for r in picked:
        t = out.setdefault(inp.name(r["model"]), {}).setdefault(kind(r["condition"]), Counter())
        t["in_scope"] += 1
        t["truncated"] += bool(by_key[r["key"]]["truncated"])
        t[r["role"]] += 1
        if r["role"] == "no_code":
            t["pass_to_fail"] += bool(by_key[r["key"]]["passed"])
        if r["role"] != "graded":
            continue
        v = verdict[r["key"]]
        t["fail_to_pass"] += v["last"] and not v["first"]
        t["pass_to_fail"] += v["first"] and not v["last"]
        t["drift"] += v["first"] != bool(by_key[r["key"]]["passed"])
    return {m: {k: dict(c) for k, c in v.items()} for m, v in out.items()}


def report(args):
    cfg = config.load()
    picked = read_csv(args.answers)
    for r in picked:
        r["run"] = int(r["run"])
    verdict = verdicts(picked, read_csv(args.grades))
    open_rows, claude_rows = collected(args.full, args.claude_full)
    first = gap_lines(load_tables(open_rows, claude_rows, cfg))
    check_committed(first, args.gaps)
    last = gap_lines(load_tables(with_last(open_rows, picked, verdict),
                                 with_last(claude_rows, picked, verdict), cfg))
    rep = {"settings": {"benchmark": B, "rule": "last fenced block in which body_via_ast finds "
                        "the target, for replies with 2 or more such blocks",
                        "interval": "CR1 cluster t with G - 1 df, no multiplicity adjustment"},
           "models": {m: {"first_block": first[m], "last_block": last[m]} for m in first},
           "tallies": tallies(picked, verdict, open_rows + claude_rows)}
    inp.write_json(os.path.join(args.out, "last_block.json"), rep)
    path = os.path.join(args.out, "findings.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(findings(inp.rounded(rep)))
    print(path)


def gap_cell(r):
    c = r["cluster"]
    return f"{rpt.pp(r['est'])} {rpt.interval(c['lo'], c['hi'])}"


def findings(rep):
    t = rep["tallies"]
    total = Counter()
    for v in t.values():
        for c in v.values():
            total.update(c)
    out = ["# Last-block sensitivity (DevEval)", "",
           ("A post hoc sensitivity analysis, added on 2026-11-26 after the main gaps were seen "
            "(docs/decisions.md 2026-11-26, UFM-35); it changes nothing in methodology 3.3. The "
            "main analysis grades the first fenced block in which the target function is found. "
            "Here a reply with 2 or more such blocks is graded on the last one, with the same "
            "re-indent. Fences only match closed blocks, so in a truncated reply the last block is "
            "the last closed one."), "",
           (f"{total['in_scope']} replies on the kept items are in scope "
            f"({total['truncated']} truncated). In {total['same']} the last block gives the same "
            f"answer and the main-run verdict stands. An empty last body is scored as a fail "
            f"({total.get('no_code', 0)}). The other {total['graded']} were graded on the "
            "cluster in one job, last block and first block both, so a flip compares two grades "
            "of the same job. Drift is the job's first-block verdict against the main run's, a "
            "measure of grading noise between the two runs."), "",
           "## Gaps (image minus text, percentage points)", "",
           ("The main gap of each model, item-weighted with every run, and the same gap with the "
            "last-block verdicts; 95% project-clustered t intervals, no Holm adjustment."), ""]
    out += rpt.md_table(["Model", "First block (main)", "Last block", "Change"],
                        [[m, gap_cell(v["first_block"]), gap_cell(v["last_block"]),
                          f"{100 * (v['last_block']['est'] - v['first_block']['est']):+.2f}"]
                         for m, v in rep["models"].items()])
    out += ["## Replies", "",
            "Graded replies, flips within the job and drift from the main run, by condition type.",
            ""]
    rows = []
    for m in rep["models"]:
        for k in ("text", "image"):
            c = t.get(m, {}).get(k, {})
            rows.append([m, k, c.get("in_scope", 0), c.get("graded", 0),
                         c.get("fail_to_pass", 0), c.get("pass_to_fail", 0), c.get("drift", 0)])
    out += rpt.md_table(["Model", "Condition", "In scope", "Graded", "Fail to pass",
                         "Pass to fail", "Drift"], rows)
    return "\n".join(out).rstrip("\n") + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description="Last-block sensitivity regrade of DevEval")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("answers")
    p.add_argument("--out", default=SCRATCH)
    p = sub.add_parser("grades")
    p.add_argument("--grades", required=True, help="the grader output copied from the cluster")
    p = sub.add_parser("report")
    p.add_argument("--answers", default=os.path.join(OUT, "answers.csv"))
    p.add_argument("--grades", default=os.path.join(OUT, "grades.csv"))
    p.add_argument("--full", default=inp.FULL)
    p.add_argument("--claude-full", default=inp.CLAUDE_FULL)
    p.add_argument("--gaps", nargs=2, default=[os.path.join(inp.OUT, "gaps.json"),
                                               os.path.join(inp.ALL_OUT, "gaps.json")])
    p.add_argument("--out", default=OUT)
    args = ap.parse_args(argv)
    try:
        {"answers": answers, "grades": grades, "report": report}[args.cmd](args)
    except (ValueError, OSError) as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
