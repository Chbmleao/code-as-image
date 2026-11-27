"""Main analysis of the full answer table (methodology 3.3).

  gaps           the paired image-text gap per model (delta_mb, mean over sizes) with the
                 clustered and item-level t intervals and Holm, the pooled gap with its joint
                 cluster resample interval, the per-size gaps and size differences (BH), prompt
                 tokens and the token ratio, leave-one-project-out, context length buckets, floor
                 and ceiling shares, scoring shares and ranks. Writes <out>/gaps.json,
                 <out>/never_passed.csv and <out>/figures/{main_gap,size_curve}.pdf. With
                 --models claude: the Claude models' own gaps (methodology addendum) with their
                 own Holm and BH families and the gaps without contamination-flagged items;
                 writes <out>/gaps.json only.
  replies        Claude only: refusals, stop reasons, over_budget, thinking share, non-thinking
                 output tokens and cache tokens per model and condition, from the Claude run
                 directory. Writes <out>/replies.json.
  prep           writes <scratch>/<b>_answers.csv (model, item, project, condition, run, passed)
                 for analysis/glmm_main.R.
  contamination  flags (model, item) when another model copies the reference in a text run, and
                 compares the gaps with and without the flagged items against a matched random
                 removal. Writes <out>/contamination.json and <out>/contamination_flags.csv.
  report         writes <out>/findings.md from gaps.json, glmm.json and contamination.json. With
                 --models all: <out>/../findings.md, the Claude extension report, and
                 <out>/figures/{claude_gap,size_curve}.pdf.
  ranks          the 7-model line only: rates, ranks with their resample intervals and the text
                 vs image swap probability of each pair. Writes <out>/ranks.json.

usage: uv run python scripts/analysis.py gaps [--models main|claude] [--answers DIR] [--full DIR]
                                         [--claude-full DIR] [--out DIR]
       uv run python scripts/analysis.py replies --run-dir DIR [--claude-full DIR] [--out DIR]
       uv run python scripts/analysis.py prep [--models main|all] [--full DIR] [--claude-full DIR]
                                         [--scratch DIR]
       uv run python scripts/analysis.py contamination --answers DIR [--models main|all]
                                         [--full DIR] [--claude-full DIR] [--out DIR]
       uv run python scripts/analysis.py ranks [--full DIR] [--claude-full DIR] [--out DIR]
       uv run python scripts/analysis.py report [--models main|all] [--out DIR]

The models are those of configs/experiment.toml (CODEIMG_CONFIG overrides the path). `main`, the
default, is the [models] table and writes to results/analysis. `all` is the 7-model line of the
methodology addendum: [models] plus the [claude] models, runs 0 and 1 only for every model; its
results go to results/claude/analysis and its answers CSVs to scratch/analysis_all. In that line
contamination writes the copy flags only. `claude` (gaps only) is the [claude] models alone, and
also writes to results/claude/analysis. Gaps are image minus text, so a loss is negative. Every resample interval is 95%
equal-tailed from type-1 percentiles.
"""
import argparse
import functools
import importlib.util
import json
import math
import os
import random
import sys
from collections import Counter, defaultdict
from itertools import combinations

from codeimg.analysis import reliability as rel
from codeimg.analysis import stats as st

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ds, gc, ft, rs = rel.ds, rel.gc, rel.ft, rel.rs
config = ft.config

OUT = os.path.join(ROOT, "results", "analysis")
FULL = os.path.join(ROOT, "results", "full")
ALL_OUT = os.path.join(ROOT, "results", "claude", "analysis")
CLAUDE_FULL = os.path.join(ROOT, "results", "claude", "full")
SCRATCH = {"main": os.path.join(ROOT, "scratch", "analysis"),
           "all": os.path.join(ROOT, "scratch", "analysis_all")}
# the 7-model line uses runs 0 and 1 of every model, and Claude has 2 runs on every item
LINE_RUNS = 2
DROP_RULE = ("an item with a Claude cell short of 2 scored runs leaves the line in all four "
             "conditions for every model")
GRID_KEYS = ("missing", "extra", "duplicates", "null_passed", "seed_not_run")
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


@functools.cache
def _claude_names():
    claude = config.load().get("claude", {})
    return {v["model"]: v.get("name", v["model"]) for v in claude.values() if isinstance(v, dict)}


def name(m):
    return ds.NAMES[m] if m in ds.NAMES else _claude_names().get(m, m)


def claude_set(cfg):
    if "claude" not in cfg:
        raise ValueError("--models all or claude needs the [claude] table of the config")
    return [m["model"] for m in config.claude_models(cfg).values()]


def model_set(cfg, which="main"):
    """Model ids of the config: the established order first, then new ones in config order, and
    for `all` the [claude] models after them. `claude` is the [claude] models alone."""
    if which == "claude":
        return claude_set(cfg)
    repos = [m["repo"] for m in cfg["models"].values()]
    out = [m for m in ds.NAMES if m in repos] + [m for m in repos if m not in ds.NAMES]
    return out + claude_set(cfg) if which == "all" else out


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


def check_models(b, rows, models):
    have = Counter(r["model"] for r in rows)
    empty = [name(m) for m in models if not have[m]]
    if empty:
        raise ValueError(f"{b}: no rows for {', '.join(empty)}")


def check_grid(b, rows, expected, claude=False):
    """ft.check on one table. Claude rows carry no seed, since none is sent, and a request_error
    has no verdict, since it is left out of scoring; for them those two checks are narrowed."""
    got = ft.check(rows, expected)
    if claude:
        by_key = {r["key"]: r for r in rows}
        got["seed_not_run"] = [k for k in got["seed_not_run"] if by_key[k]["seed"] is not None]
        got["null_passed"] = [k for k in got["null_passed"]
                              if by_key[k]["reason"] != "request_error"]
    bad = {k: got[k][:3] for k in GRID_KEYS if got[k]}
    if bad:
        raise ValueError(f"{b}: rows do not match the expected grid: {bad}")


def load_benchmark(b, rows, items, models, conds, parts):
    """Checks rows against the expected grid and returns the cells of each model and condition:
    cells[m][c][j] is item j's passes by run, tokens[m][c][j] its run-0 prompt tokens."""
    check_models(b, rows, models)
    rows = [r for r in rows if r["model"] in models]
    check_grid(b, rows, ft.expected_keys(models, conds, parts))
    items, rows, gone = rel.drop_excluded(items, rows, rel.excluded(b))
    return {**build_cells(b, rows, items, models, conds), "excluded": gone}


def load_line(b, open_rows, claude_rows, items, cfg):
    """The 7-model line. Each table is checked against its own full grid, then every model keeps
    runs 0 and 1, and an item with a Claude cell short of LINE_RUNS scored runs leaves the line in
    every condition (DROP_RULE). The excluded items leave after the grid checks, before the
    DROP_RULE. rows keeps every checked row of the kept items, for the copy check."""
    conds = conditions(cfg)
    opens, claude = model_set(cfg), claude_set(cfg)
    models = opens + claude
    rows = [r for r in open_rows + claude_rows if r["model"] in models]
    check_models(b, rows, models)
    check_grid(b, [r for r in rows if r["model"] in opens],
               ft.expected_keys(opens, conds, grid_parts(b, cfg, opens)))
    ids = [i for i, _, _ in items]
    check_grid(b, [r for r in rows if r["model"] in claude],
               ft.expected_keys(claude, conds, [(ids, dict.fromkeys(claude, LINE_RUNS))]),
               claude=True)
    items, rows, excluded = rel.drop_excluded(items, rows, rel.excluded(b))
    ids = [i for i, _, _ in items]
    scored = [r for r in rows if r["run"] < LINE_RUNS and r["passed"] is not None]
    n = Counter((r["model"], r["condition"], r["id"]) for r in scored)
    dropped = [i for i in ids if any(n[(m, c, i)] < LINE_RUNS for m in claude for c in conds)]
    gone = set(dropped)
    keep = [it for it in items if it[0] not in gone]
    if len(keep) < 2:
        raise ValueError(f"{b}: {len(keep)} item(s) left after dropping {len(dropped)} with a "
                         "short Claude cell")
    data = build_cells(b, [r for r in scored if r["id"] not in gone], keep, models, conds)
    data.update(rows=rows, all_items=ids, dropped=dropped, excluded=excluded)
    return data


