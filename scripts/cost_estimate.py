"""GPU and CPU time for block 1 and the full study, projected from the smoke run.

  python scripts/cost_estimate.py --run /snfs2/carlosleao/ufm9/smoke --out results/smoke/cost

Writes cost.json and cost.md. Every figure rests on the smoke run's 20 answers per model and
benchmark, so read the projections as order of magnitude, not as a budget.

Generation time per answer is the row's wall seconds divided by the job's concurrency: requests
run concurrency-at-a-time, so that is the GPU time each answer costs. It is cross-checked against
the job's ready-to-end wall time over its answer count.
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
# items per benchmark in each phase (docs/methodology.md 3.1)
ITEMS = {"block1": {"coderujb": 40, "deveval": 200}, "full": {"coderujb": 136, "deveval": 859}}


def read_jsonl(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f]


def metas(run, b, m):
    d = f"{run}/{b}/gen"
    out = []
    for f in sorted(os.listdir(d)):
        if f.startswith(f"{m}.jsonl.meta."):
            with open(f"{d}/{f}") as fh:
                out.append(json.load(fh))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--out", required=True, help="path prefix for .json and .md")
    args = ap.parse_args()
    cfg = config.load()
    conds = ["text"] + [f"image{px}" for px in cfg["experiment"]["sizes"]]
    runs = cfg["experiment"]["runs"]
    conc = cfg["experiment"]["concurrency"]
    models = {}
    for m in cfg["models"]:
        per = defaultdict(list)
        tokens = defaultdict(list)
        per_page = defaultdict(list)
        wall_check = []
        load = None
        for b in BENCHES:
            rows = read_jsonl(f"{args.run}/{b}/gen/{m}.jsonl")
            probe = {r["id"]: r["text_part_tokens"]
                     for r in read_jsonl(f"{args.run}/{b}/gen/{m}.jsonl.probe.jsonl")}
            for r in rows:
                if r.get("error"):
                    continue
                per[(b, r["condition"])].append(r["seconds"] / conc)
                tokens[r["condition"]].append(r["prompt_tokens"])
                if r["n_images"]:
                    per_page[r["condition"]].append((r["prompt_tokens"] - probe[r["id"]]) / r["n_images"])
            for meta in metas(args.run, b, m):
                if meta.get("server_ready") and meta.get("job_start") and load is None:
                    load = float(meta["server_ready"]) - float(meta["job_start"])
                wall_check.append((meta["end"] - meta["start"]) / max(1, len(rows)))
        sec = {f"{b} {c}": statistics.mean(per[(b, c)]) for b in BENCHES for c in conds if per[(b, c)]}
        proj = {}
        for phase, items in ITEMS.items():
            s = sum(items[b] * runs * statistics.mean(per[(b, c)])
                    for b in BENCHES for c in conds if per[(b, c)])
            proj[phase] = round((s + (load or 0)) / 3600, 2)
        models[m] = {
            "load_seconds": load,
            "gen_seconds_per_answer": {k: round(v, 2) for k, v in sec.items()},
            "wall_seconds_per_answer_check": [round(w, 2) for w in wall_check],
            "median_prompt_tokens": {c: statistics.median(tokens[c]) for c in conds if tokens[c]},
            "median_image_tokens_per_page": {c: round(statistics.median(per_page[c]))
                                             for c in conds if per_page[c]},
            "gpu_hours": proj,
        }
    grading = {}
    for b in BENCHES:
        # the gold grading rows (same grader, same items) also count, so a benchmark where every
        # smoke reply was skipped still has a timing
        secs = [r["seconds"] for p in (f"{args.run}/{b}/grades.jsonl", f"{args.run}/{b}/gold/grades.jsonl")
                if os.path.exists(p) for r in read_jsonl(p)]
        mean = statistics.mean(secs) if secs else None
        n = len(conds) * runs * len(cfg["models"])
        grading[b] = {"answers_graded": len(secs),
                      "cpu_seconds_per_answer": round(mean, 1) if mean else None,
                      **{f"cpu_hours_{p}": round(items[b] * n * mean / 3600, 1) if mean else None
                         for p, items in ITEMS.items()}}
    out = {"basis": "smoke run, 20 answers per model and benchmark, run 0 only", "concurrency": conc,
           "models": models, "grading": grading,
           "gpu_hours_total": {p: round(sum(v["gpu_hours"][p] for v in models.values()), 1) for p in ITEMS}}
    with open(args.out + ".json", "w") as f:
        json.dump(out, f, indent=1)
    lines = ["| model | load (min) | GPU h block 1 | GPU h full |", "|---|---|---|---|"]
    for m, v in models.items():
        lines.append(f"| {m} | {(v['load_seconds'] or 0) / 60:.1f} | {v['gpu_hours']['block1']} | {v['gpu_hours']['full']} |")
    lines.append(f"| total | | {out['gpu_hours_total']['block1']} | {out['gpu_hours_total']['full']} |")
    lines += ["", "| benchmark | CPU s per answer | CPU h block 1 | CPU h full |", "|---|---|---|---|"]
    for b, v in grading.items():
        lines.append(f"| {b} | {v['cpu_seconds_per_answer']} | {v['cpu_hours_block1']} | {v['cpu_hours_full']} |")
    lines += ["", "From the smoke run: 20 answers per model and benchmark, so treat these as order of magnitude."]
    with open(args.out + ".md", "w") as f:
        f.write("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
