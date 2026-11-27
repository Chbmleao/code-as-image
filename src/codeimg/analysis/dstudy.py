"""Sizes the runs for the rest of the main run from the block-1 answers.

For each model and benchmark it estimates the two components of the size-averaged gap delta_mb
(item:condition A and run noise B, moment estimators on the balanced block), projects the gap's
standard error with 1, 2 and 3 runs and applies the Nov 8 rule: 2 runs when SE(2) / SE(3) is at
most 1.10, else 3. Intervals are percentile bootstraps over items and over projects (CoderUJB) or
repositories (DevEval).

  uv run python scripts/dstudy.py [--block results/block1] [--manifests manifests/block1]
      [--out results/block1]

Writes <out>/dstudy.json, whose rows[].runs the rest of the run reads, and <out>/dstudy.md.
"""
import argparse
import json
import math
import os
import random
import sys
import textwrap
from collections import defaultdict

from codeimg import config

ROOT = config.ROOT
BENCHES = ("coderujb", "deveval")
TITLES = {"coderujb": "CoderUJB", "deveval": "DevEval"}
CONDITIONS = ("text", "image10", "image12", "image14")
RUNS = 3
# row order of every table, as in results/block1/findings.md
NAMES = {
    "cyankiwi/Qwen3.5-27B-AWQ-4bit": "Qwen3.5 27B",
    "google/gemma-4-12B-it": "Gemma 4 12B",
    "jeffcookio/Mistral-Small-3.2-24B-Instruct-2506-awq-sym": "Mistral Small 3.2 24B",
    "Qwen/Qwen3.5-9B": "Qwen3.5 9B",
    "Qwen/Qwen2.5-VL-7B-Instruct": "Qwen2.5-VL 7B",
}
# item id -> cluster: the CoderUJB project, the DevEval repository
CLUSTERS = {"coderujb": ("benchmarks/coderujb/results/gold_results.jsonl", "task_id", "project"),
            "deveval": ("benchmarks/deveval/results/gold_results.jsonl", "namespace", "project_path")}
CLUSTER_WORD = {"coderujb": "projects", "deveval": "repositories"}
MARGIN = 1.1
SEED = 20261110
N_BOOT = 2000


def read_jsonl(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f]


def read_ids(path):
    with open(path, encoding="utf-8") as f:
        return f.read().split()


def cells(benchmark, rows, ids):
    """Per model, each manifest item's passes as one [run 0, 1, 2] list per condition.

    The moment estimators are exact only on balanced data, so anything else raises ValueError.
    """
    got = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    for r in rows:
        got[r["model"]][r["id"]][r["condition"]].append((r["run"], int(r["passed"])))
    manifest = set(ids)
    for i in sorted(manifest):
        if ids.count(i) > 1:
            raise ValueError(f"{benchmark} {i}: duplicated in the manifest")
    out = {}
    for m in sorted(set(got) | set(NAMES)):
        if m not in NAMES:
            raise ValueError(f"{benchmark}: unknown model {m}")
        for i in sorted(manifest | set(got[m])):
            if i not in manifest:
                raise ValueError(f"{benchmark} {m} {i}: id not in the manifest")
            if i not in got[m]:
                raise ValueError(f"{benchmark} {m} {i}: manifest item with no rows")
            for c in sorted(set(CONDITIONS) | set(got[m][i])):
                if c not in CONDITIONS:
                    raise ValueError(f"{benchmark} {m} {i} {c}: unknown condition")
                runs = sorted(run for run, _ in got[m][i][c])
                if not runs:
                    raise ValueError(f"{benchmark} {m} {i} {c}: missing condition")
                if runs != list(range(RUNS)):
                    raise ValueError(f"{benchmark} {m} {i} {c}: runs {runs}, "
                                     f"expected {list(range(RUNS))}")
        out[m] = [[[y for _, y in sorted(got[m][i][c])] for c in CONDITIONS] for i in ids]
    return {m: out[m] for m in NAMES}


