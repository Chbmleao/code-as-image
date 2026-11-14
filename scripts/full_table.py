"""The full answer table (block 1 plus the rest) and its checks, and the re-score of a sample.

  build    concatenates block 1's and the rest's collected.jsonl per benchmark into
           <out>/<benchmark>.collected.jsonl and writes <out>/checks.json. The expected grid is
           every model x condition over the block-1 manifest at experiment.runs runs plus the rest
           manifest at the D-study's runs per model. Exits nonzero on a missing or extra key, a
           duplicate key, a null `passed` or a row whose seed is not its run.
  sample   draws the re-score keys from the full table, among answers that were graded.
  rescore  compares grade rows for those keys, regraded on the cluster from the saved replies,
           with the table's `passed` (writes <out>/rescore.json). The table is never changed.

usage: uv run python scripts/full_table.py build --rest DIR [--block1 DIR] [--out DIR]
       uv run python scripts/full_table.py sample [--out DIR]
       uv run python scripts/full_table.py rescore --grades FILE... [--extract-differs FILE] [--out DIR]
"""
import argparse
import json
import os
import random
import sys
from collections import Counter, defaultdict

from codeimg import config
from codeimg.answers import answer_key, read_jsonl
from codeimg.collect import grade_fields

BENCHES = ("coderujb", "deveval")
OUT = os.path.join(config.ROOT, "results", "full")
DSTUDY = os.path.join(config.ROOT, "results", "block1", "dstudy.json")
SAMPLE = {"deveval": 50, "coderujb": 20}
SAMPLE_SEED = 20261111
NOT_GRADED = {"request_error", "no_reply", "no_code"}


def read_ids(path):
    with open(path) as f:
        return f.read().split()


def expected_keys(models, conditions, parts):
    """parts: [(item ids, {model: runs})]."""
    return {answer_key(m, i, c, r)
            for ids, runs in parts for m in models for i in ids for c in conditions
            for r in range(runs[m])}


def check(rows, expected):
    """Problems and summaries for one benchmark's table."""
    keys = Counter(r["key"] for r in rows)
    by = defaultdict(lambda: defaultdict(Counter))
    for r in rows:
        cell = by[r["model"]][r["condition"]]
        cell["rows"] += 1
        cell["passed"] += r["passed"] is True
        cell["request_errors"] += r["reason"] == "request_error"
        cell["truncated"] += bool(r["truncated"])
    out = {
        "rows": len(rows), "expected": len(expected),
        "missing": sorted(expected - keys.keys()), "extra": sorted(keys.keys() - expected),
        "duplicates": sorted(k for k, n in keys.items() if n > 1),
        "null_passed": sorted(r["key"] for r in rows if r["passed"] is None),
        "seed_not_run": sorted(r["key"] for r in rows if r["seed"] != r["run"]),
        "per_run": dict(sorted(Counter(f"{r['model']}|{r['condition']}|r{r['run']}"
                                       for r in rows).items())),
        "cells": {m: {c: {**v, "pass_rate": round(v["passed"] / v["rows"], 4)}
                      for c, v in sorted(cs.items())} for m, cs in sorted(by.items())},
    }
    out["ok"] = not any(out[k] for k in ("missing", "extra", "duplicates", "null_passed",
                                         "seed_not_run"))
    return out


def build(args, cfg):
    models = [m["repo"] for m in cfg["models"].values()]
    conditions = ["text"] + [f"image{s}" for s in cfg["experiment"]["sizes"]]
    manifests = os.path.join(config.ROOT, "manifests")
    checks = {}
    for b in BENCHES:
        rows = (read_jsonl(os.path.join(args.block1, f"{b}.collected.jsonl"))
                + read_jsonl(os.path.join(args.rest, f"{b}.collected.jsonl")))
        expected = expected_keys(models, conditions, [
            (read_ids(f"{manifests}/block1/{b}.txt"),
             dict.fromkeys(models, cfg["experiment"]["runs"])),
            (read_ids(f"{manifests}/rest/{b}.txt"), config.runs_from(args.dstudy, b, models))])
        checks[b] = check(rows, expected)
        with open(os.path.join(args.out, f"{b}.collected.jsonl"), "w") as f:
            f.writelines(json.dumps(r) + "\n" for r in sorted(rows, key=lambda r: r["key"]))
        c = checks[b]
        print(b, c["rows"], "rows, expected", c["expected"], "ok" if c["ok"] else "FAILED",
              {k: len(c[k]) for k in ("missing", "extra", "duplicates", "null_passed",
                                      "seed_not_run")})
    with open(os.path.join(args.out, "checks.json"), "w") as f:
        json.dump(checks, f, indent=1)
    if not all(c["ok"] for c in checks.values()):
        sys.exit("full table failed its checks")


