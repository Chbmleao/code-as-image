"""Writes the inputs of analysis/glmm_check.R, so R only reads CSV.

  uv run python scripts/glmm_cells.py [--block results/block1] [--manifests manifests/block1]
      [--out scratch/glmm]

For each benchmark it writes <out>/design_<b>.csv (item, project, n: every in-range item of the
main run, 3 runs for block-1 items and 2 for the others, the Nov 10 decision) and
<out>/block1_<b>_cells.csv (model, item, condition, project, k, n: the block-1 passes per cell).
Item ids come from the final id lists; the project is the CoderUJB project or the DevEval
repository (dstudy.CLUSTERS). Block-1 rows are validated by dstudy.cells.
"""
import argparse
import csv
import os
import sys

from codeimg import config
from codeimg.analysis import dstudy as ds

ROOT = config.ROOT

ID_LISTS = {"coderujb": "benchmarks/coderujb/results/final_ids.txt",
            "deveval": "benchmarks/deveval/results/inrange_ids.txt"}
BLOCK_RUNS = 3
MAIN_RUNS = 2


def design(benchmark, ids, block_ids, labels):
    """One (item, project, n) row per item; n is 3 for block-1 items, else 2."""
    if len(set(ids)) != len(ids):
        raise ValueError(f"{benchmark}: duplicated item id")
    ds.clusters(benchmark, ids, labels)
    block = set(block_ids)
    if not block <= set(ids):
        raise ValueError(f"{benchmark}: manifest id not in the item list")
    return [(i, labels[i], BLOCK_RUNS if i in block else MAIN_RUNS) for i in ids]


def block_cells(benchmark, rows, ids, labels):
    """One (model, item, condition, project, k, n) row per block-1 cell."""
    data = ds.cells(benchmark, rows, ids)
    ds.clusters(benchmark, ids, labels)
    return [(m, i, c, labels[i], sum(data[m][j][q]), len(data[m][j][q]))
            for m in ds.NAMES for j, i in enumerate(ids) for q, c in enumerate(ds.CONDITIONS)]


def write_csv(path, header, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Design and block-1 cell CSVs for the GLMM check")
    ap.add_argument("--block", default="results/block1")
    ap.add_argument("--manifests", default="manifests/block1")
    ap.add_argument("--out", default="scratch/glmm")
    args = ap.parse_args(argv)
    try:
        for b in ds.BENCHES:
            path, key, label = ds.CLUSTERS[b]
            labels = {r[key]: r[label] for r in ds.read_jsonl(os.path.join(ROOT, path))}
            ids = ds.read_ids(os.path.join(ROOT, ID_LISTS[b]))
            block_ids = ds.read_ids(f"{args.manifests}/{b}.txt")
            rows = design(b, ids, block_ids, labels)
            out = os.path.join(args.out, f"design_{b}.csv")
            write_csv(out, ("item", "project", "n"), rows)
            print(f"{out}: {len(rows)} items")
            rows = block_cells(b, ds.read_jsonl(f"{args.block}/{b}.collected.jsonl"),
                               block_ids, labels)
            out = os.path.join(args.out, f"block1_{b}_cells.csv")
            write_csv(out, ("model", "item", "condition", "project", "k", "n"), rows)
            print(f"{out}: {len(rows)} cells")
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(1)