def clusters(benchmark, ids, labels):
    groups = defaultdict(list)
    for j, i in enumerate(ids):
        if i not in labels:
            raise ValueError(f"{benchmark} {i}: no cluster label")
        groups[labels[i]].append(j)
    return [groups[k] for k in sorted(groups)]


def item_stats(item_cells):
    """Per item, the terms every estimator sums over items, so a resample only re-sums them.

    The tuple is d, d^2, the item's one-run gap noise, the within-cell variance of each condition,
    then for the G-study the row mean, its square, the sum of squared cell means and the cell means.
    """
    stats = []
    for item in item_cells:
        means = [sum(ys) / len(ys) for ys in item]
        var = [sum((y - mu) ** 2 for y in ys) / (len(ys) - 1) for ys, mu in zip(item, means)]
        d = sum(means[1:]) / 3 - means[0]
        row = sum(means) / len(means)
        stats.append((d, d * d, var[0] + sum(var[1:]) / 9, *var,
                      row, row * row, sum(mu * mu for mu in means), *means))
    return stats


def ratio(a, b):
    """SE(2 runs) / SE(3 runs). n cancels, and a negative A counts as 0 (Brennan)."""
    if b == 0:
        return 1.0
    a = max(a, 0.0)
    return math.sqrt((a + b / 2) / (a + b / 3))


def decide(r):
    return 2 if r <= MARGIN else 3


def components(stats, idx):
    """Every estimate for the items at positions idx (repeats allowed)."""
    n, nc = len(idx), len(CONDITIONS)
    s_d, s_dd, s_w, *rest = [math.fsum(col) for col in zip(*(stats[j] for j in idx))]
    var, (s_row, s_rr, s_cells), col = rest[:nc], rest[nc:nc + 3], rest[nc + 3:]
    b = s_w / n
    a = (s_dd - s_d * s_d / n) / (n - 1) - b / RUNS
    out = {"A": a, "B": b, "ratio": ratio(a, b)}
    out.update({c: v / n for c, v in zip(CONDITIONS, var)})
    out.update({f"se{j}": math.sqrt((max(a, 0.0) + b / j) / n) for j in (1, 2, 3)})
    ss_int = s_cells - nc * s_rr - math.fsum(x * x for x in col) / n + nc * s_row * s_row / n
    out["run"] = sum(var) / (n * nc)
    out["item_condition"] = ss_int / ((n - 1) * (nc - 1)) - out["run"] / RUNS
    out["item"] = (s_rr - s_row * s_row / n) / (n - 1) - ss_int / ((n - 1) * (nc - 1) * nc)
    return out


def interval(values):
    """Percentile 95% interval: with 2000 values, the 51st and the 1950th smallest."""
    v = sorted(values)
    j = round(0.025 * len(v))
    return [v[j], v[len(v) - 1 - j]]


def firm(runs, ci_item, ci_cluster):
    if runs == 2:
        return ci_item[1] < MARGIN and ci_cluster[1] < MARGIN
    return ci_item[0] > MARGIN and ci_cluster[0] > MARGIN


def weak(est, ci):
    return ci[1] - ci[0] > abs(est)


