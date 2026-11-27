"""The analysis inputs: paths, model sets and conditions, and the answer tables checked against
the expected grid and turned into cells."""
import functools
import json
import os
from collections import Counter, defaultdict

from codeimg import config
from codeimg.analysis import dstudy as ds
from codeimg.analysis import full_table as ft
from codeimg.analysis import reliability as rel

ROOT = config.ROOT
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


def answer_rows(data):
    """The answers CSV of analysis/reliability.R's format, in model, condition, item, run order."""
    out = []
    for m in data["models"]:
        for c in data["conditions"]:
            for i, p, ys in zip(data["items"], data["projects"], data["cells"][m][c]):
                out += [(m, i, p, c, r, y) for r, y in enumerate(ys)]
    return out