def load_claude(b, rows, items, cfg):
    """The Claude table on its own, 2 runs on every item. A cell short of 2 scored runs stops,
    since the addendum's per-condition drop is not built: the collected tables have none."""
    conds, models = conditions(cfg), claude_set(cfg)
    rows = [r for r in rows if r["model"] in models]
    check_models(b, rows, models)
    ids = [i for i, _, _ in items]
    check_grid(b, rows, ft.expected_keys(models, conds, [(ids, dict.fromkeys(models, LINE_RUNS))]),
               claude=True)
    items, rows, gone = rel.drop_excluded(items, rows, rel.excluded(b))
    short = sorted({(r["model"], r["condition"], r["id"]) for r in rows if r["passed"] is None})
    if short:
        m, c, i = short[0]
        raise ValueError(f"{b}: {len(short)} Claude cell(s) short of {LINE_RUNS} scored runs, "
                         f"first {name(m)} {c} {i}")
    return {**build_cells(b, rows, items, models, conds), "excluded": gone}


def build_cells(b, rows, items, models, conds):
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


def output_lengths(data):
    """Output tokens per model and condition over every answer. Shorter answers under image input
    are the main cause of the gap in Reading, Not Thinking (arXiv 2603.09095)."""
    toks = defaultdict(list)
    for r in data["rows"]:
        toks[(r["model"], r["condition"])].append(r["output_tokens"])
    return {name(m): {c: {**spread(toks[(m, c)]), "mean": mean(toks[(m, c)])}
                      for c in data["conditions"]} for m in data["models"]}


def benchmark_gaps(data, lengths, buckets, seed, n_boot):
    b, models, conds = data["benchmark"], data["models"], data["conditions"]
    sizes = conds[1:]
    items, projects = data["items"], data["projects"]
    y = scores(data)
    groups = ds.clusters(b, items, dict(zip(items, projects)))
    out = {"n_items": len(items), "n_clusters": len(groups),
           "excluded": {"count": len(data["excluded"]), "items": data["excluded"]}}

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
    out["output_tokens"] = output_lengths(data)
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


CLAUDE_DROPPED = ("pooled", "ranks", "length", "all_none", "never_passed", "output_tokens")
CLAUDE_BH = "the per-size gaps, the size differences and the gaps without flagged items"


def token_ratio_mean(data):
    """The item mean of image over text prompt tokens (run 0), the addendum's wording."""
    tok, sizes = data["tokens"], data["conditions"][1:]
    out = {}
    for m in data["models"]:
        r = {s: mean([a / t for a, t in zip(tok[m][s], tok[m]["text"])]) for s in sizes}
        r["mean_over_sizes"] = mean([r[s] for s in sizes])
        out[name(m)] = r
    return out


def claude_contamination(b, data, lengths, copies, seed, n_draws):
    """copies holds the text runs of all seven models, so a Claude model's flag comes from any
    other model, the other Claude model included. A model's own copies never flag it and are
    counted apart."""
    check_answers(b, data, copies)
    models = data["models"]
    flags = flags_of(models, data["items"], copies)
    own = {name(m): {"answers": sum(v for (mm, _, _), v in copies.items() if mm == m),
                     "items": len({i for (mm, i, _), v in copies.items() if mm == m and v})}
           for m in models}
    return {"flagged": {name(m): len(flags[m]) for m in models}, "own_copies": own,
            **removal_checks(b, data, lengths, flags, seed, n_draws)}


def claude_gaps_report(cfg, inputs, copies_by_bench, seed=rs.SEED, n_boot=rs.N_BOOT,
                       control_seed=CONTROL_SEED, n_draws=None):
    """The Claude models' own gaps (methodology addendum): Holm over their size-averaged gaps and
    one BH set over CLAUDE_BH, apart from the 5-model families. inputs[b] is the load_claude
    output and the item lengths; copies_by_bench[b] the text copies of every model."""
    n_draws = n_draws or CONTROL["draws"]
    buckets = cfg["sample"]["deveval_buckets"]
    seven = set(model_set(cfg, "all"))
    rep = {"settings": {"models": [name(m) for m in model_set(cfg, "claude")],
                        "runs": list(range(LINE_RUNS)), "seed": seed, "n_boot": n_boot,
                        "level": st.LEVEL,
                        "interval": "CR1 cluster t with G - 1 df; item line: paired t",
                        "short_cell": "stops the command",
                        "token_ratio": ("median per-item ratio, as the open models; "
                                        "token_ratio_mean is the item mean"),
                        "control_draws": n_draws, "control_seed": control_seed,
                        "bins": CONTROL["bins"]},
           "benchmarks": {}}
    for b, (data, lengths) in inputs.items():
        v = benchmark_gaps(data, lengths, buckets, f"{seed}-{b}", n_boot)
        for k in CLAUDE_DROPPED:
            del v[k]
        v["token_ratio_mean"] = token_ratio_mean(data)
        errors = Counter((r["model"], r["condition"]) for r in data["rows"]
                         if r["reason"] == "request_error")
        v["request_errors"] = {name(m): {c: errors[(m, c)] for c in data["conditions"]}
                               for m in data["models"]}
        copies = {k: x for k, x in copies_by_bench[b].items() if k[0] in seven}
        v["contamination"] = claude_contamination(b, data, lengths, copies, f"{control_seed}-{b}",
                                                  n_draws)
        rep["benchmarks"][b] = v
    found = rep["benchmarks"].values()
    adjust([r for v in found for r in v["main"]], "holm", "holm")
    family = ([r for k in ("sizes", "size_diffs") for v in found for r in v[k]]
              + [r for v in found for r in v["contamination"]["gaps"]])
    adjust(family, "bh", "bh")
    rep["settings"]["holm_rows"] = sum(len(v["main"]) for v in found)
    rep["settings"]["bh_set"] = {"rows": len(family), "covers": CLAUDE_BH}
    return rep


def read_inputs(cfg, full, benches=ds.BENCHES):
    models, conds = model_set(cfg), conditions(cfg)
    out = {}
    for b in benches:
        rows = ds.read_jsonl(os.path.join(full, f"{b}.collected.jsonl"))
        data = load_benchmark(b, rows, rel.design(b), models, conds, grid_parts(b, cfg, models))
        out[b] = (data, read_lengths(b))
    return out


def read_claude(cfg, claude_full, benches=ds.BENCHES):
    return {b: (load_claude(b, ds.read_jsonl(os.path.join(claude_full, f"{b}.collected.jsonl")),
                            rel.design(b), cfg), read_lengths(b))
            for b in benches}


def read_line(cfg, full, claude_full, benches=ds.BENCHES):
    return {b: load_line(b, ds.read_jsonl(os.path.join(full, f"{b}.collected.jsonl")),
                         ds.read_jsonl(os.path.join(claude_full, f"{b}.collected.jsonl")),
                         rel.design(b), cfg)
            for b in benches}


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
    if args.models == "claude":
        inputs = read_claude(cfg, args.claude_full)
        copies = {b: text_copies(b, args.answers, ("block1", "rest", "claude")) for b in inputs}
        write_json(os.path.join(args.out, "gaps.json"), claude_gaps_report(cfg, inputs, copies))
        return
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
    if args.models == "all":
        inputs = read_line(cfg, args.full, args.claude_full)
    else:
        inputs = {b: data for b, (data, _) in read_inputs(cfg, args.full).items()}
    for b, data in inputs.items():
        out = answer_rows(data)
        path = os.path.join(args.scratch, f"{b}_answers.csv")
        gc.write_csv(path, rel.ANSWER_FIELDS, out)
        print(f"{path}: {len(out)} answers"
              + (f", {len(data['dropped'])} item(s) dropped" if "dropped" in data else ""))