def study(benchmark, data, groups, seed, n_boot):
    """One row per model. Each resample's draw of items or clusters is shared by the models."""
    stats = {m: item_stats(c) for m, c in data.items()}
    n = len(next(iter(data.values())))
    est = {m: components(s, range(n)) for m, s in stats.items()}
    boot, by_cluster = defaultdict(list), defaultdict(list)
    rng = random.Random(f"{seed}-{benchmark}-item")
    for _ in range(n_boot):
        idx = rng.choices(range(n), k=n)
        for m, s in stats.items():
            boot[m].append(components(s, idx))
    rng = random.Random(f"{seed}-{benchmark}-cluster")
    for _ in range(n_boot):
        idx = [j for g in rng.choices(groups, k=len(groups)) for j in g]
        for m, s in stats.items():
            by_cluster[m].append(components(s, idx)["ratio"])
    rows = []
    for m in data:
        def value(key, m=m):
            return {"est": est[m][key], "ci": interval(b[key] for b in boot[m])}

        r = est[m]["ratio"]
        ci_item, ci_cluster = interval(b["ratio"] for b in boot[m]), interval(by_cluster[m])
        gap = {"A": value("A"), "B": value("B")}
        runs = decide(r)
        rows.append({
            "benchmark": benchmark, "model": m, "name": NAMES[m], "n_items": n,
            "n_clusters": len(groups), "cluster_sizes": sorted(map(len, groups), reverse=True),
            "gap": gap, "run_by_condition": {c: value(c) for c in CONDITIONS},
            "se": {str(j): value(f"se{j}") for j in (1, 2, 3)},
            "ratio": {"est": r, "ci_item": ci_item, "ci_cluster": ci_cluster},
            "runs": runs, "firm": firm(runs, ci_item, ci_cluster),
            "weak": [k for k, v in gap.items() if weak(v["est"], v["ci"])],
            "gstudy": {"item": value("item"), "item_condition": value("item_condition"),
                       "run": est[m]["run"]},
        })
    return rows


def rounded(x):
    if isinstance(x, float):
        # + 0.0 turns -0.0 into 0.0
        return round(x, 6) + 0.0
    if isinstance(x, dict):
        return {k: rounded(v) for k, v in x.items()}
    if isinstance(x, list):
        return [rounded(v) for v in x]
    return x


def to_json(rows, seed, n_boot):
    rows = [{k: v for k, v in r.items() if k != "cluster_sizes"} for r in rows]
    doc = {"margin": MARGIN, "n_boot": n_boot, "seed": seed, "rows": rows}
    return json.dumps(rounded(doc), indent=2, sort_keys=True) + "\n"


def fmt_ratio(x):
    """3 decimals, more when 3 would print 1.100 for a value on either side of it."""
    d = 3
    while x != MARGIN and float(f"{x:.{d}f}") == MARGIN:
        d += 1
    return f"{x:.{d}f}"


def fmt_var(v, negative_is_zero=False):
    # + 0.0 so a tiny negative value prints as 0.0000, not -0.0000
    est, lo, hi = (f"{round(x, 4) + 0.0:.4f}" for x in (v["est"], *v["ci"]))
    if negative_is_zero and v["est"] < 0:
        return f"{v['est']:.4f} ({lo} to {hi}), taken as 0 in the projection"
    return f"{est} ({lo} to {hi})"


