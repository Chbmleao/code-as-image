"""Main analysis of the full answer table (methodology 3.3).

  gaps           the paired image-text gap per model (delta_mb, mean over sizes) with the
                 clustered and item-level t intervals and Holm, the pooled gap with its joint
                 cluster resample interval, the per-size gaps and size differences (BH), prompt
                 tokens and the token ratio, leave-one-project-out, context length buckets, floor
                 and ceiling shares, scoring shares and ranks. Writes <out>/gaps.json,
                 <out>/never_passed.csv and <out>/figures/{main_gap,size_curve}.pdf.
  prep           writes <scratch>/<b>_answers.csv (model, item, project, condition, run, passed)
                 for analysis/glmm_main.R.
  contamination  flags (model, item) when another model copies the reference in a text run, and
                 compares the gaps with and without the flagged items against a matched random
                 removal. Writes <out>/contamination.json and <out>/contamination_flags.csv.
  report         writes <out>/findings.md from gaps.json, glmm.json and contamination.json.

usage: uv run python scripts/analysis.py gaps [--full DIR] [--out DIR]
       uv run python scripts/analysis.py prep [--full DIR] [--scratch DIR]
       uv run python scripts/analysis.py contamination --answers DIR [--full DIR] [--out DIR]
       uv run python scripts/analysis.py report [--out DIR]

The models are those of configs/experiment.toml (CODEIMG_CONFIG overrides the path). Gaps are
image minus text, so a loss is negative. Every resample interval is 95% equal-tailed from type-1
percentiles.
"""
import argparse
import importlib.util
import json
import math
import os
import random
import sys
from collections import Counter, defaultdict
from itertools import combinations

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, "scripts", f"{name}.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


rel = _load("reliability")
st = _load("analysis_stats")
ds, gc, ft, rs = rel.ds, rel.gc, rel.ft, rel.rs
config = ft.config

OUT = os.path.join(ROOT, "results", "analysis")
FULL = os.path.join(ROOT, "results", "full")
MANIFESTS = os.path.join(ROOT, "manifests")
DSTUDY = ft.DSTUDY
PROMPT_COUNTS = "benchmarks/{b}/results/prompt_counts.jsonl"
LENGTH_COLUMN = "qwen35"
LOPO_BENCH, LOPO_N = "coderujb", 4
NEVER_FIELDS = ("benchmark", "item", "project")
FLAG_FIELDS = ("benchmark", "item", "copied_by", "run")
P_KEYS = {"p", "holm", "bh"}
# matched random removal: quintiles of the mean text score x terciles of length
CONTROL = {"draws": 1000, "bins": (5, 3), "glmm_top": 0.10}
CONTROL_SEED = 20261118


def name(m):
    return ds.NAMES.get(m, m)


def model_set(cfg):
    """Model repos of the config: the established order first, then new ones in config order."""
    repos = [m["repo"] for m in cfg["models"].values()]
    return [m for m in ds.NAMES if m in repos] + [m for m in repos if m not in ds.NAMES]


def conditions(cfg):
    return ["text"] + [f"image{s}" for s in cfg["experiment"]["sizes"]]


def grid_parts(b, cfg, models, manifests=MANIFESTS, dstudy=DSTUDY):
    """[(item ids, {model: runs})]: block 1 at experiment.runs, the rest at the D-study's runs."""
    return [(ds.read_ids(os.path.join(manifests, "block1", f"{b}.txt")),
             dict.fromkeys(models, cfg["experiment"]["runs"])),
            (ds.read_ids(os.path.join(manifests, "rest", f"{b}.txt")),
             config.runs_from(dstudy, b, models))]


def read_lengths(b):
    return {r["id"]: r[LENGTH_COLUMN]
            for r in ds.read_jsonl(os.path.join(ROOT, PROMPT_COUNTS.format(b=b)))}


def load_benchmark(b, rows, items, models, conds, parts):
    """Checks rows against the expected grid and returns the cells of each model and condition:
    cells[m][c][j] is item j's passes by run, tokens[m][c][j] its run-0 prompt tokens."""
    have = Counter(r["model"] for r in rows)
    empty = [name(m) for m in models if not have[m]]
    if empty:
        raise ValueError(f"{b}: no rows for {', '.join(empty)}")
    rows = [r for r in rows if r["model"] in models]
    got = ft.check(rows, ft.expected_keys(models, conds, parts))
    if not got["ok"]:
        bad = {k: got[k][:3] for k in ("missing", "extra", "duplicates", "null_passed",
                                       "seed_not_run") if got[k]}
        raise ValueError(f"{b}: rows do not match the expected grid: {bad}")
    pos = {i: j for j, (i, _, _) in enumerate(items)}
    runs = defaultdict(list)
    tokens = {m: {c: [None] * len(items) for c in conds} for m in models}
    for r in rows:
        if r["id"] not in pos:
            raise ValueError(f"{b}: {r['key']}: item not in the item list")
        runs[(r["model"], r["condition"], r["id"])].append((r["run"], int(r["passed"])))
        if r["run"] == 0:
            tokens[r["model"]][r["condition"]][pos[r["id"]]] = r["prompt_tokens"]
    cells = {m: {c: [[y for _, y in sorted(runs[(m, c, i)])] for i, _, _ in items]
                 for c in conds} for m in models}
    return {"benchmark": b, "models": models, "conditions": conds,
            "items": [i for i, _, _ in items], "projects": [p for _, p, _ in items],
            "cells": cells, "tokens": tokens, "rows": rows}


