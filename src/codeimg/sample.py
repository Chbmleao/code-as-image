"""Block-1 and smoke manifests, from the committed benchmark results and a fixed seed.

Block 1 (docs/methodology.md 3.1): DevEval items stratified by Qwen3.5 prompt-token bucket and
CoderUJB items by project, both in proportion to the set with largest-remainder rounding. The smoke
sample takes, per benchmark, the item with the most pages at the largest size (from `prompts
--count-only` over the whole benchmark), so the image limit is exercised, plus items drawn from
block 1 without it.

Writes <out>/block1/{coderujb,deveval}.txt and <out>/smoke/{coderujb,deveval}.txt, sorted ids.
"""
import argparse
import json
import os
import random
from collections import defaultdict

from codeimg import config

RESULTS = os.path.join(config.ROOT, "benchmarks", "{}", "results", "{}")


def largest_remainder(sizes, n):
    """Allocate n over strata in proportion to sizes; ties go to the first stratum by key."""
    total = sum(sizes.values())
    quota = {k: n * v / total for k, v in sizes.items()}
    alloc = {k: int(q) for k, q in quota.items()}
    order = sorted(sizes, key=lambda k: (-(quota[k] - alloc[k]), k))
    for k in order[:n - sum(alloc.values())]:
        alloc[k] += 1
    return alloc


def stratified(strata, n, rng):
    alloc = largest_remainder({k: len(v) for k, v in strata.items()}, n)
    picked = []
    for k in sorted(strata):
        picked += rng.sample(sorted(strata[k]), alloc[k])
    return sorted(picked), alloc


def read_lines(path):
    with open(path) as f:
        return f.read().split()


def read_jsonl(path):
    with open(path) as f:
        return [json.loads(line) for line in f]


def deveval_strata(buckets):
    ids = read_lines(RESULTS.format("deveval", "inrange_ids.txt"))
    tokens = {r["id"]: r["qwen35"] for r in read_jsonl(RESULTS.format("deveval", "prompt_counts.jsonl"))}
    strata = defaultdict(list)
    for i in ids:
        for lo, hi in buckets:
            if lo <= tokens[i] < hi:
                strata[f"{lo}-{hi}"].append(i)
    assert sum(map(len, strata.values())) == len(ids), "an in-range item fell outside the buckets"
    return strata


def coderujb_strata():
    ids = set(read_lines(RESULTS.format("coderujb", "final_ids.txt")))
    strata = defaultdict(list)
    for r in read_jsonl(RESULTS.format("coderujb", "gold_results.jsonl")):
        if r["task_id"] in ids:
            strata[r["project"]].append(r["task_id"])
    return strata


def smoke(block, pages, n, rng):
    """pages: rows from `prompts --count-only` for the whole benchmark."""
    largest = max(k for k in pages[0] if k.startswith("image"))
    top = min(pages, key=lambda r: (-r[largest], r["id"]))["id"]
    rest = sorted(set(block) - {top})
    return sorted([top] + rng.sample(rest, n - 1))


def write(path, ids):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write("\n".join(ids) + "\n")


def build(cfg, pages_by_bench):
    """Manifests as {(sample, benchmark): ids}. One generator, consumed in a fixed order."""
    s = cfg["sample"]
    rng = random.Random(cfg["experiment"]["seed"])
    dev, _ = stratified(deveval_strata(s["deveval_buckets"]), s["deveval_n"], rng)
    ujb, _ = stratified(coderujb_strata(), s["coderujb_n"], rng)
    out = {("block1", "deveval"): dev, ("block1", "coderujb"): ujb}
    for bench, block in (("deveval", dev), ("coderujb", ujb)):
        out[("smoke", bench)] = smoke(block, pages_by_bench[bench], s["smoke_n"], rng)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(prog="codeimg sample", description=__doc__.split("\n")[0])
    ap.add_argument("--pages-deveval", required=True, help="prompts --count-only output, all items")
    ap.add_argument("--pages-coderujb", required=True)
    ap.add_argument("--out", default=os.path.join(config.ROOT, "manifests"))
    args = ap.parse_args(argv)
    pages = {"deveval": read_jsonl(args.pages_deveval), "coderujb": read_jsonl(args.pages_coderujb)}
    for (sample, bench), ids in build(config.load(), pages).items():
        write(os.path.join(args.out, sample, f"{bench}.txt"), ids)
        print(sample, bench, len(ids))