def sample(rows_by_bench, n_by_bench, seed):
    """{benchmark: sorted keys}, drawn among graded answers."""
    rng = random.Random(seed)
    return {b: sorted(rng.sample(sorted(r["key"] for r in rows_by_bench[b]
                                        if r["reason"] not in NOT_GRADED), n_by_bench[b]))
            for b in BENCHES}


def rescore(rows_by_bench, keys_by_bench, grades, extract_differs):
    """Regraded verdicts against the table. grades: grader rows from both benchmarks."""
    out = {}
    for b in BENCHES:
        table = {r["key"]: r for r in rows_by_bench[b]}
        field = "task_id" if b == "coderujb" else "key"
        regraded = {g[field]: g for g in grades if field in g and g[field] in table}
        mismatches, missing = [], []
        for k in keys_by_bench[b]:
            if k not in regraded:
                missing.append(k)
                continue
            passed, reason, _ = grade_fields(b, regraded[k])
            if passed != table[k]["passed"]:
                mismatches.append({"key": k, "table": table[k]["reason"], "regraded": reason})
        out[b] = {"sampled": len(keys_by_bench[b]), "regraded": len(keys_by_bench[b]) - len(missing),
                  "missing": missing, "verdict_mismatches": mismatches,
                  "extraction_differs": sorted(set(extract_differs) & set(keys_by_bench[b]))}
    return out


def load_table(out_dir):
    return {b: read_jsonl(os.path.join(out_dir, f"{b}.collected.jsonl")) for b in BENCHES}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="mode", required=True)
    b = sub.add_parser("build")
    b.add_argument("--rest", required=True, help="dir with the rest's <benchmark>.collected.jsonl")
    b.add_argument("--block1", default=os.path.join(config.ROOT, "results", "block1"))
    b.add_argument("--dstudy", default=DSTUDY)
    s = sub.add_parser("sample")
    r = sub.add_parser("rescore")
    r.add_argument("--grades", nargs="+", required=True)
    r.add_argument("--extract-differs", help="keys whose re-extracted answer differs, one per line")
    for p in (b, s, r):
        p.add_argument("--out", default=OUT)
    args = ap.parse_args(argv)
    os.makedirs(args.out, exist_ok=True)
    keys_path = os.path.join(args.out, "rescore_keys.json")
    if args.mode == "build":
        build(args, config.load())
    elif args.mode == "sample":
        keys = sample(load_table(args.out), SAMPLE, SAMPLE_SEED)
        with open(keys_path, "w") as f:
            json.dump({"seed": SAMPLE_SEED, "keys": keys}, f, indent=1)
        print({b: len(k) for b, k in keys.items()})
    else:
        with open(keys_path) as f:
            keys = json.load(f)["keys"]
        grades = [g for p in args.grades for g in read_jsonl(p)]
        differs = read_ids(args.extract_differs) if args.extract_differs else []
        result = rescore(load_table(args.out), keys, grades, differs)
        with open(os.path.join(args.out, "rescore.json"), "w") as f:
            json.dump(result, f, indent=1)
        for bench, v in result.items():
            print(bench, v["regraded"], "of", v["sampled"], "regraded,",
                  len(v["verdict_mismatches"]), "verdicts differ,",
                  len(v["extraction_differs"]), "extractions differ")


if __name__ == "__main__":
    main()