def scores(data):
    """Y[m][c][j]: the mean of item j's runs."""
    return {m: {c: [sum(ys) / len(ys) for ys in data["cells"][m][c]] for c in data["conditions"]}
            for m in data["models"]}


def mean(xs):
    return math.fsum(xs) / len(xs)


def differences(y, a, b):
    """Per item, Y(a) - Y(b); a may be a list of conditions, averaged."""
    a = a if isinstance(a, list) else [a]
    return [mean([y[c][j] for c in a]) - y[b][j] for j in range(len(y[b]))]


def test_row(model, values, projects, **extra):
    c = st.cluster_t(values, projects)
    i = st.item_t(values)
    return {"model": name(model), "repo": model, **extra, "est": c["est"], "n": c["n"],
            "cluster": {k: c[k] for k in ("clusters", "df", "se", "lo", "hi", "p")},
            "item": {k: i[k] for k in ("df", "se", "lo", "hi", "p")}}


def adjust(rows, how, key):
    ps = [r["cluster"]["p"] for r in rows]
    for r, q in zip(rows, (st.holm if how == "holm" else st.bh)(ps)):
        r[key] = q


def pooled(d_by_model, groups, seed, n_boot):
    """Mean of the model gaps, with the resample interval: each draw keeps the same items for
    every model."""
    models = list(d_by_model)
    est = mean([mean(d_by_model[m]) for m in models])
    per_draw = [mean([mean([d_by_model[m][j] for j in idx]) for m in models])
                for idx in rs.cluster_draws(groups, n_boot, seed)]
    s = rel.summarize(per_draw)
    return {"est": est, "lo": s["lo"], "hi": s["hi"], "n_boot": n_boot}


def bucket_of(n, buckets):
    for k, (lo, hi) in enumerate(buckets):
        if lo <= n < hi:
            return k
    raise ValueError(f"{n} tokens is outside every length bucket {buckets}")


def check_lengths(b, items, lengths):
    missing = [i for i in items if i not in lengths]
    if missing:
        raise ValueError(f"{b}: no prompt count for {len(missing)} item(s), first {missing[0]}")


def spread(values):
    v = sorted(values)
    return {"median": rel.quantile(v, 0.5), "q1": rel.quantile(v, 0.25),
            "q3": rel.quantile(v, 0.75)}


def lopo_projects(projects, n):
    """The n largest projects by item count, ties by name."""
    return [p for p, _ in sorted(Counter(projects).items(), key=lambda kv: (-kv[1], kv[0]))[:n]]


def scoring_shares(data):
    """Answer-level shares per model and condition: empty, truncated, no code and (DevEval) no
    `def` line for the target outside no_code."""
    cells = defaultdict(Counter)
    for r in data["rows"]:
        c = cells[(r["model"], r["condition"])]
        c["answers"] += 1
        c["empty"] += r["output_tokens"] == 0
        c["truncated"] += bool(r["truncated"])
        c["no_code"] += r["reason"] == "no_code"
        c["no_def_line"] += r["defines_target"] is False and r["reason"] != "no_code"
    keys = ["empty", "truncated", "no_code"] + (["no_def_line"] if data["benchmark"] == "deveval"
                                                 else [])
    return {name(m): {c: {"answers": cells[(m, c)]["answers"],
                          **{k: cells[(m, c)][k] / cells[(m, c)]["answers"] for k in keys}}
                      for c in data["conditions"]} for m in data["models"]}


