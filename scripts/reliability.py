"""Reliability of the full answer table (methodology 3.3).

  prep    re-checks the collected rows against the expected grid (full_table.expected_keys and
          check, block-1 items at 3 runs and the rest at 2) and writes <scratch>/<b>_answers.csv
          (model, item, project, condition, run, passed) for analysis/reliability.R.
  report  reads those CSVs and what analysis/reliability.R wrote (<out>/draws_<b>.csv,
          <out>/mcmc_diagnostics.csv, <out>/sim_check.csv) and writes <out>/reliability.json and
          <out>/findings.md: the variance components, Spearman-Brown reliability of the item
          scores for 1 to 3 runs, the empirical run-to-run correlation, the two G coefficients for
          ranking the models, the share of items passed by every model and by none, and rank
          intervals and text/image swap probabilities from the joint cluster resample
          (scripts/resample.py).

usage: uv run python scripts/reliability.py prep [--full DIR] [--scratch DIR] [--bench B]
       uv run python scripts/reliability.py report [--scratch DIR] [--out DIR]

Every interval is a 95% equal-tailed interval from type-1 percentiles (no interpolation).
"""
import argparse
import csv
import importlib.util
import json
import math
import os
import sys
import textwrap
from collections import Counter, defaultdict
from itertools import combinations

from codeimg.analysis import full_table as ft
from codeimg.analysis import resample as rs

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, "scripts", f"{name}.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


gc = _load("glmm_cells")
ds = gc.ds

COMPONENTS = ("s2_model", "s2_project", "s2_item", "s2_model_project", "s2_model_item", "s2_run")
LABELS = {"s2_model": "model", "s2_project": "project", "s2_item": "item",
          "s2_model_project": "model:project", "s2_model_item": "model:item", "s2_run": "run"}
PRIORS = ("main", "ig")
PRIOR_TEXT = {"main": "half-Cauchy(0.5) on each SD", "ig": "inverse-gamma (V = 1, nu = 0.002)"}
RANKED = ("text", "image", "image10", "image12", "image14")
RANK_TITLES = {"text": "Text", "image": "Image", "image10": "10 px", "image12": "12 px",
               "image14": "14 px"}
CLUSTER_WORD = ds.CLUSTER_WORD
# the prior moves a quantity when its posterior median changes by more than 5%, or by more than
# 0.002 when the main-prior median is below 0.01 (a relative change means little near zero)
SENS_REL, SENS_ABS, SENS_SMALL = 0.05, 0.002, 0.01
ANSWER_FIELDS = ("model", "item", "project", "condition", "run", "passed")
DRAW_FIELDS = ("benchmark", "condition", "prior", "chain", "draw") + COMPONENTS
DIAG_FIELDS = ("benchmark", "condition", "prior", "component", "psrf", "ess", "nitt", "seconds",
               "gate")
# the constants of analysis/reliability.R, repeated here for the report text
MCMC = {"nitt": 60000, "burnin": 10000, "thin": 25, "chains": 2, "max_psrf": 1.05,
        "min_ess": 400, "rerun_scale": 3}


MANIFESTS = os.path.join(ROOT, "manifests")


def name(m):
    return ds.NAMES.get(m, m)


def design(b):
    """(item, project, runs) per item of benchmark b, in the order of its item list."""
    path, key, label = ds.CLUSTERS[b]
    labels = {r[key]: r[label] for r in ds.read_jsonl(os.path.join(ROOT, path))}
    ids = ds.read_ids(os.path.join(ROOT, gc.ID_LISTS[b]))
    block = ds.read_ids(os.path.join(ROOT, "manifests", "block1", f"{b}.txt"))
    return gc.design(b, ids, block, labels)


# The docs/decisions.md entry that excluded each benchmark's items.
EXCLUDED_ON = {"deveval": "2026-11-25", "coderujb": "2026-11-26"}