def ranks_report(line, seed=rs.SEED, n_boot=None):
    """Rates, ranks with resample intervals and pair swap probabilities of the 7-model line, from
    the reliability code and the scripts/resample.py draws, keyed by display name."""
    n_boot = n_boot or rs.N_BOOT
    models = next(iter(line.values()))["models"]
    rep = {"settings": {"models": [name(m) for m in models], "runs": list(range(LINE_RUNS)),
                        "drop_rule": DROP_RULE, "seed": seed, "n_boot": n_boot,
                        "interval": "95% equal-tailed, type-1 percentiles"},
           "benchmarks": {}}
    for b, data in line.items():
        items, projects = data["items"], data["projects"]
        groups = ds.clusters(b, items, dict(zip(items, projects)))
        res = rel.rank_stability(data, groups, f"{seed}-{b}", n_boot)
        shown = {rel.name(m): name(m) for m in models}
        rep["benchmarks"][b] = {
            "n_items": len(items), "n_clusters": len(groups),
            "dropped": {"count": len(data["dropped"]), "items": data["dropped"]},
            "excluded": {"count": len(data["excluded"]), "items": data["excluded"]},
            "rates": {c: {shown[k]: v for k, v in x.items()} for c, x in res["rates"].items()},
            "ranks": {c: {shown[k]: v for k, v in x.items()} for c, x in res["ranks"].items()},
            "swap": [{"pair": [shown[k] for k in s["pair"]], "p": s["p"]} for s in res["swap"]]}
    return rep


def ranks(args):
    rep = ranks_report(read_line(config.load(), args.full, args.claude_full))
    write_json(os.path.join(args.out, "ranks.json"), rep)


def reply_cell():
    return {"replies": 0, "request_errors": 0, "refusals": Counter(), "max_tokens": 0,
            "over_budget": 0, "other_stops": Counter(), "thinking": 0, "output": 0,
            "with_thinking": 0, "plain": [], "cache_creation_tokens": 0, "cache_read_tokens": 0}


def replies_report(cfg, run_dir, collected, benches=ds.BENCHES):
    """Per Claude model, benchmark and condition, from the run directory: each gen row joined on
    (benchmark, id, condition, run) to its one succeeded result in the run log, which holds the
    stop reason and the usage. collected[b] is the Claude collected table, which the gen rows must
    match key for key. Output tokens here leave thinking out."""
    conds = conditions(cfg)
    rep = {"settings": {"models": [name(m) for m in claude_set(cfg)],
                        "output_tokens": "output_tokens minus thinking_tokens, per reply",
                        "thinking_share": "thinking tokens over output tokens, summed"},
           "benchmarks": {b: {} for b in benches}}
    for short, settings in config.claude_models(cfg).items():
        model = settings["model"]
        results = defaultdict(list)
        for r in ds.read_jsonl(os.path.join(run_dir, "claude", f"{short}.log.jsonl")):
            if r["kind"] == "result":
                results[tuple(r["key"])].append(r)
        for b in benches:
            gen = ds.read_jsonl(os.path.join(run_dir, b, "gen", f"claude_{short}.jsonl"))
            col = {(r["id"], r["condition"], r["run"]): r for r in collected[b]
                   if r["model"] == model}
            keys = Counter((g["id"], g["condition"], g["run"]) for g in gen)
            if keys != Counter(col.keys()):
                raise ValueError(f"{b}: the gen rows of {name(model)} ({len(gen)}) do not match "
                                 f"its collected rows ({len(col)}) key for key")
            cells = defaultdict(reply_cell)
            for g in gen:
                k = (b, g["id"], g["condition"], g["run"])
                reason = col[k[1:]]["reason"]
                if g["fail_reason"] is not None and g["fail_reason"] != reason:
                    raise ValueError(f"{b}: {k}: gen fail_reason {g['fail_reason']} but the "
                                     f"collected reason is {reason}")
                done = [r for r in results[k] if r["type"] == "succeeded"]
                cell = cells[g["condition"]]
                cell["replies"] += 1
                if g["fail_reason"] == "request_error":
                    if done:
                        raise ValueError(f"{b}: {k} is a request_error with a succeeded result")
                    cell["request_errors"] += 1
                    continue
                if len(done) != 1:
                    raise ValueError(f"{b}: {k} has {len(done)} succeeded results in the run log")
                res = done[0]
                u, stop = res["usage"], res["stop_reason"]
                if u["thinking_tokens"] is None:
                    raise ValueError(f"{b}: {k}: no thinking_tokens in the usage")
                if stop == "refusal":
                    cell["refusals"][(res["stop_details"] or {}).get("category") or "none"] += 1
                elif stop == "max_tokens":
                    cell["max_tokens"] += 1
                elif stop != "end_turn":
                    cell["other_stops"][stop] += 1
                cell["over_budget"] += g["fail_reason"] == "over_budget"
                cell["thinking"] += u["thinking_tokens"]
                cell["output"] += u["output_tokens"]
                cell["with_thinking"] += u["thinking_tokens"] > 0
                cell["plain"].append(u["output_tokens"] - u["thinking_tokens"])
                cell["cache_creation_tokens"] += u["cache_creation_input_tokens"] or 0
                cell["cache_read_tokens"] += u["cache_read_input_tokens"] or 0
            stopped = sum(c["max_tokens"] for c in cells.values())
            truncated = sum(bool(r["truncated"]) for r in col.values())
            if stopped != truncated:
                raise ValueError(f"{b}: {name(model)} has {stopped} replies at max_tokens but "
                                 f"{truncated} truncated collected rows")
            out = {}
            for c in conds:
                x = cells[c]
                plain = x.pop("plain")
                thinking, output = x.pop("thinking"), x.pop("output")
                out[c] = {**x, "refusals": dict(x["refusals"]),
                          "other_stops": dict(x["other_stops"]),
                          "thinking_share": thinking / output if output else None,
                          "output_tokens": {**spread(plain), "mean": mean(plain)}}
            rep["benchmarks"][b][name(model)] = out
    return rep


def replies(args):
    collected = {b: ds.read_jsonl(os.path.join(args.claude_full, f"{b}.collected.jsonl"))
                 for b in ds.BENCHES}
    rep = replies_report(config.load(), args.run_dir, collected)
    write_json(os.path.join(args.out, "replies.json"), rep)


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


def text_copies(b, answers_dir, parts=("block1", "rest")):
    """{(model, item, run): exact copy?} over the text answers of each part (block 1 and the rest;
    `claude` for the Claude replies), without the excluded items."""
    cont = _contamination_module()
    gone = set(rel.excluded(b))
    out = {}
    for part in parts:
        path = os.path.join(answers_dir, f"{part}_{b}_text.jsonl")
        if not os.path.exists(path):
            raise ValueError(f"{path} is missing")
        pairs = (cont.deveval_pairs(path, os.path.join(answers_dir, "deveval_gold.jsonl"))
                 if b == "deveval" else
                 cont.coderujb_pairs(path, os.path.join(answers_dir, "coderujb_items.jsonl")))
        for key, model, item, ans, ref in pairs:
            condition, run = run_of(key)
            if condition != "text":
                raise ValueError(f"{path}: {key} is not a text answer")
            if item not in gone:
                out[(model, item, run)] = ans == ref
    return out


def check_answers(b, data, copies):
    """Every graded text answer of the table must have its reply; no_code, no_reply and
    request_error answers have none and count as no copy. So do Claude replies that fail before
    grading (refusal, over_budget, another stop reason), which collect leaves with no
    defines_target."""
    want = {(r["model"], r["id"], r["run"]) for r in data["rows"]
            if r["condition"] == "text" and r["reason"] not in ft.NOT_GRADED
            and r["defines_target"] is not None}
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