def benchmark_gaps(data, lengths, buckets, seed, n_boot):
    b, models, conds = data["benchmark"], data["models"], data["conditions"]
    sizes = conds[1:]
    items, projects = data["items"], data["projects"]
    y = scores(data)
    groups = ds.clusters(b, items, dict(zip(items, projects)))
    out = {"n_items": len(items), "n_clusters": len(groups)}

    rates = {c: {name(m): mean(y[m][c]) for m in models} for c in conds}
    rates["image"] = {name(m): mean([rates[c][name(m)] for c in sizes]) for m in models}
    out["rates"] = rates
    out["ranks"] = {c: dict(zip(rates[c], rel.average_ranks(list(rates[c].values()))))
                    for c in ["text", "image"] + sizes}

    d_main = {m: differences(y[m], sizes, "text") for m in models}
    out["main"] = [test_row(m, d_main[m], projects) for m in models]
    out["pooled"] = pooled(d_main, groups, seed, n_boot)
    out["sizes"] = [test_row(m, differences(y[m], s, "text"), projects, size=s)
                    for m in models for s in sizes]
    out["size_diffs"] = [test_row(m, differences(y[m], s1, s2), projects, pair=f"{s1}-{s2}")
                         for m in models for s2, s1 in combinations(sizes, 2)]

    tok = data["tokens"]
    out["tokens"] = {name(m): {c: spread(tok[m][c]) for c in conds} for m in models}
    out["token_ratio"] = {
        name(m): {s: rel.quantile(sorted(a / t for a, t in zip(tok[m][s], tok[m]["text"])), 0.5)
                  for s in sizes} for m in models}
    for m in models:
        r = out["token_ratio"][name(m)]
        r["mean_over_sizes"] = mean([r[s] for s in sizes])

    out["lopo"] = []
    if b == LOPO_BENCH:
        for p in lopo_projects(projects, LOPO_N):
            keep = [j for j, q in enumerate(projects) if q != p]
            for m in models:
                out["lopo"].append(test_row(m, [d_main[m][j] for j in keep],
                                            [projects[j] for j in keep], left_out=p))

    check_lengths(b, items, lengths)
    bucket = [bucket_of(lengths[i], buckets) for i in items]
    out["length"] = []
    for k, (lo, hi) in enumerate(buckets):
        keep = [j for j in range(len(items)) if bucket[j] == k]
        if not keep:
            continue
        for m in models:
            for s in sizes:
                d = differences(y[m], s, "text")
                out["length"].append(test_row(m, [d[j] for j in keep],
                                              [projects[j] for j in keep],
                                              size=s, bucket=f"{lo}-{hi}"))

    cells = data["cells"]
    out["floor_ceiling"] = {
        name(m): {c: {"none": sum(max(ys) == 0 for ys in cells[m][c]) / len(items),
                      "all": sum(min(ys) == 1 for ys in cells[m][c]) / len(items)}
                  for c in conds} for m in models}
    out["all_none"] = {}
    for c in conds:
        full, zero = rel.all_none_shares({m: cells[m][c] for m in models})
        out["all_none"][c] = {"all_models_pass": full, "no_model_passes": zero}
    never = [j for j in range(len(items))
             if all(max(cells[m][c][j]) == 0 for m in models for c in conds)]
    out["never_passed"] = [(b, items[j], projects[j]) for j in never]
    out["scoring"] = scoring_shares(data)
    return out


def gaps_report(cfg, inputs, seed=rs.SEED, n_boot=rs.N_BOOT):
    """inputs[b]: the load_benchmark output and the item lengths, per benchmark."""
    buckets = cfg["sample"]["deveval_buckets"]
    rep = {"settings": {"models": [name(m) for m in model_set(cfg)], "seed": seed,
                        "n_boot": n_boot, "level": st.LEVEL, "length_buckets": buckets,
                        "length_column": LENGTH_COLUMN,
                        "interval": "CR1 cluster t with G - 1 df; item line: paired t",
                        "pooled_interval": "95% equal-tailed, type-1 percentiles"},
           "benchmarks": {}}
    for b, (data, lengths) in inputs.items():
        rep["benchmarks"][b] = benchmark_gaps(data, lengths, buckets, f"{seed}-{b}", n_boot)
    for key, how in (("main", "holm"), ("sizes", "bh"), ("size_diffs", "bh"), ("length", "bh")):
        adjust([r for v in rep["benchmarks"].values() for r in v[key]], how, how)
    return rep


def read_inputs(cfg, full, benches=ds.BENCHES):
    models, conds = model_set(cfg), conditions(cfg)
    out = {}
    for b in benches:
        rows = ds.read_jsonl(os.path.join(full, f"{b}.collected.jsonl"))
        data = load_benchmark(b, rows, rel.design(b), models, conds, grid_parts(b, cfg, models))
        out[b] = (data, read_lengths(b))
    return out