def excluded(b, manifests=MANIFESTS):
    """Items left out of every analysis (manifests/excluded/<b>.txt): the items whose reference
    fails through the main run's answer path (13 DevEval, 1 CoderUJB; see EXCLUDED_ON)."""
    path = os.path.join(manifests, "excluded", f"{b}.txt")
    if not os.path.exists(path):
        return []
    ids = ds.read_ids(path)
    unknown = sorted(set(ids) - {i for i, _, _ in design(b)})
    if unknown:
        raise ValueError(f"{path}: id(s) not in the {b} item list: {unknown}")
    return ids


def drop_excluded(items, rows, ids):
    """items and rows without the excluded ids, and the ids that were in items. Run after the grid
    check, which sees every item."""
    gone = set(ids)
    return ([it for it in items if it[0] not in gone], [r for r in rows if r["id"] not in gone],
            [it[0] for it in items if it[0] in gone])


def answers(b, rows, items):
    """The answers CSV rows, after checking rows against the grid that items implies."""
    models = list(ds.NAMES)
    parts = defaultdict(list)
    for i, _, n in items:
        parts[n].append(i)
    expected = ft.expected_keys(models, ds.CONDITIONS,
                                [(ids, {m: n for m in models}) for n, ids in parts.items()])
    got = ft.check(rows, expected)
    if not got["ok"]:
        bad = {k: got[k][:3] for k in ("missing", "extra", "duplicates", "null_passed",
                                       "seed_not_run") if got[k]}
        raise ValueError(f"{b}: rows do not match the expected grid: {bad}")
    items, rows, _ = drop_excluded(items, rows, excluded(b))
    project = {i: p for i, p, _ in items}
    pos = {i: j for j, (i, _, _) in enumerate(items)}
    morder = {m: k for k, m in enumerate(models)}
    corder = {c: k for k, c in enumerate(ds.CONDITIONS)}
    rows = sorted(rows, key=lambda r: (morder[r["model"]], corder[r["condition"]], pos[r["id"]],
                                       r["run"]))
    return [(r["model"], r["id"], project[r["id"]], r["condition"], r["run"], int(r["passed"]))
            for r in rows]


def prep(args):
    for b in args.bench or ds.BENCHES:
        rows = ds.read_jsonl(os.path.join(args.full, f"{b}.collected.jsonl"))
        out = answers(b, rows, design(b))
        path = os.path.join(args.scratch, f"{b}_answers.csv")
        gc.write_csv(path, ANSWER_FIELDS, out)
        print(f"{path}: {len(out)} answers")


def quantile(sorted_values, p):
    """Type-1 percentile: the smallest value whose empirical CDF reaches p."""
    return sorted_values[max(math.ceil(p * len(sorted_values)) - 1, 0)]


def summarize(values):
    v = sorted(values)
    return {"median": quantile(v, 0.5), "lo": quantile(v, 0.025), "hi": quantile(v, 0.975)}


def true_variance(c):
    """Variance of a model's item scores that is not run noise; s2_model is constant within a
    model, so it is not part of it."""
    return c["s2_project"] + c["s2_item"] + c["s2_model_project"] + c["s2_model_item"]


def reliability(c, n):
    """Spearman-Brown reliability of an item score averaged over n runs."""
    r1 = true_variance(c) / (true_variance(c) + c["s2_run"])
    return n * r1 / (1 + (n - 1) * r1)


def design_terms(projects, runs):
    """n_items, the clustering weight sum_P (n_P / n)^2 and h = mean of 1 / runs, per item."""
    n = len(projects)
    sizes = Counter(projects).values()
    return {"n_items": n, "n_clusters": len(sizes),
            "cluster_weight": math.fsum((k / n) ** 2 for k in sizes),
            "h": math.fsum(1 / r for r in runs) / n}


def error_variance(c, d):
    """Relative error variance of a model's item-weighted mean score."""
    return (c["s2_model_project"] * d["cluster_weight"]
            + (c["s2_model_item"] + c["s2_run"] * d["h"]) / d["n_items"])


def g_random(c, d):
    return c["s2_model"] / (c["s2_model"] + error_variance(c, d))