def copy_flags(b, data, items, copies):
    """The flag of each model over items, its counts, and the copies of the table's models."""
    check_answers(b, data, copies)
    models = data["models"]
    copies = {k: v for k, v in copies.items() if k[0] in models}
    flags = flags_of(models, items, copies)
    summary = {"copy_answers": sum(copies.values()),
               "copied_items": len({i for (_, i, _), v in copies.items() if v}),
               "flagged": {name(m): len(flags[m]) for m in models}}
    return flags, summary, copies


def line_flags_report(line, copies_by_bench):
    """The 7-model line's copy flags: over every item, not only those the line keeps, and from
    every text run of the other models, run 2 of the open models included."""
    rep = {"settings": {"models": [name(m) for m in next(iter(line.values()))["models"]],
                        "runs": "every text run"},
           "benchmarks": {}}
    for b, data in line.items():
        _, summary, copies = copy_flags(b, data, data["all_items"], copies_by_bench[b])
        summary["flag_rows"] = sorted((b, i, m, r) for (m, i, r), v in copies.items() if v)
        rep["benchmarks"][b] = summary
    return rep


def removal_checks(b, data, lengths, flags, seed, n_draws):
    """Per model of data: the gaps without its flagged items, the matched random removal and the
    flagged items alone. The rate bins come from the mean text score of data's models."""
    models, items, projects = data["models"], data["items"], data["projects"]
    y = scores(data)
    sizes = data["conditions"][1:]
    pos = {i: j for j, i in enumerate(items)}
    text_mean = [mean([y[m]["text"][j] for m in models]) for j in range(len(items))]
    q, t = CONTROL["bins"]
    rate_bin = equal_groups(text_mean, items, q)
    check_lengths(b, items, lengths)
    len_bin = equal_groups([lengths[i] for i in items], items, t)
    bins = [(rate_bin[j], len_bin[j]) for j in range(len(items))]
    out = {"gaps": [], "control": {}, "flagged_only": []}
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
        flagged.sort()
        # flags come from the other models' text answers, so flagged items lean easy in text
        row = test_row(m, [d[j] for j in flagged], [projects[j] for j in flagged])
        row["text_flagged"] = mean([y[m]["text"][j] for j in flagged])
        row["text_rest"] = mean([y[m]["text"][j] for j in keep])
        row["gap_rest"] = mean([d[j] for j in keep])
        out["flagged_only"].append(row)
        base = mean(d)
        observed = mean([d[j] for j in keep]) - base
        pool = set(keep)
        draws, short = matched_removals(flagged, bins, pool, n_draws, f"{seed}-{m}")
        total = math.fsum(d)
        changes = sorted((total - math.fsum(d[j] for j in dr)) / (len(d) - len(dr)) - base
                         for dr in draws)
        out["control"][name(m)] = {
            "observed_change": observed, "lo": rel.quantile(changes, 0.025),
            "hi": rel.quantile(changes, 0.975),
            "share_at_or_below": sum(c <= observed for c in changes) / len(changes),
            "flagged": len(flagged), "removed_per_draw": len(draws[0]), "shortfall": short}
    return out


def contamination_report(inputs, copies_by_bench, modes, seed=CONTROL_SEED,
                         n_draws=None):
    n_draws = n_draws or CONTROL["draws"]
    rep = {"settings": {"control_draws": n_draws, "seed": seed, "bins": CONTROL["bins"],
                        "glmm_top": CONTROL["glmm_top"]}, "benchmarks": {}}
    for b, (data, lengths) in inputs.items():
        models, items = data["models"], data["items"]
        flags, summary, copies = copy_flags(b, data, items, copies_by_bench[b])
        out = {**summary, **removal_checks(b, data, lengths, flags, f"{seed}-{b}", n_draws)}
        if b not in modes:
            raise ValueError(f"{b}: no item:model modes; run analysis/glmm_main.R first")
        out["flag2"] = flag2_overlap(models, items, modes[b], flags)
        out["flag_rows"] = sorted((b, i, mm, r) for (mm, i, r), v in copies.items() if v)
        rep["benchmarks"][b] = out
    adjust([r for v in rep["benchmarks"].values() for r in v["gaps"]], "bh", "bh")
    return rep


def contamination(args):
    cfg = config.load()
    if args.models == "all":
        line = read_line(cfg, args.full, args.claude_full)
        copies = {b: text_copies(b, args.answers, ("block1", "rest", "claude")) for b in line}
        rep = line_flags_report(line, copies)
    else:
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
LINE_REPORT_INPUTS = {"ranks.json": "scripts/analysis.py ranks",
                      "glmm.json": ("analysis/glmm_main.R --in scratch/analysis_all --out "
                                    "results/claude/analysis"),
                      "contamination.json": "scripts/analysis.py contamination --models all"}
CLAUDE_REPORT_INPUTS = {"gaps.json": ("scripts/analysis.py gaps --models claude --answers "
                                      "scratch/contamination"),
                        "replies.json": "scripts/analysis.py replies --run-dir <Claude run dir>",
                        **LINE_REPORT_INPUTS}
COV_FIELDS = ("benchmark", "model_a", "model_b", "cov")
# the CSV keeps 15 significant digits and glmm.json rounds the SE to 6 decimals
COV_TOL = {"symmetry": 1e-9, "se": 2e-6}
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


def read_report_inputs(out, wanted=None):
    got = {}
    for f, cmd in (wanted or REPORT_INPUTS).items():
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
    if "pooled" in g:
        p = g["pooled"]
        rows.append(["Mean of models", "", pp(p["est"]), interval(p["lo"], p["hi"]), "", "", "",
                     "", ""])
    return md_table(["Model", "Text %", "Gap pp", "Cluster 95% CI", "Holm p", "Item-level CI",
                     "Logit contrast", "Logit 95% CI", "Token ratio"], rows)


def size_tables(g, sizes_note, diffs_note):
    out = [f"Gap per image size ({sizes_note}):", ""]
    out += md_table(["Model", "Size", "Gap pp", "Cluster 95% CI", "p", "BH p"],
                    [[r["model"], r["size"]] + gap_cells(r) + [pval(r["bh"])] for r in g["sizes"]])
    out += [f"Differences between sizes ({diffs_note}):", ""]
    out += md_table(["Model", "Pair", "Diff pp", "Cluster 95% CI", "p", "BH p"],
                    [[r["model"], r["pair"]] + gap_cells(r) + [pval(r["bh"])]
                     for r in g["size_diffs"]])
    return out


def token_table(g, models, sizes, ratio_note, extra=None):
    """Prompt tokens per condition and the median token ratio, plus extra[m][s] columns."""
    conds = list(g["tokens"][models[0]])
    out = [f"Prompt tokens, run 0, median [q1, q3], {ratio_note}:", ""]
    head = ["Model"] + conds + [f"ratio {s}" for s in sizes]
    if extra:
        head += [f"mean ratio {s}" for s in sizes]
    return out + md_table(head, [[m] + [f"{t['median']:g} [{t['q1']:g}, {t['q3']:g}]"
                                        for t in g["tokens"][m].values()]
                                 + [num(g["token_ratio"][m][s], 2) for s in sizes]
                                 + ([num(extra[m][s], 2) for s in sizes] if extra else [])
                                 for m in models])


def lopo_table(g):
    if not g["lopo"]:
        return []
    out = ["Leave one project out (gap over sizes without that project):", ""]
    return out + md_table(["Model", "Left out", "Items", "Gap pp", "Cluster 95% CI", "p"],
                          [[r["model"], r["left_out"], r["n"]] + gap_cells(r) for r in g["lopo"]])


def floor_table(g, models):
    out = ["Floor and ceiling: share of items (%) with no run passing / every run passing:", ""]
    fc = g["floor_ceiling"]
    conds = list(fc[models[0]])
    return out + md_table(["Model"] + conds,
                          [[m] + [f"{pp(v['none'], False)} / {pp(v['all'], False)}"
                                  for v in fc[m].values()] for m in models])


