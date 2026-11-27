"""Samples for the validity audit (UFM-18) and the counts of their labels.

  hand-read     draws 10 failed DevEval answers of Claude Sonnet 5.5 per condition and writes
                <out>/hand_read.csv with empty label and note columns. --model, --input and
                --file draw another model from another collected table into another file;
                --analysed leaves out the items of manifests/excluded/deveval.txt first.
  never-passed  drops from never_passed.csv the items a Claude model passes, draws 10 of the
                rest with their gold run and 5-model failure reasons, and writes
                <out>/never_passed_check.csv and the pool counts to <out>/never_passed_pool.json.
  harness       lists the DevEval items whose reference body, run through the answer path, would
                not land as written: body_position starts at a decorator or the def line of the
                target or inside the signature, or the body has column-0 lines that
                re-indenting shifts. Writes <out>/harness_suspects.csv, with whether any of the
                7 models passes the item. It checks the main run's harness: the re-indent is
                pinned here, but the spans come from --gold, so that file must be built with
                the main run's deveval.py (before BODY_POSITION_FIX, commit bd045fc or earlier).
  summary       checks the labels of both files, and of each <out>/hand_read_*.csv, and writes
                their counts to <out>/summary.md.

Neither draw overwrites an existing file, so labels are not lost by a rerun. Only ids, row facts
and labels are written; reply text never is.

usage: uv run python scripts/audit_sample.py {hand-read,never-passed,summary} [--out DIR]
       uv run python scripts/audit_sample.py hand-read [--model M] [--input FILE] [--file NAME]
                                             [--analysed] [--out DIR]
       uv run python scripts/audit_sample.py harness --gold FILE --data FILE [--out DIR]
       FILE: the DevEval reference bodies ({id, completion} per line, read from body_position)
       and the DevEval items (namespace, indent)
"""
import argparse
import ast
import csv
import glob
import json
import os
import random
import re
import sys
import textwrap
from collections import Counter

from scipy.stats import binomtest

from codeimg import config
from codeimg.analysis import reliability as rel

ROOT = config.ROOT
OUT = os.path.join(ROOT, "results", "audit")
BENCHES = ("coderujb", "deveval")
TITLES = {"coderujb": "CoderUJB", "deveval": "DevEval"}
CONDITIONS = ("text", "image10", "image12", "image14")
SEED = 20261123
MODEL = "claude-sonnet-5-5"
CLAUDE_DEVEVAL = os.path.join("results", "claude", "full", "deveval.collected.jsonl")
N_PER_CONDITION = 10
N_ITEMS = 10
# Grader budgets of the main run: DevEval per item (src/codeimg/grade/deveval.py), CoderUJB per
# trigger test as pinned for grading (docs/decisions.md, 2026-11-06).
BUDGET = {"deveval": 180, "coderujb": 600}
NEAR_BUDGET = 0.8

HAND_LABELS = ("false_fail", "extraction", "truncated", "wrong_name", "other_function",
               "wrong_logic", "unclear")
BUG_LABELS = ("test_bug", "no_bug", "unclear")
HAND_FIELDS = ["benchmark", "model", "id", "condition", "run", "reason", "label", "note"]
CHECK_FIELDS = ["benchmark", "item", "project", "rows", "reasons", "gold_passed", "gold_seconds",
                "budget_seconds", "label", "note"]


class AuditError(Exception):
    pass


def read_jsonl(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f]


