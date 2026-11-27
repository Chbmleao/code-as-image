"""The contamination checks: copy flags from the text answers that match the reference, and the
gaps without the flagged items against a matched random removal."""
import importlib.util
import math
import os
import random
from collections import Counter, defaultdict

from codeimg import config
from codeimg.analysis import full_table as ft
from codeimg.analysis import inputs as inp
from codeimg.analysis import reliability as rel
from codeimg.analysis import stats as st

ROOT = config.ROOT

# matched random removal: quintiles of the mean text score x terciles of length
CONTROL = {"draws": 1000, "bins": (5, 3), "glmm_top": 0.10}
CONTROL_SEED = 20261118


def claude_contamination(b, data, lengths, copies, seed, n_draws):
    """copies holds the text runs of all seven models, so a Claude model's flag comes from any
    other model, the other Claude model included. A model's own copies never flag it and are
    counted apart."""
    check_answers(b, data, copies)
    models = data["models"]
    flags = flags_of(models, data["items"], copies)
    own = {inp.name(m): {"answers": sum(v for (mm, _, _), v in copies.items() if mm == m),
                         "items": len({i for (mm, i, _), v in copies.items() if mm == m and v})}
           for m in models}
    return {"flagged": {inp.name(m): len(flags[m]) for m in models}, "own_copies": own,
            **removal_checks(b, data, lengths, flags, seed, n_draws)}


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
        out[inp.name(m)] = {"both": len(f & top), "copy_only": len(f - top),
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
               "flagged": {inp.name(m): len(flags[m]) for m in models}}
    return flags, summary, copies


def line_flags_report(line, copies_by_bench):
    """The 7-model line's copy flags: over every item, not only those the line keeps, and from
    every text run of the other models, run 2 of the open models included."""
    rep = {"settings": {"models": [inp.name(m) for m in next(iter(line.values()))["models"]],
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
    y = st.scores(data)
    sizes = data["conditions"][1:]
    pos = {i: j for j, i in enumerate(items)}
    text_mean = [st.mean([y[m]["text"][j] for m in models]) for j in range(len(items))]
    q, t = CONTROL["bins"]
    rate_bin = equal_groups(text_mean, items, q)
    st.check_lengths(b, items, lengths)
    len_bin = equal_groups([lengths[i] for i in items], items, t)
    bins = [(rate_bin[j], len_bin[j]) for j in range(len(items))]
    out = {"gaps": [], "control": {}, "flagged_only": []}
    for m in models:
        keep = [j for j, i in enumerate(items) if i not in flags[m]]
        for label, cond in [("mean", sizes)] + [(s, s) for s in sizes]:
            d = st.differences(y[m], cond, "text")
            full = st.cluster_t(d, projects)
            row = st.test_row(m, [d[j] for j in keep], [projects[j] for j in keep],
                              gap=label, removed=len(items) - len(keep))
            row["all_items"] = full["est"]
            out["gaps"].append(row)
        d = st.differences(y[m], sizes, "text")
        flagged = [pos[i] for i in flags[m]]
        if not flagged:
            out["control"][inp.name(m)] = None
            continue
        flagged.sort()
        # flags come from the other models' text answers, so flagged items lean easy in text
        row = st.test_row(m, [d[j] for j in flagged], [projects[j] for j in flagged])
        row["text_flagged"] = st.mean([y[m]["text"][j] for j in flagged])
        row["text_rest"] = st.mean([y[m]["text"][j] for j in keep])
        row["gap_rest"] = st.mean([d[j] for j in keep])
        out["flagged_only"].append(row)
        base = st.mean(d)
        observed = st.mean([d[j] for j in keep]) - base
        pool = set(keep)
        draws, short = matched_removals(flagged, bins, pool, n_draws, f"{seed}-{m}")
        total = math.fsum(d)
        changes = sorted((total - math.fsum(d[j] for j in dr)) / (len(d) - len(dr)) - base
                         for dr in draws)
        out["control"][inp.name(m)] = {
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
    st.adjust([r for v in rep["benchmarks"].values() for r in v["gaps"]], "bh", "bh")
    return rep