def scoring_table(b, g, models):
    out = ["Scoring shares (%): empty / truncated / no code"
           + (" / no def line of the target" if b == "deveval" else "") + ":", ""]
    keys = ["empty", "truncated", "no_code"] + (["no_def_line"] if b == "deveval" else [])
    conds = list(g["scoring"][models[0]])
    return out + md_table(["Model"] + conds,
                          [[m] + [" / ".join(pp(v[k], False) for k in keys)
                                  for v in g["scoring"][m].values()] for m in models])


def excluded_note(b, v):
    n = v.get("excluded", {}).get("count", 0)
    return f" ({n} excluded, see docs/decisions.md {rel.EXCLUDED_ON[b]})" if n else ""


def gaps_sections(b, g, gl):
    conds = list(g["rates"])
    models = [r["model"] for r in g["main"]]
    out = [f"### {BENCH_TITLES.get(b, b)}", "",
           (f"{g['n_items']} items{excluded_note(b, g)} in {g['n_clusters']} clusters. No "
            f"{'other ' if excluded_note(b, g) else ''}item is dropped: the grid check fails on "
            "any missing cell, so counting dropped items as failures changes nothing."), ""]
    out += main_table(g, gl)
    out += ["Rates by condition (%), item-weighted, with the rank in brackets:", ""]
    out += md_table(["Model"] + conds,
                    [[m] + [f"{pp(g['rates'][c][m], False)} ({g['ranks'][c][m]:g})" for c in conds]
                     for m in models])
    out += size_tables(g, "BH over the per-size family", "BH over the size-difference family")
    sizes = [c for c in conds if c not in ("text", "image")]
    out += token_table(g, models, sizes, "and the median per-item ratio to text")
    out += lopo_table(g)
    out += [("Context length (exploratory; buckets of Qwen3.5 text tokens, [lo, hi); BH over the "
            "length family):"), ""]
    out += md_table(["Model", "Size", "Bucket", "Items", "Gap pp", "Cluster 95% CI", "p", "BH p"],
                    [[r["model"], r["size"], r["bucket"], r["n"]] + gap_cells(r) + [pval(r["bh"])]
                     for r in g["length"]])
    out += floor_table(g, models)
    out += md_table(["Condition", "Every model passes %", "No model passes %"],
                    [[c, pp(v["all_models_pass"], False), pp(v["no_model_passes"], False)]
                     for c, v in g["all_none"].items()])
    out += [(f"{g['never_passed']} items pass in no condition for any model "
            "(`never_passed.csv`)."), ""]
    out += scoring_table(b, g, models)
    out += [("Output tokens over all runs, median [q1, q3] and mean, and the image-to-text ratio "
             "of the means:"), ""]
    ot = g["output_tokens"]
    out += md_table(["Model"] + [c for c in conds if c != "image"] + [f"ratio {s}" for s in sizes],
                    [[m] + [f"{t['median']:g} [{t['q1']:g}, {t['q3']:g}], {t['mean']:.0f}"
                            for t in ot[m].values()]
                     + [num(ot[m][s]["mean"] / ot[m]["text"]["mean"], 2) for s in sizes]
                     for m in models])
    return out