def rounded(x, key=None):
    """6 decimals, except p-values, which keep 3 significant digits so a tiny p is not 0."""
    if isinstance(x, float):
        return float(f"{x:.3g}") if key in P_KEYS else round(x, 6)
    if isinstance(x, dict):
        return {k: rounded(v, k) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [rounded(v, key) for v in x]
    return x


def write_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(json.dumps(rounded(obj), indent=1) + "\n")
    print(path)


def gaps(args):
    cfg = config.load()
    rep = gaps_report(cfg, read_inputs(cfg, args.full))
    never = [row for v in rep["benchmarks"].values() for row in v.pop("never_passed")]
    for b, v in rep["benchmarks"].items():
        v["never_passed"] = sum(row[0] == b for row in never)
    write_json(os.path.join(args.out, "gaps.json"), rep)
    path = os.path.join(args.out, "never_passed.csv")
    gc.write_csv(path, NEVER_FIELDS, never)
    print(path)
    figures(rounded(rep), os.path.join(args.out, "figures"))


def answer_rows(data):
    """The answers CSV of analysis/reliability.R's format, in model, condition, item, run order."""
    out = []
    for m in data["models"]:
        for c in data["conditions"]:
            for i, p, ys in zip(data["items"], data["projects"], data["cells"][m][c]):
                out += [(m, i, p, c, r, y) for r, y in enumerate(ys)]
    return out


def prep(args):
    cfg = config.load()
    for b, (data, _) in read_inputs(cfg, args.full).items():
        out = answer_rows(data)
        path = os.path.join(args.scratch, f"{b}_answers.csv")
        gc.write_csv(path, rel.ANSWER_FIELDS, out)
        print(f"{path}: {len(out)} answers")


def _contamination_module():
    path = os.path.join(ROOT, "benchmarks", "shared", "contamination.py")
    spec = importlib.util.spec_from_file_location("contamination", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def run_of(key):
    """(condition, run) from an answer key, model__item__condition__rN."""
    _, condition, run = key.rsplit("__", 2)
    return condition, int(run[1:])


def text_copies(b, answers_dir):
    """{(model, item, run): exact copy?} over the text answers of block 1 and the rest."""
    cont = _contamination_module()
    out = {}
    for part in ("block1", "rest"):
        path = os.path.join(answers_dir, f"{part}_{b}_text.jsonl")
        pairs = (cont.deveval_pairs(path, os.path.join(answers_dir, "deveval_gold.jsonl"))
                 if b == "deveval" else
                 cont.coderujb_pairs(path, os.path.join(answers_dir, "coderujb_items.jsonl")))
        for key, model, item, ans, ref in pairs:
            condition, run = run_of(key)
            if condition != "text":
                raise ValueError(f"{path}: {key} is not a text answer")
            out[(model, item, run)] = ans == ref
    return out


def check_answers(b, data, copies):
    """Every graded text answer of the table must have its reply; no_code, no_reply and
    request_error answers have none and count as no copy."""
    want = {(r["model"], r["id"], r["run"]) for r in data["rows"]
            if r["condition"] == "text" and r["reason"] not in ft.NOT_GRADED}
    missing = sorted(want - copies.keys())
    if missing:
        raise ValueError(f"{b}: {len(missing)} graded text answer(s) have no reply in the answers "
                         f"files, first {missing[0]}")


def flags_of(models, items, copies):
    """flags[m]: items where another model copied the reference in some text run."""
    copied = defaultdict(set)
    for (m, i, _), exact in copies.items():
        if exact:
            copied[i].add(m)
    return {m: {i for i in items if copied[i] - {m}} for m in models}


def equal_groups(values, ids, k):
    """Group 0..k-1 of each position: equal-count groups in (value, id) order."""
    order = sorted(range(len(values)), key=lambda j: (values[j], ids[j]))
    out = [0] * len(values)
    for r, j in enumerate(order):
        out[j] = r * k // len(values)
    return out


def matched_removals(flagged, bins, pool, n_draws, seed):
    """Each draw removes, per bin, as many pool items as the flagged set has there, without
    replacement. Returns the draws and the per-bin shortfall when a bin's pool is too small."""
    need = Counter(bins[j] for j in flagged)
    by_bin = defaultdict(list)
    for j in sorted(pool):
        by_bin[bins[j]].append(j)
    short = {str(k): need[k] - len(by_bin[k]) for k in sorted(need) if need[k] > len(by_bin[k])}
    rng = random.Random(seed)
    draws = [sorted(j for k in sorted(need) for j in rng.sample(by_bin[k], min(need[k],
                                                                               len(by_bin[k]))))
             for _ in range(n_draws)]
    return draws, short


def flag2_overlap(models, items, modes, flags):
    """2x2 counts of the copy flag against the GLMM flag (item:model mode in the model's top
    10%)."""
    out = {}
    for m in models:
        got = sorted(((v, i) for (mm, i), v in modes.items() if mm == m), key=lambda t: (-t[0], t[1]))
        top = {i for _, i in got[:math.ceil(CONTROL["glmm_top"] * len(got))]}
        f = flags[m]
        out[name(m)] = {"both": len(f & top), "copy_only": len(f - top),
                        "glmm_only": len(top - f), "neither": len(set(items) - f - top)}
    return out


def read_item_modes(path):
    if not os.path.exists(path):
        raise ValueError(f"{path} is missing: run analysis/glmm_main.R first")
    rows = rel.read_csv(path, ("benchmark", "item", "model", "mode"))
    out = defaultdict(dict)
    for r in rows:
        out[r["benchmark"]][(r["model"], r["item"])] = float(r["mode"])
    return out


def contamination_report(inputs, copies_by_bench, modes, seed=CONTROL_SEED,
                         n_draws=None):
    n_draws = n_draws or CONTROL["draws"]
    rep = {"settings": {"control_draws": n_draws, "seed": seed, "bins": CONTROL["bins"],
                        "glmm_top": CONTROL["glmm_top"]}, "benchmarks": {}}
    for b, (data, lengths) in inputs.items():
        copies = copies_by_bench[b]
        check_answers(b, data, copies)
        models, items, projects = data["models"], data["items"], data["projects"]
        copies = {k: v for k, v in copies.items() if k[0] in models}
        flags = flags_of(models, items, copies)
        y = scores(data)
        sizes = data["conditions"][1:]
        pos = {i: j for j, i in enumerate(items)}
        text_mean = [mean([y[m]["text"][j] for m in models]) for j in range(len(items))]
        q, t = CONTROL["bins"]
        rate_bin = equal_groups(text_mean, items, q)
        check_lengths(b, items, lengths)
        len_bin = equal_groups([lengths[i] for i in items], items, t)
        bins = [(rate_bin[j], len_bin[j]) for j in range(len(items))]
        out = {"copy_answers": sum(copies.values()),
               "copied_items": len({i for (_, i, _), v in copies.items() if v}),
               "flagged": {name(m): len(flags[m]) for m in models}, "gaps": [], "control": {}}
        for m in models:
            keep = [j for j, i in enumerate(items) if i not in flags[m]]
            for label, cond in [("mean", sizes)] + [(s, s) for s in sizes]:
                d = differences(y[m], cond, "text")
                full = st.cluster_t(d, projects)
                row = test_row(m, [d[j] for j in keep], [projects[j] for j in keep],
                               gap=label, removed=len(items) - len(keep))
                row["all_items"] = full["est"]
                out["gaps"].append(row)
            d = differences(y[m], sizes, "text")
            flagged = [pos[i] for i in flags[m]]
            if not flagged:
                out["control"][name(m)] = None
                continue
            base = mean(d)
            observed = mean([d[j] for j in keep]) - base
            pool = set(keep)
            draws, short = matched_removals(flagged, bins, pool, n_draws, f"{seed}-{b}-{m}")
            total = math.fsum(d)
            changes = sorted((total - math.fsum(d[j] for j in dr)) / (len(d) - len(dr)) - base
                             for dr in draws)
            out["control"][name(m)] = {
                "observed_change": observed, "lo": rel.quantile(changes, 0.025),
                "hi": rel.quantile(changes, 0.975),
                "share_at_or_below": sum(c <= observed for c in changes) / len(changes),
                "flagged": len(flagged), "removed_per_draw": len(draws[0]), "shortfall": short}
        if b not in modes:
            raise ValueError(f"{b}: no item:model modes; run analysis/glmm_main.R first")
        out["flag2"] = flag2_overlap(models, items, modes[b], flags)
        out["flag_rows"] = sorted((b, i, mm, r) for (mm, i, r), v in copies.items() if v)
        rep["benchmarks"][b] = out
    adjust([r for v in rep["benchmarks"].values() for r in v["gaps"]], "bh", "bh")
    return rep


def contamination(args):
    cfg = config.load()
    modes = read_item_modes(os.path.join(args.out, "glmm_item_model.csv"))
    inputs = read_inputs(cfg, args.full)
    copies = {b: text_copies(b, args.answers) for b in inputs}
    rep = contamination_report(inputs, copies, modes)
    rows = [r for v in rep["benchmarks"].values() for r in v.pop("flag_rows")]
    write_json(os.path.join(args.out, "contamination.json"), rep)
    path = os.path.join(args.out, "contamination_flags.csv")
    gc.write_csv(path, FLAG_FIELDS, rows)
    print(path)


REPORT_INPUTS = {"gaps.json": "scripts/analysis.py gaps",
                 "glmm.json": "analysis/glmm_main.R",
                 "contamination.json": "scripts/analysis.py contamination"}
# bias of the size-averaged logit penalty toward 0 in the UFM-21 simulation
# (results/glmm/glmm.md, decisions 2026-11-13)
LOGIT_BIAS = (0.03, 0.13)
BENCH_TITLES = {"coderujb": "CoderUJB", "deveval": "DevEval"}


def pp(x, sign=True):
    """A fraction as percentage points with one decimal."""
    if x is None:
        return "n/a"
    return f"{100 * x:+.1f}" if sign else f"{100 * x:.1f}"


def num(x, digits=3):
    return "n/a" if x is None else f"{x:.{digits}f}"


def pval(p):
    return "n/a" if p is None else f"{p:.3g}"


def interval(lo, hi, fmt=pp):
    return "n/a" if lo is None else f"[{fmt(lo)}, {fmt(hi)}]"


def md_table(header, rows):
    out = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    out += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return out + [""]


def gap_cells(r):
    c = r["cluster"]
    return [pp(r["est"]), interval(c["lo"], c["hi"]), pval(c["p"])]


def read_report_inputs(out):
    got = {}
    for f, cmd in REPORT_INPUTS.items():
        path = os.path.join(out, f)
        if not os.path.exists(path):
            raise ValueError(f"{path} is missing: run {cmd} first")
        with open(path, encoding="utf-8") as fh:
            got[f.split(".")[0]] = json.load(fh)
    return got


def main_table(g, gl):
    contrast = {name(r["model"]): r for r in gl["contrast"]}
    rows = []
    for r in g["main"]:
        m, c, it = r["model"], r["cluster"], r["item"]
        lg = contrast.get(m)
        rows.append([m, pp(g["rates"]["text"][m], False), pp(r["est"]),
                     interval(c["lo"], c["hi"]), pval(r["holm"]), interval(it["lo"], it["hi"]),
                     num(lg["est"], 2) if lg else "n/a",
                     interval(lg["lo"], lg["hi"], lambda x: num(x, 2)) if lg else "n/a",
                     num(g["token_ratio"][m]["mean_over_sizes"], 2)])
    p = g["pooled"]
    rows.append(["Mean of models", "", pp(p["est"]), interval(p["lo"], p["hi"]), "", "", "", "",
                 ""])
    return md_table(["Model", "Text %", "Gap pp", "Cluster 95% CI", "Holm p", "Item-level CI",
                     "Logit contrast", "Logit 95% CI", "Token ratio"], rows)


def gaps_sections(b, g, gl):
    conds = list(g["rates"])
    models = [r["model"] for r in g["main"]]
    out = [f"### {BENCH_TITLES.get(b, b)}", "",
           (f"{g['n_items']} items in {g['n_clusters']} clusters. No item is dropped: the grid check "
           "fails on any missing cell, so counting dropped items as failures changes nothing."), ""]
    out += main_table(g, gl)
    out += ["Rates by condition (%), item-weighted, with the rank in brackets:", ""]
    out += md_table(["Model"] + conds,
                    [[m] + [f"{pp(g['rates'][c][m], False)} ({g['ranks'][c][m]:g})" for c in conds]
                     for m in models])
    out += ["Gap per image size (BH over the per-size family):", ""]
    out += md_table(["Model", "Size", "Gap pp", "Cluster 95% CI", "p", "BH p"],
                    [[r["model"], r["size"]] + gap_cells(r) + [pval(r["bh"])] for r in g["sizes"]])
    out += ["Differences between sizes (BH over the size-difference family):", ""]
    out += md_table(["Model", "Pair", "Diff pp", "Cluster 95% CI", "p", "BH p"],
                    [[r["model"], r["pair"]] + gap_cells(r) + [pval(r["bh"])]
                     for r in g["size_diffs"]])
    out += ["Prompt tokens, run 0, median [q1, q3], and the median per-item ratio to text:", ""]
    sizes = [c for c in conds if c not in ("text", "image")]
    out += md_table(["Model"] + [c for c in conds if c != "image"] + [f"ratio {s}" for s in sizes],
                    [[m] + [f"{t['median']:g} [{t['q1']:g}, {t['q3']:g}]"
                            for t in g["tokens"][m].values()]
                     + [num(g["token_ratio"][m][s], 2) for s in sizes] for m in models])
    if g["lopo"]:
        out += ["Leave one project out (gap over sizes without that project):", ""]
        out += md_table(["Model", "Left out", "Items", "Gap pp", "Cluster 95% CI", "p"],
                        [[r["model"], r["left_out"], r["n"]] + gap_cells(r) for r in g["lopo"]])
    out += [("Context length (exploratory; buckets of Qwen3.5 text tokens, [lo, hi); BH over the "
            "length family):"), ""]
    out += md_table(["Model", "Size", "Bucket", "Items", "Gap pp", "Cluster 95% CI", "p", "BH p"],
                    [[r["model"], r["size"], r["bucket"], r["n"]] + gap_cells(r) + [pval(r["bh"])]
                     for r in g["length"]])
    out += ["Floor and ceiling: share of items (%) with no run passing / every run passing:", ""]
    fc = g["floor_ceiling"]
    out += md_table(["Model"] + [c for c in conds if c != "image"],
                    [[m] + [f"{pp(v['none'], False)} / {pp(v['all'], False)}"
                            for v in fc[m].values()] for m in models])
    out += md_table(["Condition", "Every model passes %", "No model passes %"],
                    [[c, pp(v["all_models_pass"], False), pp(v["no_model_passes"], False)]
                     for c, v in g["all_none"].items()])
    out += [(f"{g['never_passed']} items pass in no condition for any model "
            "(`never_passed.csv`)."), "",
            "Scoring shares (%): empty / truncated / no code"
            + (" / no def line of the target" if b == "deveval" else "") + ":", ""]
    keys = ["empty", "truncated", "no_code"] + (["no_def_line"] if b == "deveval" else [])
    out += md_table(["Model"] + [c for c in conds if c != "image"],
                    [[m] + [" / ".join(pp(v[k], False) for k in keys)
                            for v in g["scoring"][m].values()] for m in models])
    return out


def glmm_sections(b, v):
    out = [f"### {BENCH_TITLES.get(b, b)}", "",
           (f"{v['n_cells']} cells, {v['n_items']} items, {v['n_clusters']} clusters, "
           f"log-likelihood {num(v['loglik'], 1)}."), ""]
    out += md_table(["Term", "SD (logit)", "SD (probit)"],
                    [[t, num(s), num(v["probit"]["sd"][t])] for t, s in v["sd"].items()])
    w, ic, lrt, ho = v["wald"], v["item_condition_sd"], v["lrt"], v["heldout"]
    out += [(f"- Equal contrasts across models (Wald): chi2 {num(w['stat'], 2)} on {w['df']} df, "
            f"p {pval(w['p'])}."),
            (f"- item:condition SD {num(ic['est'])}, 95% CI {interval(ic['lo'], ic['hi'], num)} "
            f"({ic['method']})."),
            (f"- LRT against no item:condition: {num(lrt['stat'], 2)} on {lrt['df']} df, halved p "
            f"{pval(lrt['p'])}."),
            f"- Held-out log-likelihood ({len(ho['folds'])} folds of whole clusters, "
            f"{ho['integration']}): full {num(ho['full'], 1)}, without item:condition "
            f"{num(ho['reduced'], 1)}, difference {num(ho['diff'], 1)} (SE {num(ho['se'], 1)})"
            + ("; some folds did not converge" if ho["partial"] else "") + ". Per fold, full "
            "minus reduced: " + ", ".join(num(f["full"] - f["reduced"], 1) for f in ho["folds"]
                                         if f["converged"])
            + ". Folds hold unequal numbers of clusters and items, so the SE, which treats them as "
            "exchangeable, is a rough guide.",
            (f"- SD of item:condition over SD of item: logit {num(v['probit']['ratio_logit'])}, "
            f"probit {num(v['probit']['ratio_probit'])}."),
            (f"- Item flags: {v['item_flags']['bh_flagged']} of {v['item_flags']['n']} "
            "item:condition modes with BH p < 0.05; "
            f"{v['item_flags']['raw_ci_excludes_zero']} with a raw 95% interval excluding 0."),
            "- Built-in checks: " + ", ".join(f"({k}) {'ok' if c['ok'] else 'FAILED'}"
                                              for k, c in v["checks"].items()) + ".", ""]
    out += [("Item-logit correlations against the one-ability reference (simulated 2.5% to 97.5% "
            "and the percentile of the observed value). C = mean size-size minus mean text-size "
            "correlation:"), ""]
    rows = []
    for method, pairs in v["correlation"].items():
        rows += [[method, k, num(x["observed"]), interval(x["lo"], x["hi"], num),
                  num(x["percentile"])] for k, x in pairs.items()]
    out += md_table(["Method", "Pair", "Observed", "Reference", "Percentile"], rows)
    out += ["Common slope of image logits (run 1) on text logits (run 0):", ""]
    out += md_table(["Size", "Slope", "R^2", "Text run 0-1 r", "Slope / r"],
                    [[s, num(x["slope"]), num(x["r2"]), num(x["text_run_correlation"]),
                      num(x["corrected"])] for s, x in v["common_slope"].items()])
    return out


def contamination_sections(b, v, top):
    out = [f"### {BENCH_TITLES.get(b, b)}", "",
           (f"{v['copy_answers']} text answers copy the reference exactly, on "
           f"{v['copied_items']} items."), ""]
    out += md_table(["Model", "Gap", "Removed", "All items pp", "Without flagged pp",
                     "Cluster 95% CI", "BH p"],
                    [[r["model"], r["gap"], r["removed"], pp(r["all_items"]), pp(r["est"]),
                      interval(r["cluster"]["lo"], r["cluster"]["hi"]), pval(r["bh"])]
                     for r in v["gaps"]])
    rows = []
    for m, c in v["control"].items():
        if c is None:
            rows.append([m, "nothing flagged", "", "", "", ""])
            continue
        short = ", ".join(f"bin {k} short by {n}" for k, n in c["shortfall"].items())
        rows.append([m, pp(c["observed_change"]), interval(c["lo"], c["hi"]),
                     num(c["share_at_or_below"]), f"{c['removed_per_draw']} of {c['flagged']}",
                     short or "none"])
    out += [("Matched random removal (change of the mean-over-sizes gap when the same number of "
             "unflagged items is removed per bin). Where a bin has fewer unflagged items than "
             "flagged ones, a draw removes all it has, so it removes fewer items than the flag "
             "and its range sits closer to 0 than a full match would:"), ""]
    out += md_table(["Model", "Observed change pp", "Random 95% range", "Share <= observed",
                     "Removed per draw", "Bins short of items"], rows)
    out += [(f"Copy flag against the GLMM flag (item:model mode in the model's top "
            f"{100 * top:g}%):"), ""]
    out += md_table(["Model", "Both", "Copy only", "GLMM only", "Neither"],
                    [[m, x["both"], x["copy_only"], x["glmm_only"], x["neither"]]
                     for m, x in v["flag2"].items()])
    return out


def findings(inputs):
    g, gl, c = inputs["gaps"], inputs["glmm"], inputs["contamination"]
    s = g["settings"]
    out = ["# Main analysis findings", "",
           ("Generated by `uv run python scripts/analysis.py report` from gaps.json, glmm.json and "
           "contamination.json; edit the scripts, not this file."), "",
           f"Models: {', '.join(s['models'])}. Gap = image minus text, mean over the image "
           "sizes, in percentage points. Intervals: " + s["interval"] + f"; Holm over the "
           f"{sum(len(v['main']) for v in g['benchmarks'].values())} main gaps. The mean of models "
           f"uses {s['pooled_interval']} of {s['n_boot']} joint cluster draws.", "",
           ("The logit contrast (GLMM, mean over sizes of the image-text difference in fixed "
           f"effects) is biased toward 0 by {LOGIT_BIAS[0]} to {LOGIT_BIAS[1]} logit in the "
           "UFM-21 simulation."), "",
           "## Gaps", ""]
    for b, v in g["benchmarks"].items():
        out += gaps_sections(b, v, gl["benchmarks"].get(b, {"contrast": []}))
    out += ["## GLMM", "", (f"`{gl['settings']['formula']}`, glmmTMB {gl['settings']['glmmTMB']}, "
            f"R {gl['settings']['R']}."), ""]
    for b, v in gl["benchmarks"].items():
        out += glmm_sections(b, v)
    out += ["## Contamination", "",
            ("An item is flagged for model m when another model copies the reference token for "
            "token in a text run. This is a sensitivity check, not a corrected gap. "
            f"{c['settings']['control_draws']} matched random removals per model."), ""]
    for b, v in c["benchmarks"].items():
        out += contamination_sections(b, v, c["settings"]["glmm_top"])
    return "\n".join(out).rstrip("\n") + "\n"


def report(args):
    text = findings(read_report_inputs(args.out))
    path = os.path.join(args.out, "findings.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    print(path)


# slots 1 to 5 of the dataviz reference palette (light), and its text inks
SERIES = ("#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4")
INK, INK2, GRID = "#0b0b0b", "#52514e", "#d9d8d4"
WIDTH = 5.5


def _pyplot():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"font.family": "serif", "font.size": 9, "pdf.fonttype": 42,
                         "axes.edgecolor": INK2, "axes.labelcolor": INK, "xtick.color": INK2,
                         "ytick.color": INK2, "text.color": INK, "axes.spines.top": False,
                         "axes.spines.right": False, "svg.hashsalt": "analysis"})
    return plt


def _save(fig, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fig.savefig(path, metadata={"CreationDate": None, "ModDate": None, "Producer": None,
                                "Creator": None})
    print(path)


def figures(rep, out_dir):
    plt = _pyplot()
    benches = list(rep["benchmarks"])
    models = rep["settings"]["models"]
    scale = 100

    fig, axes = plt.subplots(1, len(benches), figsize=(WIDTH, 0.45 * len(models) + 1.1),
                             sharey=True)
    for ax, b in zip(axes, benches):
        v = rep["benchmarks"][b]
        sizes = sorted({r["size"] for r in v["sizes"]}, key=lambda s: int(s[5:]))
        for k, r in enumerate(v["main"]):
            yk = len(models) - 1 - k
            c = r["cluster"]
            ax.plot([c["lo"] * scale, c["hi"] * scale], [yk, yk], color=INK, lw=1.5,
                    solid_capstyle="round")
            ax.plot(r["est"] * scale, yk, "o", color=INK, ms=6)
            for q, s in enumerate(sizes):
                g = next(x for x in v["sizes"] if x["model"] == r["model"] and x["size"] == s)
                ax.plot(g["est"] * scale, yk + 0.22, "o", color=SERIES[q], ms=4,
                        label=f"{s[5:]} px" if k == 0 else None)
        ax.axvline(0, color=GRID, lw=1, zorder=0)
        ax.set_title(ds.TITLES.get(b, b), fontsize=9)
        ax.set_xlabel("Image minus text (points)")
        ax.set_yticks(range(len(models)))
        ax.set_yticklabels(list(reversed(models)))
        ax.tick_params(axis="y", length=0)
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, frameon=False, fontsize=8, loc="lower center", ncol=len(labels),
               handletextpad=0.2)
    fig.tight_layout(rect=(0, 0.07, 1, 1))
    _save(fig, os.path.join(out_dir, "main_gap.pdf"))
    plt.close(fig)

    fig, axes = plt.subplots(1, len(benches), figsize=(WIDTH, 2.6), sharey=True)
    for ax, b in zip(axes, benches):
        v = rep["benchmarks"][b]
        for k, m in enumerate(models):
            rows = [r for r in v["sizes"] if r["model"] == m]
            rows.sort(key=lambda r: int(r["size"][5:]))
            xs = [v["token_ratio"][m][r["size"]] for r in rows]
            ax.plot(xs, [r["est"] * scale for r in rows], "-o", color=SERIES[k % len(SERIES)],
                    lw=2, ms=4, label=m)
            for x, r in zip(xs, rows):
                ax.plot([x, x], [r["cluster"]["lo"] * scale, r["cluster"]["hi"] * scale],
                        color=SERIES[k % len(SERIES)], lw=1, alpha=0.6)
        ax.axhline(0, color=GRID, lw=1, zorder=0)
        ax.set_title(ds.TITLES.get(b, b), fontsize=9)
        ax.set_xlabel("Image / text prompt tokens (median)")
    axes[0].set_ylabel("Image minus text (points)")
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, frameon=False, fontsize=8, loc="lower center",
               ncol=min(len(models), 3))
    fig.tight_layout(rect=(0, 0.16, 1, 1))
    _save(fig, os.path.join(out_dir, "size_curve.pdf"))
    plt.close(fig)


COMMANDS = {"gaps": gaps, "prep": prep, "contamination": contamination, "report": report}


def main(argv=None):
    ap = argparse.ArgumentParser(description="Main analysis of the full answer table")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("gaps")
    p.add_argument("--full", default=FULL)
    p.add_argument("--out", default=OUT)
    p = sub.add_parser("prep")
    p.add_argument("--full", default=FULL)
    p.add_argument("--scratch", default=os.path.join(ROOT, "scratch", "analysis"))
    p = sub.add_parser("contamination")
    p.add_argument("--answers", required=True,
                   help="text answers and references copied from the cluster")
    p.add_argument("--full", default=FULL)
    p.add_argument("--out", default=OUT)
    p = sub.add_parser("report")
    p.add_argument("--out", default=OUT)
    args = ap.parse_args(argv)
    try:
        COMMANDS[args.cmd](args)
    except (ValueError, OSError) as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