def read_csv(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_new_csv(path, fields, rows):
    if os.path.exists(path):
        raise AuditError(f"{path} exists; delete it by hand to draw again")
    with open(path, "x", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def draw_hand_read(rows, model=MODEL, n=N_PER_CONDITION, seed=SEED):
    """n failed answers of `model` per condition, with one generator across the conditions."""
    rng = random.Random(seed)
    drawn = []
    for c in CONDITIONS:
        pool = sorted((r for r in rows if r["model"] == model and r["condition"] == c
                       and not r["passed"]), key=lambda r: r["key"])
        if len(pool) < n:
            raise AuditError(f"{model} {c}: {len(pool)} failures, need {n}")
        drawn += rng.sample(pool, n)
    drawn.sort(key=lambda r: (CONDITIONS.index(r["condition"]), r["id"], r["run"]))
    return [{"benchmark": r["benchmark"], "model": r["model"], "id": r["id"],
             "condition": r["condition"], "run": r["run"], "reason": r["reason"],
             "label": "", "note": ""} for r in drawn]


def gold_by_item(bench, rows):
    """{item: (passed, seconds)} from a gold_results.jsonl. CoderUJB seconds are the slowest
    trigger test, since its budget is per test."""
    if bench == "deveval":
        return {g["namespace"]: (g["result"] == "Pass", g["seconds"]) for g in rows}
    return {g["task_id"]: (bool(g["pass_trigger"]), max(g["test_s"], default=0.0)) for g in rows}


def never_passed_pool(never, claude_rows, gold):
    """Items no model of the 7 passes, and the counts per benchmark.

    never: never_passed.csv rows; claude_rows and gold: {benchmark: ...}."""
    pool, counts = [], {}
    for b in BENCHES:
        items = [r for r in never if r["benchmark"] == b]
        claude_pass = {r["id"] for r in claude_rows[b] if r["passed"]}
        rest = [r for r in items if r["item"] not in claude_pass]
        counts[b] = {"never_passed_open": len(items),
                     "gold_passed": sum(1 for r in items if gold[b].get(r["item"], (False,))[0]),
                     "claude_passed": len(items) - len(rest),
                     "passed_by_none": len(rest)}
        pool += rest
    pool.sort(key=lambda r: (r["benchmark"], r["item"]))
    return pool, counts


def draw_never_passed(pool, collected, gold, n=N_ITEMS, seed=SEED):
    """n items of the pool with the 5-model failure reasons and the gold run of each."""
    if len(pool) < n:
        raise AuditError(f"never-passed pool has {len(pool)} items, need {n}")
    out = []
    for r in sorted(random.Random(seed).sample(pool, n), key=lambda r: (r["benchmark"], r["item"])):
        b, item = r["benchmark"], r["item"]
        reasons = Counter(x["reason"] for x in collected[b] if x["id"] == item)
        if not reasons:
            raise AuditError(f"{b} {item}: no collected rows")
        if item not in gold[b]:
            raise AuditError(f"{b} {item}: no gold record")
        passed, seconds = gold[b][item]
        out.append({"benchmark": b, "item": item, "project": r["project"],
                    "rows": sum(reasons.values()),
                    "reasons": ";".join(f"{k}:{v}" for k, v in sorted(reasons.items())),
                    "gold_passed": passed, "gold_seconds": round(seconds, 1),
                    "budget_seconds": BUDGET[b], "label": "", "note": ""})
    return out


def is_body(code):
    try:
        ast.parse("async def _f():\n" + textwrap.indent(textwrap.dedent(code), "    "))
    except SyntaxError:
        return False
    return True


def main_run_reindent(code, new_indent):
    # pass_k.py's adjust_indent, which the main run used: this check describes the main run
    return textwrap.indent(textwrap.dedent(code), " " * new_indent)


def harness_suspects(gold, items):
    """{item: pattern} for the reference bodies the answer path would not splice back as written.

    gold: {item: body read from body_position}; items: {item: {"indent": ...}}. "offset": the span
    starts at a decorator or the def line of the target, or is not a function body at all (it
    starts inside the signature). "reindent": re-indenting moves column-0 lines, such as those of
    a triple-quoted string."""
    out = {}
    for i in sorted(gold):
        body, name = gold[i], i.split(".")[-1]
        first = next((x for x in body.splitlines() if x.strip()), "")
        if re.match(r"\s*(@|(async\s+)?def\s+" + re.escape(name) + r"\b)", first) \
                or not is_body(body):
            out[i] = "offset"
        elif main_run_reindent(body, int(items[i]["indent"])).splitlines() != body.splitlines() \
                and any(x and not x[0].isspace() for x in body.splitlines()):
            out[i] = "reindent"
    return out


def check_labels(rows, allowed, name):
    for i, r in enumerate(rows, start=2):
        if r["label"] not in allowed:
            raise AuditError(f"{name} line {i}: label {r['label']!r} not in {', '.join(allowed)}")


def excluded_items():
    """{benchmark: (count, date)} of the items manifests/excluded/ leaves out of the analysis,
    read through src/codeimg/analysis/reliability.py so the ids are checked against the item
    lists."""
    return {b: (len(rel.excluded(b)), rel.EXCLUDED_ON[b]) for b in BENCHES}


def base_note(excluded):
    """excluded: {benchmark: (count, date of its docs/decisions.md entry)}."""
    parts = [f"{n} {TITLES[b]} ({day})" for b, (n, day) in (excluded or {}).items() if n]
    tail = (f", including the {' and '.join(parts)} items excluded from the analysis in "
            "docs/decisions.md" if parts else "")
    return f"Base: every item of the main run{tail}."


def label_table(hand):
    lines = ["| Label | " + " | ".join(CONDITIONS) + " | All |",
             "|---|" + "---|" * (len(CONDITIONS) + 1)]
    for lab in HAND_LABELS:
        per = [sum(1 for r in hand if r["condition"] == c and r["label"] == lab) for c in CONDITIONS]
        lines.append(f"| {lab} | " + " | ".join(map(str, per)) + f" | {sum(per)} |")
    return lines


def false_fails(hand):
    k, n = sum(1 for r in hand if r["label"] == "false_fail"), len(hand)
    share = ""
    if n:
        ci = binomtest(k, n).proportion_ci(method="exact")
        share = f", {100 * k / n:.1f}% (exact 95% CI {100 * ci.low:.1f}% to {100 * ci.high:.1f}%)"
    return f"{k} of {n}{share}"


def extra_hand_read(name, rows, hand, excluded_ids, n_items):
    """Section for another model's hand read, drawn from the analysed items, with the Sonnet read
    cut to the same base. The Sonnet subset is post hoc: it shares the base, not the items."""
    if not rows:
        raise AuditError(f"{name}: no rows")
    check_labels(rows, HAND_LABELS, name)
    model = rows[0]["model"]
    same = [r for r in hand if r["id"] not in excluded_ids]
    sample = (f"Failed DevEval answers of {model}, {N_PER_CONDITION} per condition, seed {SEED}, "
              f"drawn from the {n_items} analysed items (the main run's items minus the "
              f"{len(excluded_ids)} in manifests/excluded/deveval.txt). Labels by Claude Code, "
              "not checked by a person.")
    sonnet = (f"On the same {n_items}-item base, {MODEL} (its hand read minus the "
              f"{len(hand) - len(same)} answers on excluded items): {false_fails(same)}.")
    return (["", f"## Hand read: {model}", "", sample, ""] + label_table(rows)
            + ["", f"False fails: {false_fails(rows)}.", "", sonnet])


def summary(hand, check, counts, harness=(), excluded=None, extra=(), excluded_ids=(),
            n_items=None):
    """Markdown with the label counts. The false-fail share is pooled over every drawn answer,
    unclear included, since 10 per condition is too few for a rate.

    extra: [(file name, rows)] of other models' hand reads, each drawn from the n_items analysed
    DevEval items, that is without excluded_ids."""
    check_labels(hand, HAND_LABELS, "hand_read.csv")
    check_labels(check, BUG_LABELS, "never_passed_check.csv")
    files = ", ".join(["hand_read.csv"] + [name for name, _ in extra] + ["never_passed_check.csv"])
    head = (f"Generated by `uv run python scripts/audit_sample.py summary` from {files} "
            "and never_passed_pool.json; edit the labels, not this file.")
    base = base_note(excluded)
    if extra:
        base += " The hand reads of other models below give their own base."
    sample = (f"Failed DevEval answers of {MODEL}, {N_PER_CONDITION} per condition, seed {SEED}. "
              "Labels by Claude Code, not checked by a person.")
    lines = (["# Validity audit samples", "", head, "", base, "", "## Hand read", "", sample, ""]
             + label_table(hand) + ["", f"False fails: {false_fails(hand)}."])
    for name, rows in extra:
        lines += extra_hand_read(name, rows, hand, set(excluded_ids), n_items)
    pool_head = ("| Benchmark | Never passed by the 5 open models | Gold passes "
                 "| A Claude model passes | Passed by none of the 7 |")
    lines += ["", "## Items no model passes", "", pool_head, "|---|---|---|---|---|"]
    for b in BENCHES:
        c = counts[b]
        lines.append(f"| {b} | {c['never_passed_open']} | {c['gold_passed']} | "
                     f"{c['claude_passed']} | {c['passed_by_none']} |")
    desk = (f"Desk check of {len(check)} items drawn from those no model passes, seed {SEED} "
            f"(test bug: gold fails, gold at {NEAR_BUDGET:.0%} or more of the budget, the answer "
            "path cannot splice an answer in, or the tests need what the prompt and context do "
            "not give):")
    lines += ["", desk, "", "| Label | Items |", "|---|---|"]
    lines += [f"| {lab} | {sum(1 for r in check if r['label'] == lab)} |" for lab in BUG_LABELS]
    if harness:
        by = Counter((r["pattern"], r["passed_by_none"] == "True") for r in harness)
        lines += ["", "## DevEval harness suspects", "",
                  ("Reference bodies the answer path would not splice back as written "
                   "(harness_suspects.csv):"), "",
                  "| Pattern | Items | Of them passed by none of the 7 |", "|---|---|---|"]
        for pat in ("offset", "reindent"):
            n = by[(pat, True)] + by[(pat, False)]
            lines.append(f"| {pat} | {n} | {by[(pat, True)]} |")
    return "\n".join(lines) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("mode", choices=("hand-read", "never-passed", "harness", "summary"))
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--gold", help="harness: DevEval reference bodies, jsonl")
    ap.add_argument("--data", help="harness: DevEval items, jsonl")
    ap.add_argument("--model", help=f"hand-read: model to draw (default {MODEL})")
    ap.add_argument("--input", help="hand-read: collected DevEval table, relative to the repo "
                                    f"(default {CLAUDE_DEVEVAL})")
    ap.add_argument("--file", help="hand-read: output file name in --out (default hand_read.csv)")
    ap.add_argument("--analysed", action="store_true",
                    help="hand-read: leave out the items of manifests/excluded/deveval.txt")
    args = ap.parse_args(argv)
    if args.mode != "hand-read" and (args.analysed or any(
            v is not None for v in (args.model, args.input, args.file))):
        sys.exit("audit_sample: --model, --input, --file and --analysed are only for hand-read")
    os.makedirs(args.out, exist_ok=True)
    claude = {b: read_jsonl(os.path.join(ROOT, "results", "claude", "full", f"{b}.collected.jsonl"))
              for b in BENCHES} if args.mode == "never-passed" else None
    pool_path = os.path.join(args.out, "never_passed_pool.json")
    try:
        if args.mode == "hand-read":
            rows = read_jsonl(os.path.join(ROOT, args.input or CLAUDE_DEVEVAL))
            if args.analysed:
                drop = set(rel.excluded("deveval"))
                rows = [r for r in rows if r["id"] not in drop]
            rows = draw_hand_read(rows, args.model or MODEL)
            write_new_csv(os.path.join(args.out, args.file or "hand_read.csv"), HAND_FIELDS, rows)
            print(len(rows), "answers drawn")
        elif args.mode == "never-passed":
            gold = {b: gold_by_item(b, read_jsonl(os.path.join(ROOT, "benchmarks", b, "results",
                                                               "gold_results.jsonl")))
                    for b in BENCHES}
            never = read_csv(os.path.join(ROOT, "results", "analysis", "never_passed.csv"))
            pool, counts = never_passed_pool(never, claude, gold)
            collected = {b: read_jsonl(os.path.join(ROOT, "results", "full", f"{b}.collected.jsonl"))
                         for b in BENCHES}
            rows = draw_never_passed(pool, collected, gold)
            write_new_csv(os.path.join(args.out, "never_passed_check.csv"), CHECK_FIELDS, rows)
            with open(pool_path, "w") as f:
                json.dump({"seed": SEED, "counts": counts}, f, indent=1)
            print(counts)
        elif args.mode == "harness":
            if not (args.gold and args.data):
                raise AuditError("harness needs --gold and --data")
            run_ids = {r["id"] for r in read_jsonl(os.path.join(ROOT, "results", "full",
                                                               "deveval.collected.jsonl"))}
            gold = {g["id"]: g["completion"] for g in read_jsonl(args.gold) if g["id"] in run_ids}
            if len(gold) != len(run_ids):
                raise AuditError(f"{len(run_ids) - len(gold)} DevEval items have no reference body")
            items = {d["namespace"]: d for d in read_jsonl(args.data)}
            passed = {r["id"] for path in (("full",), ("claude", "full"))
                      for r in read_jsonl(os.path.join(ROOT, "results", *path,
                                                       "deveval.collected.jsonl"))
                      if r["passed"]}
            rows = [{"benchmark": "deveval", "item": i, "pattern": p,
                     "passed_by_none": i not in passed}
                    for i, p in harness_suspects(gold, items).items()]
            with open(os.path.join(args.out, "harness_suspects.csv"), "w", newline="") as f:
                w = csv.DictWriter(f, fieldnames=["benchmark", "item", "pattern", "passed_by_none"])
                w.writeheader()
                w.writerows(rows)
            print(len(rows), "suspects,", sum(r["passed_by_none"] for r in rows), "passed by none")
        else:
            with open(pool_path) as f:
                counts = json.load(f)["counts"]
            harness_path = os.path.join(args.out, "harness_suspects.csv")
            harness = read_csv(harness_path) if os.path.exists(harness_path) else ()
            extra = [(os.path.basename(p), read_csv(p))
                     for p in sorted(glob.glob(os.path.join(args.out, "hand_read_*.csv")))]
            ids = rel.excluded("deveval")
            text = summary(read_csv(os.path.join(args.out, "hand_read.csv")),
                           read_csv(os.path.join(args.out, "never_passed_check.csv")), counts,
                           harness, excluded_items(), extra, ids,
                           len(rel.design("deveval")) - len(ids))
            with open(os.path.join(args.out, "summary.md"), "w") as f:
                f.write(text)
            print(text)
    except AuditError as e:
        sys.exit(f"audit_sample: {e}")


if __name__ == "__main__":
    main()