def glmm_sections(b, v, item_flags=True):
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
            f"probit {num(v['probit']['ratio_probit'])}.")]
    if item_flags:
        out.append(f"- Item flags: {v['item_flags']['bh_flagged']} of {v['item_flags']['n']} "
                   "item:condition modes with BH p < 0.05; "
                   f"{v['item_flags']['raw_ci_excludes_zero']} with a raw 95% interval "
                   "excluding 0.")
    out += ["- Built-in checks: " + ", ".join(f"({k}) {'ok' if c['ok'] else 'FAILED'}"
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
    out += removal_tables(v)
    out += [(f"Copy flag against the GLMM flag (item:model mode in the model's top "
            f"{100 * top:g}%):"), ""]
    out += md_table(["Model", "Both", "Copy only", "GLMM only", "Neither"],
                    [[m, x["both"], x["copy_only"], x["glmm_only"], x["neither"]]
                     for m, x in v["flag2"].items()])
    return out


def removal_tables(v):
    """Gaps without flagged items, the matched random removal and the flagged items alone."""
    out = md_table(["Model", "Gap", "Removed", "All items pp", "Without flagged pp",
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
    out += [("Flagged items alone (mean-over-sizes gap with its cluster interval) against the rest, "
             "with the model's own text rate on each set. Flags come from the other models' text "
             "answers, so a higher text rate on flagged items says they lean easy in text:"), ""]
    out += md_table(["Model", "Flagged", "Text % flagged", "Text % rest", "Gap flagged pp",
                     "Cluster 95% CI", "Gap rest pp"],
                    [[r["model"], r["n"], pp(r["text_flagged"], False), pp(r["text_rest"], False),
                      pp(r["est"]), interval(r["cluster"]["lo"], r["cluster"]["hi"]),
                      pp(r["gap_rest"])] for r in v["flagged_only"]])
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


def rank_sections(b, v):
    conds = list(v["ranks"])
    out = [f"### {BENCH_TITLES.get(b, b)}", "",
           (f"{v['n_items']} items{excluded_note(b, v)} in {v['n_clusters']} clusters, "
            f"{v['dropped']['count']} dropped."),
           "", "Rate % (rank) [95% rank interval], item-weighted:", ""]
    out += md_table(["Model"] + conds,
                    [[m] + [f"{pp(v['rates'][c][m], False)} ({v['ranks'][c][m]['rank']:g}) "
                            f"[{v['ranks'][c][m]['lo']:g}, {v['ranks'][c][m]['hi']:g}]"
                            for c in conds] for m in v["ranks"][conds[0]]])
    out += ["Probability that a pair swaps order between text and image (ties count half):", ""]
    out += md_table(["Pair", "P(swap)"],
                    [[f"{s['pair'][0]} / {s['pair'][1]}", num(s["p"])] for s in v["swap"]])
    return out


def check_line(inputs):
    """The ranks, the GLMM fit and the copy flags must come from the same 7-model table."""
    r, gl, c = inputs["ranks"], inputs["glmm"], inputs["contamination"]
    models = r["settings"]["models"]
    for b, v in r["benchmarks"].items():
        g = gl["benchmarks"].get(b, {})
        if [name(m) for m in g.get("models", [])] != models or g.get("n_items") != v["n_items"]:
            raise ValueError(f"{b}: glmm.json ({len(g.get('models', []))} models, "
                             f"{g.get('n_items')} items) does not match ranks.json ({len(models)} "
                             f"models, {v['n_items']} items); rerun prep --models all, "
                             "glmm_main.R and ranks on the same table")
        if list(c["benchmarks"].get(b, {}).get("flagged", {})) != models:
            raise ValueError(f"{b}: contamination.json does not flag the models of ranks.json; "
                             "rerun contamination --models all")


def read_cov(path, glmm):
    """{benchmark: {(model_a, model_b): cov}} from glmm_contrast_cov.csv, checked against
    glmm.json: every pair of its models, symmetric, and sqrt of the diagonal equal to its SEs."""
    rerun = f"; rerun {LINE_REPORT_INPUTS['glmm.json']}"
    if not os.path.exists(path):
        raise ValueError(f"{path} is missing{rerun}")
    cov = defaultdict(dict)
    for r in rel.read_csv(path, COV_FIELDS):
        cov[r["benchmark"]][(r["model_a"], r["model_b"])] = float(r["cov"])
    for b, v in glmm["benchmarks"].items():
        s, models = cov[b], v["models"]
        missing = [(x, y) for x in models for y in models if (x, y) not in s]
        if missing:
            raise ValueError(f"{path}: {b} has no entry for {missing[0]}{rerun}")
        for x, y in combinations(models, 2):
            if abs(s[(x, y)] - s[(y, x)]) > COV_TOL["symmetry"] * max(abs(s[(x, y)]),
                                                                      abs(s[(y, x)])):
                raise ValueError(f"{path}: {b} is not symmetric at {x}, {y}{rerun}")
        for r in v["contrast"]:
            if abs(math.sqrt(s[(r["model"], r["model"])]) - r["se"]) > COV_TOL["se"]:
                raise ValueError(f"{path}: {b} {r['model']}: sqrt of the variance does not match "
                                 f"the glmm.json SE {r['se']}{rerun}")
    return cov


def open_closed(v, cov, claude):
    """c of the addendum on one benchmark: the mean Claude logit contrast minus the mean open one,
    with its Wald interval. v is the benchmark's glmm.json entry, cov its contrast covariance."""
    models = v["models"]
    est = {r["model"]: r["est"] for r in v["contrast"]}
    missing = [m for m in models if m not in est]
    if missing:
        raise ValueError(f"no logit contrast for {', '.join(missing)}")
    closed = [m for m in models if m in claude]
    opens = [m for m in models if m not in claude]
    if not closed or not opens:
        raise ValueError(f"c needs Claude and open models, got {len(closed)} and {len(opens)}")
    w = [1 / len(closed) if m in claude else -1 / len(opens) for m in models]
    if abs(math.fsum(w)) > 1e-12:
        raise ValueError(f"the weights of c sum to {math.fsum(w)}, not 0")
    out = st.wald_contrast([est[m] for m in models], [[cov[(a, b)] for b in models]
                                                       for a in models], w)
    return {**out, "closed": len(closed), "open": len(opens)}


def excludes_zero(lo, hi):
    return lo is not None and hi is not None and (lo > 0 or hi < 0)


def c_reading(c):
    if c["lo"] > 0:
        return "Claude loses less (interval above 0)"
    if c["hi"] < 0:
        return "Claude loses more (interval below 0)"
    return "the interval includes 0"


def claude_gap_sections(b, g, gl, g5, gl5):
    models = [r["model"] for r in g["main"]]
    sizes = [c for c in g["rates"] if c not in ("text", "image")]
    errors = sum(n for x in g["request_errors"].values() for n in x.values())
    out = [f"### {BENCH_TITLES.get(b, b)}", "",
           (f"{g['n_items']} items{excluded_note(b, g)} in {g['n_clusters']} clusters. {errors} "
            "request errors: every "
            "Claude cell has its 2 scored runs, so the sensitivity line that counts a request "
            "error as a failure equals the main line. The logit contrast is from the 7-model "
            "GLMM."), ""]
    out += main_table(g, gl)
    out += [("The five open models, for comparison: the 5-model confirmatory family (Holm over "
             "its 10 gaps, every run), with the logit contrast of the 5-model GLMM."), ""]
    out += main_table(g5, gl5)
    out += size_tables(g, "BH over the Claude set", "BH over the Claude set")
    out += lopo_table(g)
    out += token_table(g, models, sizes, ("the median per-item ratio to text (primary, as for the "
                                          "open models) and the item mean ratio (the addendum's "
                                          "wording)"), extra=g["token_ratio_mean"])
    out += floor_table(g, models)
    return out


def claude_contamination_sections(b, g):
    k = g["contamination"]
    rows = [[m, pp(g["rates"]["text"][m], False), pp(g["floor_ceiling"][m]["text"]["all"], False),
             f"{k['flagged'][m]} of {g['n_items']}",
             f"{k['own_copies'][m]['answers']} / {k['own_copies'][m]['items']}"]
            for m in k["flagged"]]
    out = [f"### {BENCH_TITLES.get(b, b)}", ""]
    out += md_table(["Model", "Text %", "Text 2 of 2 %", "Flagged items",
                     "Own copies (answers / items)"], rows)
    short = [(m, c) for m, c in k["control"].items() if c and c["shortfall"]]
    if short:
        out += ["Where the unflagged items run short, the control cannot match the flagged set: "
                + "; ".join(control_note(m, c, g["n_items"]) for m, c in short)
                + ". The control is not a match there.", ""]
    out += removal_tables(k)
    out += ["The flagged-only rows are the related-work check of decisions 2026-11-16.", ""]
    return out


def control_note(m, c, n_items):
    pool = n_items - c["flagged"]
    note = (f"{m} has {pool} unflagged items, so each draw removes {c['removed_per_draw']} of "
            f"the {c['flagged']} it should")
    if c["removed_per_draw"] == pool:
        note += (", every draw removes the same items, and its range and share carry no "
                 "information")
    return note


def count_cell(counts):
    return ", ".join(f"{k} {n}" for k, n in sorted(counts.items())) or "0"


def reply_sections(b, rp, g):
    models = list(rp)
    conds = list(rp[models[0]])
    out = [f"### {BENCH_TITLES.get(b, b)}", ""]
    out += md_table(["Model", "Condition", "Replies", "Request errors", "Refusals",
                     "max_tokens", "over_budget", "Other stops", "Thinking share %",
                     "With thinking", "Cache tokens (write / read)"],
                    [[m, c, x["replies"], x["request_errors"], count_cell(x["refusals"]),
                      x["max_tokens"], x["over_budget"], count_cell(x["other_stops"]),
                      pp(x["thinking_share"], False), x["with_thinking"],
                      f"{x['cache_creation_tokens']} / {x['cache_read_tokens']}"]
                     for m in models for c, x in rp[m].items()])
    out += scoring_table(b, g, models)
    sizes = conds[1:]
    out += [("Non-thinking output tokens, median [q1, q3] and mean, and the image-to-text ratio of "
             "the means (the related-work check of decisions 2026-11-16):"), ""]
    out += md_table(["Model"] + conds + [f"ratio {s}" for s in sizes],
                    [[m] + [f"{t['median']:g} [{t['q1']:g}, {t['q3']:g}], {t['mean']:.0f}"
                            for t in (rp[m][c]["output_tokens"] for c in conds)]
                     + [num(rp[m][s]["output_tokens"]["mean"]
                            / rp[m]["text"]["output_tokens"]["mean"], 2) for s in sizes]
                     for m in models])
    return out


def glmm_compare_rows(v):
    w, ic, lrt, ho, pr = v["wald"], v["item_condition_sd"], v["lrt"], v["heldout"], v["probit"]
    rows = [("Equal contrasts (Wald)",
             f"chi2 {num(w['stat'], 2)} on {w['df']} df, p {pval(w['p'])}"),
            ("item:condition SD (logit)", f"{num(ic['est'])} {interval(ic['lo'], ic['hi'], num)}"),
            ("LRT against no item:condition", f"{num(lrt['stat'], 2)}, halved p {pval(lrt['p'])}"),
            ("Held-out difference (SE)", f"{num(ho['diff'], 1)} ({num(ho['se'], 1)})"),
            ("SD item:condition / SD item, logit / probit",
             f"{num(pr['ratio_logit'])} / {num(pr['ratio_probit'])}")]
    rows += [(f"C, {method}", num(pairs["C"]["observed"])) for method, pairs in
             v["correlation"].items()]
    rows += [(f"Common slope / r, {s}", num(x["corrected"])) for s, x in v["common_slope"].items()]
    rows.append(("Built-in checks", ", ".join(f"({k}) {'ok' if c['ok'] else 'FAILED'}"
                                              for k, c in v["checks"].items())))
    return rows


def line_sections(inputs, gl5):
    r, gl = inputs["ranks"], inputs["glmm"]
    s = r["settings"]
    dropped = ", ".join(f"{BENCH_TITLES.get(b, b)} {v['dropped']['count']}"
                        for b, v in r["benchmarks"].items())
    out = [f"## {len(s['models'])}-model line", "",
           (f"Every model uses runs {' and '.join(str(k) for k in s['runs'])} only; the 5-model "
            f"column keeps every run. Items dropped ({s['drop_rule']}): {dropped}."), ""]
    for b, v in gl["benchmarks"].items():
        main = gl5["benchmarks"].get(b)
        rv = r["benchmarks"][b]
        out += [f"### {BENCH_TITLES.get(b, b)}", "",
                (f"{rv['n_items']} items{excluded_note(b, rv)} in {rv['n_clusters']} clusters, "
                 f"{rv['dropped']['count']} dropped."), ""]
        mine = glmm_compare_rows(v)
        theirs = dict(glmm_compare_rows(main)) if main else {}
        out += md_table(["Statistic", f"{len(main['models'])}-model" if main else "5-model",
                         f"{len(v['models'])}-model"],
                        [[k, theirs.get(k, "n/a"), x] for k, x in mine])
    out += [f"## {len(s['models'])}-model GLMM detail", "",
            (f"`{gl['settings']['formula']}`, glmmTMB {gl['settings']['glmmTMB']}, "
             f"R {gl['settings']['R']}."), ""]
    for b, v in gl["benchmarks"].items():
        out += glmm_sections(b, v, item_flags=False)
    return out


def rank_and_flag_sections(inputs, g5):
    r, c = inputs["ranks"], inputs["contamination"]
    s = r["settings"]
    models = s["models"]
    out = [f"## Ranks ({len(models)}-model line)", "",
           (f"Rank intervals and swap probabilities use {s['n_boot']} joint cluster draws "
            f"({s['interval']})."), ""]
    for b, v in r["benchmarks"].items():
        out += rank_sections(b, v)
        main = g5["benchmarks"].get(b)
        if main:
            conds = [k for k in v["ranks"] if k in main["ranks"]]
            out += ["5-model ranks, every run (results/analysis/gaps.json):", ""]
            out += md_table(["Model"] + conds, [[m] + [f"{main['ranks'][k][m]:g}" for k in conds]
                                                for m in main["ranks"][conds[0]]])
    flagged = c["benchmarks"]
    out += ["## Contamination flags", "",
            (f"An item is flagged for model m when one of the other {len(models) - 1} models "
             "copies the reference token for token in any of its text runs. Flags cover every "
             "item, including dropped ones, but not the excluded ones."), ""]
    out += md_table(["Model"] + [BENCH_TITLES.get(b, b) for b in flagged],
                    [[m] + [v["flagged"][m] for v in flagged.values()] for m in models])
    out += [", ".join(f"{BENCH_TITLES.get(b, b)}: {v['copy_answers']} text answers copy the "
                      f"reference, on {v['copied_items']} items" for b, v in flagged.items())
            + "."]
    return out


def paper_paragraph(g, g5, gl, cs):
    """The Claude result in a few sentences for the paper; every direction word comes from the
    values."""
    benches = list(g["benchmarks"])
    models = g["settings"]["models"]
    t = [BENCH_TITLES.get(b, b) for b in benches]

    def per_model(f):
        return " and ".join(f(m) for m in models)

    def text_rates(b):
        return per_model(lambda m: pp(g["benchmarks"][b]["rates"]["text"][m], False) + "%")

    rates = "; ".join(f"{tb} {text_rates(b)}" for b, tb in zip(benches, t))
    rows = [(b, r) for b in benches for r in g["benchmarks"][b]["main"]]
    gaps = "; ".join(f"{tb} " + " and ".join(
        f"{pp(r['est'])} pp {interval(r['cluster']['lo'], r['cluster']['hi'])}"
        for r in g["benchmarks"][b]["main"]) for b, tb in zip(benches, t))
    k = sum(excludes_zero(r["cluster"]["lo"], r["cluster"]["hi"]) for _, r in rows)
    excl = (f"all {len(rows)} cluster intervals exclude 0" if k == len(rows) else
            f"{k} of the {len(rows)} cluster intervals exclude 0")
    loose = [(tb, r) for b, tb in zip(benches, t) for r in g["benchmarks"][b]["main"]
             if not excludes_zero(r["item"]["lo"], r["item"]["hi"])]
    item_note = ("" if not loose else " The item-level interval includes 0 for "
                 + "; ".join(f"{r['model']} on {tb} {interval(r['item']['lo'], r['item']['hi'])}"
                             for tb, r in loose) + ".")
    opens = "; ".join(
        f"{tb} {pp(min(r['est'] for r in g5['benchmarks'][b]['main']))} to "
        f"{pp(max(r['est'] for r in g5['benchmarks'][b]['main']))} pp"
        for b, tb in zip(benches, t) if b in g5["benchmarks"])
    c_text = "; ".join(f"{tb} {num(cs[b]['est'], 2)} "
                       f"{interval(cs[b]['lo'], cs[b]['hi'], lambda x: num(x, 2))}, "
                       f"{c_reading(cs[b])}" for b, tb in zip(benches, t))
    wald = "; ".join(f"{tb} chi2 {num(gl['benchmarks'][b]['wald']['stat'], 1)}, "
                     f"p {pval(gl['benchmarks'][b]['wald']['p'])}" for b, tb in zip(benches, t))
    df = next(iter(gl["benchmarks"].values()))["wald"]["df"]
    ceiling = ""
    if LOPO_BENCH in g["benchmarks"]:
        v = g["benchmarks"][LOPO_BENCH]
        k = v["contamination"]["flagged"]
        ceiling = (f" On {BENCH_TITLES[LOPO_BENCH]}, "
                   f"{per_model(lambda m: pp(v['floor_ceiling'][m]['text']['all'], False) + '%')} "
                   "of items pass both Claude text runs, and another model's text answer "
                   "reproduces the "
                   f"reference token for token on {per_model(lambda m: str(k[m]))} of its "
                   f"{v['n_items']} items.")
    return (f"In an exploratory extension under a methodology addendum written before the first "
            f"request, {per_model(lambda m: m)} answered the same items in the same four "
            "conditions, two runs each. They differ from the open-model run in three ways: the "
            "API takes no seed, it samples at temperature 1.0, and Opus cannot turn thinking "
            f"off. Their text pass rates were {rates}. Averaged over the three image sizes, the "
            f"image-minus-text gaps (95% cluster intervals) were {gaps}; {excl}.{item_note} The "
            f"open models' "
            f"gaps ranged over {opens}. The open vs closed logit contrast c (Claude mean minus "
            f"open mean, 95% Wald interval) was {c_text}. With seven models the Wald test of equal "
            f"contrasts on {df} df gave {wald}.{ceiling}")


def check_claude_flags(g, line_c):
    """gaps.json and the line's contamination.json flag the Claude models from the same copies."""
    for b, v in g["benchmarks"].items():
        mine = v["contamination"]["flagged"]
        theirs = {m: line_c["benchmarks"].get(b, {}).get("flagged", {}).get(m) for m in mine}
        if mine != theirs:
            raise ValueError(f"{b}: the Claude flag counts of gaps.json {mine} differ from "
                             f"contamination.json {theirs}; rerun both on the same answers")


def claude_findings(inputs, main, cov, claude):
    g, rp, gl = inputs["gaps"], inputs["replies"], inputs["glmm"]
    g5, gl5 = main["gaps"], main["glmm"]
    check_line(inputs)
    check_claude_flags(g, inputs["contamination"])
    cs = {b: open_closed(v, cov[b], claude) for b, v in gl["benchmarks"].items()}
    s = g["settings"]
    out = ["# Claude extension findings", "",
           ("Generated by `uv run python scripts/analysis.py report --models all` from "
            "results/claude/analysis/{gaps,replies,ranks,glmm,contamination}.json, "
            "glmm_contrast_cov.csv and results/analysis/{gaps,glmm}.json; edit the scripts, not "
            "this file."), "",
           (f"Every number here is exploratory (methodology addendum, 2026-11-14). Models: "
            f"{', '.join(s['models'])}, runs {' and '.join(str(k) for k in s['runs'])} on every "
            "item. Gap = image minus text, mean over the image sizes, in percentage points. "
            f"Intervals: {s['interval']}. Holm over the {s['holm_rows']} Claude size-averaged "
            f"gaps; one BH set over {s['bh_set']['covers']} ({s['bh_set']['rows']} rows). The "
            "logit contrast is biased toward 0 by "
            f"{LOGIT_BIAS[0]} to {LOGIT_BIAS[1]} logit in the UFM-21 simulation."), "",
           "Run differences from the open models (addendum):", "",
           "- No seed is sent, since the API takes none.",
           "- No temperature or top_p is sent, so both models sample at temperature 1.0.",
           "- Opus cannot turn thinking off and runs adaptive thinking at low effort.",
           ("- An Opus reply over 2,048 non-thinking tokens fails before grading "
            "(`over_budget`)."),
           "- 2 runs on every item, where the open models have 3 on block-1 items.",
           "- Closed weights and training data: the copy flags are the only contamination check.",
           "", "Analysis deviations:", "",
           ("- The 7-model line drops an item with a short Claude cell in all four conditions "
            "(decisions 2026-11-17)."),
           ("- A short Claude cell stops `gaps --models claude` instead of leaving its condition; "
            "the collected tables have none."),
           ("- The token ratio is the median per-item ratio, as for the open models; the item "
            "mean that the addendum names is shown beside it."),
           "- Claude output tokens leave thinking out.", "",
           "## Claude gaps", ""]
    for b, v in g["benchmarks"].items():
        out += claude_gap_sections(b, v, gl["benchmarks"].get(b, {"contrast": []}),
                                   g5["benchmarks"][b], gl5["benchmarks"].get(b, {"contrast": []}))
    out += ["## Contamination and ceiling", "",
            ("An item is flagged for a Claude model when one of the other 6 models copies the "
             "reference token for token in any text run. A model's own copies never flag it and "
             "are counted apart. This is a sensitivity check, not a corrected gap. "
             f"{s['control_draws']} matched random removals per model."), ""]
    for b, v in g["benchmarks"].items():
        out += claude_contamination_sections(b, v)
    out += ["## Replies", "",
            ("From the Claude run log joined to the collected rows (`replies`). Thinking share is "
             "thinking tokens over output tokens, summed."), ""]
    for b, v in rp["benchmarks"].items():
        out += reply_sections(b, v, g["benchmarks"][b])
    out += line_sections(inputs, gl5)
    k = next(iter(cs.values()))
    out += ["## Open vs closed", "",
            (f"c = (1/{k['closed']}) sum of the Claude logit contrasts minus (1/{k['open']}) sum "
             "of the open ones, from the 7-model GLMM, with a 95% Wald interval from the "
             "contrasts' covariance (glmm_contrast_cov.csv). No p-value, outside every correction "
             "family, and it describes these 7 models only. c > 0 means the Claude models lose "
             "less from images than the open models. The per-model contrasts are biased toward 0 "
             f"by {LOGIT_BIAS[0]} to {LOGIT_BIAS[1]} logit in the UFM-21 simulation; c itself was "
             "not simulated."), ""]
    out += md_table(["Benchmark", "c (logit)", "SE", "95% Wald CI", "Reading"],
                    [[BENCH_TITLES.get(b, b), num(c["est"]), num(c["se"]),
                      interval(c["lo"], c["hi"], num), c_reading(c)] for b, c in cs.items()])
    out += rank_and_flag_sections(inputs, g5)
    out += ["", "## Paper paragraph", "", paper_paragraph(g, g5, gl, cs)]
    return "\n".join(out).rstrip("\n") + "\n"


def report(args):
    if args.models == "all":
        inputs = read_report_inputs(args.out, CLAUDE_REPORT_INPUTS)
        main = read_report_inputs(OUT, {f: REPORT_INPUTS[f] for f in ("gaps.json", "glmm.json")})
        cov = read_cov(os.path.join(args.out, "glmm_contrast_cov.csv"), inputs["glmm"])
        text = claude_findings(inputs, main, cov, claude_set(config.load()))
        path = os.path.join(os.path.dirname(os.path.abspath(args.out)), "findings.md")
        claude_figures(inputs["gaps"], main["gaps"], os.path.join(args.out, "figures"))
    else:
        text = findings(read_report_inputs(args.out))
        path = os.path.join(args.out, "findings.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    print(path)


# slots 1 to 5 of the dataviz reference palette (light), and its text inks
SERIES = ("#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4")
INK, INK2, GRID, MUTED = "#0b0b0b", "#52514e", "#d9d8d4", "#a8a7a2"
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


def figures(rep, out_dir, files=("main_gap.pdf", "size_curve.pdf"), muted=()):
    """The gap per model with its interval and per-size dots, and the size curve. Muted models
    are drawn in grey without intervals on the size curve, with one legend entry."""
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
    _save(fig, os.path.join(out_dir, files[0]))
    plt.close(fig)

    fig, axes = plt.subplots(1, len(benches), figsize=(WIDTH, 2.6), sharey=True)
    for ax, b in zip(axes, benches):
        v = rep["benchmarks"][b]
        first_muted = next((m for m in models if m in muted), None)
        for k, m in enumerate(models):
            rows = [r for r in v["sizes"] if r["model"] == m]
            rows.sort(key=lambda r: int(r["size"][5:]))
            xs = [v["token_ratio"][m][r["size"]] for r in rows]
            if m in muted:
                ax.plot(xs, [r["est"] * scale for r in rows], "-o", color=MUTED, lw=1, ms=3,
                        label="Open models, every run" if m == first_muted else None)
                continue
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
               ncol=min(len(labels), 3))
    fig.tight_layout(rect=(0, 0.16, 1, 1))
    _save(fig, os.path.join(out_dir, files[1]))
    plt.close(fig)


def claude_figures(g, g5, out_dir):
    """claude_gap.pdf and size_curve.pdf: the Claude models, then the open models of the 5-model
    run, which are grey on the size curve."""
    benches = {}
    for b, v in g["benchmarks"].items():
        w = g5["benchmarks"][b]
        benches[b] = {"main": v["main"] + w["main"], "sizes": v["sizes"] + w["sizes"],
                      "token_ratio": {**v["token_ratio"], **w["token_ratio"]}}
    rep = {"settings": {"models": g["settings"]["models"] + g5["settings"]["models"]},
           "benchmarks": benches}
    figures(rep, out_dir, ("claude_gap.pdf", "size_curve.pdf"), muted=set(g5["settings"]["models"]))


COMMANDS = {"gaps": gaps, "prep": prep, "contamination": contamination, "ranks": ranks,
            "report": report, "replies": replies}


def main(argv=None):
    ap = argparse.ArgumentParser(description="Main analysis of the full answer table")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("gaps")
    p.add_argument("--models", choices=("main", "claude"), default="main")
    p.add_argument("--full", default=FULL)
    p.add_argument("--claude-full", default=CLAUDE_FULL)
    p.add_argument("--answers", help="with --models claude: the text answers of every model")
    p.add_argument("--out")
    p = sub.add_parser("replies")
    p.add_argument("--run-dir", required=True, help="the Claude run directory (gen/ and claude/)")
    p.add_argument("--claude-full", default=CLAUDE_FULL)
    p.add_argument("--out")
    for cmd in ("prep", "contamination", "ranks", "report"):
        p = sub.add_parser(cmd)
        if cmd != "ranks":
            p.add_argument("--models", choices=("main", "all"), default="main")
        if cmd != "report":
            p.add_argument("--full", default=FULL)
            p.add_argument("--claude-full", default=CLAUDE_FULL)
        if cmd == "prep":
            p.add_argument("--scratch")
        else:
            p.add_argument("--out")
        if cmd == "contamination":
            p.add_argument("--answers", required=True,
                           help="text answers and references copied from the cluster")
    args = ap.parse_args(argv)
    if args.cmd == "gaps" and (args.models == "claude") != (args.answers is not None):
        ap.error("gaps: --answers goes with --models claude, and only with it")
    line = args.cmd in ("ranks", "replies") or getattr(args, "models", "main") != "main"
    if args.cmd == "prep" and args.scratch is None:
        args.scratch = SCRATCH["all" if line else "main"]
    if args.cmd != "prep" and args.out is None:
        args.out = ALL_OUT if line else OUT
    try:
        COMMANDS[args.cmd](args)
    except (ValueError, OSError) as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