def to_markdown(rows, seed, n_boot):
    out = [
        "# Block 1 D-study",
        "",
        ("Estimated from the block-1 answers (`coderujb.collected.jsonl` and "
         "`deveval.collected.jsonl`, 3 runs per item and condition): the two components of the "
         "size-averaged gap delta_mb for each model and benchmark, and the ratio of the gap's "
         "standard error with 2 runs to that with 3. The rule, set on Nov 8, is 2 runs when the "
         "ratio is at most 1.10 and 3 otherwise, applied to the estimate. The standard errors for "
         "1, 2 and 3 runs are in `dstudy.json`; rerun with `uv run python scripts/dstudy.py`."),
        "",
        "## Decisions",
        "",
        ("| Benchmark | Model | Ratio SE(2)/SE(3) | Interval over items "
         "| Interval over projects/repositories | Runs | Firm or close call |"),
        "|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        x = r["ratio"]
        out.append(f"| {TITLES[r['benchmark']]} | {r['name']} | {fmt_ratio(x['est'])} "
                   f"| {' to '.join(map(fmt_ratio, x['ci_item']))} "
                   f"| {' to '.join(map(fmt_ratio, x['ci_cluster']))} "
                   f"| {r['runs']} | {'firm' if r['firm'] else 'close call'} |")
    out += [
        "",
        ("A close call does not change the decision; the rule uses the estimate. A call is firm "
         "when both intervals sit on the same side of 1.10 as the estimate. The intervals are 95% "
         f"percentile intervals from {n_boot} bootstrap resamples (seed {seed}), one over items "
         "and one over whole projects (CoderUJB) or repositories (DevEval)."),
        "",
        "## Gap components",
        "",
        ("Run noise per condition is the within-cell variance over the 3 runs, averaged over "
         "items. The run noise of a one-run gap weights text by 1 and each size by 1/9, the "
         "squares of delta_mb's weights."),
        "",
        ("| Benchmark | Model | item:condition (spread of the gap across items) "
         "| run noise of a one-run gap | Run noise, text | 10 px | 12 px | 14 px |"),
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        cols = [fmt_var(r["gap"]["A"], negative_is_zero=True), fmt_var(r["gap"]["B"])]
        cols += [fmt_var(r["run_by_condition"][c]) for c in CONDITIONS]
        out.append(f"| {TITLES[r['benchmark']]} | {r['name']} | " + " | ".join(cols) + " |")
    out += ["", "## Precision", ""]
    for b in BENCHES:
        rs = [r for r in rows if r["benchmark"] == b]
        if not rs:
            continue
        n, k, word = rs[0]["n_items"], rs[0]["n_clusters"], CLUSTER_WORD[b]
        text = f"{TITLES[b]}: {n} items in {k} {word}"
        if b == "coderujb":
            text += f" (sizes {', '.join(map(str, rs[0]['cluster_sizes']))})"
        weak_by = [f"{r['name']} {' and '.join(r['weak'])}" for r in rs if r["weak"]]
        text += (". Estimates whose interval over items is wider than the estimate itself: "
                 + ("; ".join(weak_by) if weak_by else "none") + ". ")
        close = sum(not r["firm"] for r in rs)
        text += f"Close calls: {close} of {len(rs)}."
        if b == "coderujb":
            text += f" The interval over projects rests on {k} projects, so it is rough."
        out += [text, ""]
    out += [
        "## Reference: G-study components (descriptive, not used for the decision)",
        "",
        ("Brennan's balanced design, item x condition x (run:item x condition), with condition "
         "random. Its item:condition is per condition, on a different scale from A above. Run is "
         "the mean of the four run noises above."),
        "",
        "| Benchmark | Model | item | item:condition | run |",
        "|---|---|---|---|---|",
    ]
    for r in rows:
        g = r["gstudy"]
        out.append(f"| {TITLES[r['benchmark']]} | {r['name']} | {fmt_var(g['item'])} "
                   f"| {fmt_var(g['item_condition'])} | {g['run']:.4f} |")
    out = [x if x.startswith(("|", "#")) else textwrap.fill(x, 100, break_on_hyphens=False)
           for x in out]
    return "\n".join(out) + "\n"


def load(benchmark, rows, ids, labels):
    return cells(benchmark, rows, ids), clusters(benchmark, ids, labels)


def main(argv=None):
    ap = argparse.ArgumentParser(description="D-study on a balanced block: 2 or 3 runs per pair")
    ap.add_argument("--block", default="results/block1")
    ap.add_argument("--manifests", default="manifests/block1")
    ap.add_argument("--out", default="results/block1")
    args = ap.parse_args(argv)
    rows = []
    try:
        for b in BENCHES:
            path, key, label = CLUSTERS[b]
            labels = {r[key]: r[label] for r in read_jsonl(os.path.join(ROOT, path))}
            ids = read_ids(f"{args.manifests}/{b}.txt")
            data, groups = load(b, read_jsonl(f"{args.block}/{b}.collected.jsonl"), ids, labels)
            rows += study(b, data, groups, SEED, N_BOOT)
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(1)
    for r in rows:
        print(f"{r['benchmark']} {r['name']}: ratio {fmt_ratio(r['ratio']['est'])}, "
              f"{r['runs']} runs")
    os.makedirs(args.out, exist_ok=True)
    for name, text in (("dstudy.json", to_json(rows, SEED, N_BOOT)),
                       ("dstudy.md", to_markdown(rows, SEED, N_BOOT))):
        path = os.path.join(args.out, name)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        print(path)