def g_finite(c, effects, d):
    """G with the five sampled model effects as the population (variance with divisor k - 1)."""
    mu = math.fsum(effects) / len(effects)
    v = math.fsum((a - mu) ** 2 for a in effects) / (len(effects) - 1)
    return v / (v + error_variance(c, d))


def sample_variance(ys):
    mu = math.fsum(ys) / len(ys)
    return math.fsum((y - mu) ** 2 for y in ys) / (len(ys) - 1)


def within_cell(cells):
    """Mean over cells of the unbiased within-cell variance of the runs."""
    return math.fsum(sample_variance(ys) for ys in cells) / len(cells)


def _centred(xs):
    mu = math.fsum(xs) / len(xs)
    return [x - mu for x in xs]


def _corr(x, y):
    sxx, syy = math.fsum(a * a for a in x), math.fsum(b * b for b in y)
    if sxx == 0 or syy == 0:
        return None
    return math.fsum(a * b for a, b in zip(x, y)) / math.sqrt(sxx * syy)


def run_correlation(cells_by_model):
    """Pearson correlation of run 0 with run 1 over items, per model and pooled over models after
    centring each model's runs on their own means. None when a run has no variance."""
    per, xs, ys = {}, [], []
    for m, cells in cells_by_model.items():
        x, y = _centred([c[0] for c in cells]), _centred([c[1] for c in cells])
        per[m] = _corr(x, y)
        xs += x
        ys += y
    return per, _corr(xs, ys)


def all_none_shares(cells_by_model):
    """Share of items whose cell score is 1 for every model, and 0 for every model."""
    models = list(cells_by_model)
    n = len(cells_by_model[models[0]])
    full = sum(all(min(cells_by_model[m][j]) == 1 for m in models) for j in range(n))
    zero = sum(all(max(cells_by_model[m][j]) == 0 for m in models) for j in range(n))
    return full / n, zero / n


def average_ranks(values):
    """Rank 1 for the largest value; tied values share the mean of their ranks."""
    order = sorted(range(len(values)), key=lambda k: -values[k])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        for k in order[i:j + 1]:
            ranks[k] = (i + j) / 2 + 1
        i = j + 1
    return ranks


def swap_probability(text, image):
    """Share of draws where a pair's text order and image order are strictly opposite; a tie in
    either counts as half. text and image are per-draw differences between the two models."""
    score = 0.0
    for t, i in zip(text, image):
        if t == 0 or i == 0:
            score += 0.5
        elif (t > 0) != (i > 0):
            score += 1
    return score / len(text)


def read_csv(path, fields):
    with open(path, encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    if rows and not set(fields) <= set(rows[0]):
        raise ValueError(f"{path}: missing column(s) {sorted(set(fields) - set(rows[0]))}")
    return rows


def load_answers(path):
    """Models, items and their projects, and passes[model][condition][item position] by run."""
    rows = read_csv(path, ANSWER_FIELDS)
    models, items, project = [], [], {}
    got = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    for r in rows:
        if r["model"] not in models:
            models.append(r["model"])
        if r["item"] not in project:
            items.append(r["item"])
            project[r["item"]] = r["project"]
        got[r["model"]][r["condition"]][r["item"]].append((int(r["run"]), int(r["passed"])))
    cells = {}
    runs = None
    for m in models:
        cells[m] = {}
        for c in ds.CONDITIONS:
            per = [sorted(got[m][c][i]) for i in items]
            n = [len(p) for p in per]
            if runs is None:
                runs = n
            if n != runs or any([k for k, _ in p] != list(range(len(p))) for p in per):
                raise ValueError(f"{path}: {name(m)} {c}: runs differ from the first cell's")
            cells[m][c] = [[y for _, y in p] for p in per]
    return {"models": models, "items": items, "projects": [project[i] for i in items],
            "runs": runs, "cells": cells}


def load_draws(path):
    """{(condition, prior): [{component: value, ..., 'effects': [a_m]}]} in file order."""
    rows = read_csv(path, DRAW_FIELDS)
    effects = sorted((k for k in (rows[0] if rows else {}) if k.startswith("a")),
                     key=lambda k: int(k[1:]))
    out = defaultdict(list)
    for r in rows:
        d = {k: float(r[k]) for k in COMPONENTS}
        d["effects"] = [float(r[k]) for k in effects]
        out[(r["condition"], r["prior"])].append(d)
    return out


def sixths(runs):
    """A cell score in sixths, so rates over the same items compare exactly (2 or 3 runs)."""
    return sum(runs) * 6 // len(runs)


def rank_stability(data, groups, seed, n_boot):
    """Full-data rate and rank, rank interval, and pairwise text/image swap probability."""
    models = data["models"]
    col = {(m, c): [sixths(ys) for ys in data["cells"][m][c]]
           for m in models for c in ds.CONDITIONS}

    def totals(idx):
        t = {k: sum(v[j] for j in idx) for k, v in col.items()}
        out = {c: [t[(m, c)] for m in models] for c in ds.CONDITIONS}
        out["image"] = [sum(t[(m, c)] for c in ds.CONDITIONS[1:]) for m in models]
        return out

    n = len(data["items"])
    full = totals(range(n))
    draws = [totals(idx) for idx in rs.cluster_draws(groups, n_boot, seed)]
    res = {"rates": {}, "ranks": {}, "swap": []}
    for c in RANKED:
        scale = 6 * n * (3 if c == "image" else 1)
        ranks = average_ranks(full[c])
        per_draw = [average_ranks(t[c]) for t in draws]
        res["rates"][c] = {name(m): full[c][k] / scale for k, m in enumerate(models)}
        res["ranks"][c] = {}
        for k, m in enumerate(models):
            v = sorted(r[k] for r in per_draw)
            res["ranks"][c][name(m)] = {"rank": ranks[k], "lo": quantile(v, 0.025),
                                        "hi": quantile(v, 0.975)}
    for a, b in combinations(range(len(models)), 2):
        diff = {c: [t[c][a] - t[c][b] for t in draws] for c in ("text", "image")}
        res["swap"].append({"pair": [name(models[a]), name(models[b])],
                            "p": swap_probability(diff["text"], diff["image"])})
    return res


def sensitivity(main, alt):
    """Relative change of the posterior median from the main prior to the alternative."""
    a, b = main["median"], alt["median"]
    change = (b - a) / a if a else None
    moved = abs(b - a) > SENS_ABS if abs(a) < SENS_SMALL else abs(b - a) > SENS_REL * abs(a)
    return {"relative_change": change, "moved": moved}


def condition_report(data, c, draws, d):
    cells = {m: data["cells"][m][c] for m in data["models"]}
    out = {"components": {}, "g_random": {}, "g_finite": {}}
    for prior in PRIORS:
        xs = draws.get((c, prior))
        if not xs:
            continue
        out["components"][prior] = {k: summarize([x[k] for x in xs]) for k in COMPONENTS}
        out["g_random"][prior] = summarize([g_random(x, d) for x in xs])
        out["g_finite"][prior] = summarize([g_finite(x, x["effects"], d) for x in xs])
        if prior == "main":
            out["reliability"] = {str(n): summarize([reliability(x, n) for x in xs])
                                  for n in (1, 2, 3)}
    if "main" not in out["components"]:
        raise ValueError(f"no main-prior draws for {c}")
    if "ig" in out["components"]:
        sens = {"s2_model": sensitivity(out["components"]["main"]["s2_model"],
                                        out["components"]["ig"]["s2_model"])}
        for k in ("g_random", "g_finite"):
            sens[k] = sensitivity(out[k]["main"], out[k]["ig"])
        m, i = out["g_random"]["main"], out["g_random"]["ig"]
        sens["g_random_prior_driven"] = m["hi"] < i["lo"] or i["hi"] < m["lo"]
        out["sensitivity"] = sens
    per, pooled = run_correlation(cells)
    full, zero = all_none_shares(cells)
    out["empirical"] = {
        "within_cell": {"all": within_cell([ys for m in cells for ys in cells[m]]),
                        "by_model": {name(m): within_cell(cells[m]) for m in cells}},
        "run_correlation": {"pooled": pooled, "by_model": {name(m): v for m, v in per.items()}},
    }
    out["all_pass_share"], out["none_pass_share"] = full, zero
    return out


def rounded(x):
    if isinstance(x, float):
        return round(x, 6)
    if isinstance(x, dict):
        return {k: rounded(v) for k, v in x.items()}
    if isinstance(x, list):
        return [rounded(v) for v in x]
    return x


def build(scratch, out_dir, benches=ds.BENCHES):
    diag = read_csv(os.path.join(out_dir, "mcmc_diagnostics.csv"), DIAG_FIELDS)
    sim_path = os.path.join(out_dir, "sim_check.csv")
    sim = read_csv(sim_path, ("component",)) if os.path.exists(sim_path) else []
    report = {
        "settings": {"seed": rs.SEED, "n_boot": rs.N_BOOT, "priors": PRIOR_TEXT, "mcmc": MCMC,
                     "interval": "95% equal-tailed, type-1 percentiles"},
        "benchmarks": {},
    }
    for b in benches:
        data = load_answers(os.path.join(scratch, f"{b}_answers.csv"))
        draws = load_draws(os.path.join(out_dir, f"draws_{b}.csv"))
        d = design_terms(data["projects"], data["runs"])
        groups = ds.clusters(b, data["items"], dict(zip(data["items"], data["projects"])))
        report["benchmarks"][b] = {
            "design": d,
            "conditions": {c: condition_report(data, c, draws, d) for c in ds.CONDITIONS},
            **rank_stability(data, groups, f"{rs.SEED}-{b}", rs.N_BOOT),
        }
        gone = excluded(b)
        report["benchmarks"][b]["excluded"] = {"count": len(gone), "items": gone}
    fits = defaultdict(set)
    for r in diag:
        fits[(r["benchmark"], r["condition"], r["prior"])].add(r["gate"])
    report["gate"] = {"fits": len(fits), "passed": sum(v == {"pass"} for v in fits.values()),
                      "failed": [list(k) for k, v in sorted(fits.items()) if v != {"pass"}],
                      "rows": diag}
    report["sim_check"] = sim
    return rounded(report)


def fmt(s, digits=4):
    return f"{s['median']:.{digits}f} ({s['lo']:.{digits}f} to {s['hi']:.{digits}f})"


def fmt_rank(r):
    return f"{r['rank']:g} ({r['lo']:g} to {r['hi']:g})"


def opt(x, digits=3):
    return "n/a" if x is None else f"{x:.{digits}f}"


def excluded_note(rep):
    parts = [f"{v['excluded']['count']} {ds.TITLES[b]} ({EXCLUDED_ON[b]})"
             for b, v in rep["benchmarks"].items() if v.get("excluded", {}).get("count")]
    return f", minus the {' and '.join(parts)} items excluded in docs/decisions.md" if parts else ""


def to_markdown(rep):
    out = [
        "# Reliability",
        "",
        ("Methodology 3.3, on the full answer table (results/full, 3 runs for block-1 items and 2 "
         "for the rest)" + excluded_note(rep) + ". Variance components come from one Gaussian "
         "mixed model per benchmark and "
         "condition on the 0/1 pass of each run (analysis/reliability.R, MCMCglmm): model, "
         "project (CoderUJB) or repository (DevEval), item, model:project, model:item, and the "
         "run within a cell. Intervals are 95% equal-tailed (type-1 percentiles). Rerun with "
         "`uv run python scripts/reliability.py prep`, the R script, then `report`; every number "
         "is in `reliability.json`."),
        "",
        "## Run noise and item-score reliability",
        "",
        ("Run is the occasion component (within-cell variance); the empirical value next to it is "
         "the mean unbiased within-cell variance. rho_n is the Spearman-Brown reliability of a "
         "model's item score averaged over n runs, among items within a model (book p. 147). The "
         "empirical rho_1 is the correlation of run 0 with run 1, pooled over models."),
        "",
        "| Benchmark | Condition | Run | Empirical | rho_1 | rho_2 | rho_3 | Empirical rho_1 |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for b, rb in rep["benchmarks"].items():
        for c, rc in rb["conditions"].items():
            r, e = rc["reliability"], rc["empirical"]
            out.append(f"| {ds.TITLES[b]} | {c} | {fmt(rc['components']['main']['s2_run'])} "
                       f"| {e['within_cell']['all']:.4f} | {fmt(r['1'], 3)} | {fmt(r['2'], 3)} "
                       f"| {fmt(r['3'], 3)} | {opt(e['run_correlation']['pooled'])} |")
    first = next(iter(rep["benchmarks"].values()))
    names = list(first["conditions"]["text"]["empirical"]["within_cell"]["by_model"])
    out += ["", "Empirical within-cell variance by model:", "",
            "| Benchmark | Condition | " + " | ".join(names) + " |",
            "|---|---|" + "---|" * len(names)]
    for b, rb in rep["benchmarks"].items():
        for c, rc in rb["conditions"].items():
            by = rc["empirical"]["within_cell"]["by_model"]
            out.append(f"| {ds.TITLES[b]} | {c} | "
                       + " | ".join(f"{by[n]:.4f}" for n in names) + " |")
    out += ["", "## Variance components", "",
            "Main prior. The model term rests on 5 models (4 df).", "",
            "| Benchmark | Condition | " + " | ".join(LABELS[k] for k in COMPONENTS) + " |",
            "|---|---|" + "---|" * len(COMPONENTS)]
    for b, rb in rep["benchmarks"].items():
        for c, rc in rb["conditions"].items():
            comp = rc["components"]["main"]
            out.append(f"| {ds.TITLES[b]} | {c} | "
                       + " | ".join(fmt(comp[k]) for k in COMPONENTS) + " |")
    out += ["", "## G for ranking the five models", "",
            ("Secondary line. Relative error includes model:project, model:item and run noise for "
             "the benchmark's items and runs. Random-model G uses s2_model, which rests on 4 df "
             "and depends on the prior; finite-population G uses the variance of the five model "
             "effects in the same draw."), "",
            ("| Benchmark | Condition | G random, main | G random, inverse-gamma "
             "| G finite, main | G finite, inverse-gamma |"),
            "|---|---|---|---|---|---|"]
    for b, rb in rep["benchmarks"].items():
        for c, rc in rb["conditions"].items():
            cols = [fmt(rc[g][p], 3) if p in rc[g] else "not run"
                    for g in ("g_random", "g_finite") for p in PRIORS]
            out.append(f"| {ds.TITLES[b]} | {c} | " + " | ".join(cols) + " |")
    flags = []
    for b, rb in rep["benchmarks"].items():
        for c, rc in rb["conditions"].items():
            s = rc.get("sensitivity")
            if not s:
                continue
            moved = [k for k in ("s2_model", "g_random", "g_finite") if s[k]["moved"]]
            if moved:
                flags.append(f"{ds.TITLES[b]} {c}: {', '.join(moved)}")
            if s["g_random_prior_driven"]:
                flags.append(f"{ds.TITLES[b]} {c}: random-model G intervals do not overlap "
                             "between priors (prior-driven)")
    out += ["", "Moved by the prior (median change over 5%, or over 0.002 below 0.01): "
            + ("; ".join(flags) if flags else "none") + "."]
    out += ["", "## Items passed by every model or by none", "",
            "| Benchmark | Condition | All 5 pass | None pass |", "|---|---|---|---|"]
    for b, rb in rep["benchmarks"].items():
        for c, rc in rb["conditions"].items():
            out.append(f"| {ds.TITLES[b]} | {c} | {100 * rc['all_pass_share']:.1f}% "
                       f"| {100 * rc['none_pass_share']:.1f}% |")
    out += ["", "## Rank stability", "",
            (f"Item-weighted pass rates (each item counts once; its score is the mean of its "
             f"runs), ranked 1 to 5, with the 95% interval of the rank over {rep['settings']['n_boot']} "
             f"joint resamples of whole {CLUSTER_WORD['coderujb']} or repositories (seed "
             f"{rep['settings']['seed']}). Image is the mean of the three sizes. These rates weigh "
             "items equally, so they can differ by a point from results/full/findings.md, which "
             "pools answers.")]
    for b, rb in rep["benchmarks"].items():
        out += ["", f"{ds.TITLES[b]}:", "",
                "| Model | " + " | ".join(RANK_TITLES[c] for c in RANKED) + " |",
                "|---|" + "---|" * len(RANKED)]
        for n in rb["ranks"]["text"]:
            out.append(f"| {n} | " + " | ".join(
                f"{100 * rb['rates'][c][n]:.1f}%, {fmt_rank(rb['ranks'][c][n])}" for c in RANKED)
                + " |")
        out += ["", "Probability that the pair's order in text and in image is reversed:", "",
                "| Pair | P(swap) |", "|---|---|"]
        for s in rb["swap"]:
            out.append(f"| {s['pair'][0]} vs {s['pair'][1]} | {s['p']:.3f} |")
    g = rep["gate"]
    longer = len({(r["benchmark"], r["condition"], r["prior"]) for r in g["rows"]
                  if int(r["nitt"]) > MCMC["nitt"]})
    out += ["", "## MCMC", "",
            (f"{g['passed']} of {g['fits']} fits pass the gate (PSRF at most "
             f"{MCMC['max_psrf']} and effective sample size at least {MCMC['min_ess']} for every "
             f"component, {MCMC['chains']} chains of {MCMC['nitt']} iterations, burn-in "
             f"{MCMC['burnin']}, thin {MCMC['thin']}; a fit that fails is rerun once at "
             f"{MCMC['rerun_scale']} times the length, which {longer} of them needed). Priors: main "
             f"{PRIOR_TEXT['main']}, sensitivity {PRIOR_TEXT['ig']}. Gates per component are in "
             "`mcmc_diagnostics.csv`.")]
    if g["failed"]:
        out += ["", "Failing fits: " + "; ".join(" ".join(f) for f in g["failed"]) + "."]
    if rep["sim_check"]:
        missed = [r["component"] for r in rep["sim_check"] if r["covered"] != "TRUE"]
        out += ["", ("Simulation check (one simulated dataset with the CoderUJB design and known "
                     "components, a wiring check, not a coverage claim): "
                     + (f"missed {', '.join(missed)} (see docs/decisions.md)" if missed
                        else "every true value inside its 95% interval")
                     + f"; gate {rep['sim_check'][0]['gate']}.")]
    out = [x if x.startswith(("|", "#")) or not x else textwrap.fill(x, 100,
                                                                      break_on_hyphens=False)
           for x in out]
    return "\n".join(out) + "\n"


def report(args):
    rep = build(args.scratch, args.out)
    os.makedirs(args.out, exist_ok=True)
    for fname, text in (("reliability.json", json.dumps(rep, indent=1) + "\n"),
                        ("findings.md", to_markdown(rep))):
        path = os.path.join(args.out, fname)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        print(path)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Reliability analysis of the full answer table")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("prep")
    p.add_argument("--full", default=os.path.join(ROOT, "results", "full"))
    p.add_argument("--scratch", default=os.path.join(ROOT, "scratch", "reliability"))
    p.add_argument("--bench", action="append", choices=ds.BENCHES)
    p = sub.add_parser("report")
    p.add_argument("--scratch", default=os.path.join(ROOT, "scratch", "reliability"))
    p.add_argument("--out", default=os.path.join(ROOT, "results", "reliability"))
    args = ap.parse_args(argv)
    try:
        (prep if args.cmd == "prep" else report)(args)
    except (ValueError, OSError) as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
