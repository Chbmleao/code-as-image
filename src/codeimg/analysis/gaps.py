"""The gaps: the paired image-text gap per model with its intervals and corrections, the per-size
and per-length gaps, the scoring shares, the Claude models' own gaps and the 7-model ranks."""
from collections import Counter, defaultdict
from itertools import combinations

from codeimg.analysis import contamination as ctm
from codeimg.analysis import dstudy as ds
from codeimg.analysis import inputs as inp
from codeimg.analysis import reliability as rel
from codeimg.analysis import resample as rs
from codeimg.analysis import stats as st


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
    return {inp.name(m): {c: {"answers": cells[(m, c)]["answers"],
                              **{k: cells[(m, c)][k] / cells[(m, c)]["answers"] for k in keys}}
                          for c in data["conditions"]} for m in data["models"]}


def output_lengths(data):
    """Output tokens per model and condition over every answer. Shorter answers under image input
    are the main cause of the gap in Reading, Not Thinking (arXiv 2603.09095)."""
    toks = defaultdict(list)
    for r in data["rows"]:
        toks[(r["model"], r["condition"])].append(r["output_tokens"])
    return {inp.name(m): {c: {**st.spread(toks[(m, c)]), "mean": st.mean(toks[(m, c)])}
                          for c in data["conditions"]} for m in data["models"]}


def benchmark_gaps(data, lengths, buckets, seed, n_boot):
    b, models, conds = data["benchmark"], data["models"], data["conditions"]
    sizes = conds[1:]
    items, projects = data["items"], data["projects"]
    y = st.scores(data)
    groups = ds.clusters(b, items, dict(zip(items, projects)))
    out = {"n_items": len(items), "n_clusters": len(groups),
           "excluded": {"count": len(data["excluded"]), "items": data["excluded"]}}

    rates = {c: {inp.name(m): st.mean(y[m][c]) for m in models} for c in conds}
    rates["image"] = {inp.name(m): st.mean([rates[c][inp.name(m)] for c in sizes]) for m in models}
    out["rates"] = rates
    out["ranks"] = {c: dict(zip(rates[c], rel.average_ranks(list(rates[c].values()))))
                    for c in ["text", "image"] + sizes}

    d_main = {m: st.differences(y[m], sizes, "text") for m in models}
    out["main"] = [st.test_row(m, d_main[m], projects) for m in models]
    out["pooled"] = st.pooled(d_main, groups, seed, n_boot)
    out["sizes"] = [st.test_row(m, st.differences(y[m], s, "text"), projects, size=s)
                    for m in models for s in sizes]
    out["size_diffs"] = [st.test_row(m, st.differences(y[m], s1, s2), projects, pair=f"{s1}-{s2}")
                         for m in models for s2, s1 in combinations(sizes, 2)]

    tok = data["tokens"]
    out["tokens"] = {inp.name(m): {c: st.spread(tok[m][c]) for c in conds} for m in models}
    out["token_ratio"] = {
        inp.name(m): {s: rel.quantile(sorted(a / t for a, t in zip(tok[m][s], tok[m]["text"])), 0.5)
                      for s in sizes} for m in models}
    for m in models:
        r = out["token_ratio"][inp.name(m)]
        r["mean_over_sizes"] = st.mean([r[s] for s in sizes])

    out["lopo"] = []
    if b == inp.LOPO_BENCH:
        for p in lopo_projects(projects, inp.LOPO_N):
            keep = [j for j, q in enumerate(projects) if q != p]
            for m in models:
                out["lopo"].append(st.test_row(m, [d_main[m][j] for j in keep],
                                               [projects[j] for j in keep], left_out=p))

    st.check_lengths(b, items, lengths)
    bucket = [st.bucket_of(lengths[i], buckets) for i in items]
    out["length"] = []
    for k, (lo, hi) in enumerate(buckets):
        keep = [j for j in range(len(items)) if bucket[j] == k]
        if not keep:
            continue
        for m in models:
            for s in sizes:
                d = st.differences(y[m], s, "text")
                out["length"].append(st.test_row(m, [d[j] for j in keep],
                                                 [projects[j] for j in keep],
                                                 size=s, bucket=f"{lo}-{hi}"))

    cells = data["cells"]
    out["floor_ceiling"] = {
        inp.name(m): {c: {"none": sum(max(ys) == 0 for ys in cells[m][c]) / len(items),
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
    rep = {"settings": {"models": [inp.name(m) for m in inp.model_set(cfg)], "seed": seed,
                        "n_boot": n_boot, "level": st.LEVEL, "length_buckets": buckets,
                        "length_column": inp.LENGTH_COLUMN,
                        "interval": "CR1 cluster t with G - 1 df; item line: paired t",
                        "pooled_interval": "95% equal-tailed, type-1 percentiles"},
           "benchmarks": {}}
    for b, (data, lengths) in inputs.items():
        rep["benchmarks"][b] = benchmark_gaps(data, lengths, buckets, f"{seed}-{b}", n_boot)
    for key, how in (("main", "holm"), ("sizes", "bh"), ("size_diffs", "bh"), ("length", "bh")):
        st.adjust([r for v in rep["benchmarks"].values() for r in v[key]], how, how)
    return rep


CLAUDE_DROPPED = ("pooled", "ranks", "length", "all_none", "never_passed", "output_tokens")
CLAUDE_BH = "the per-size gaps, the size differences and the gaps without flagged items"


def token_ratio_mean(data):
    """The item mean of image over text prompt tokens (run 0), the addendum's wording."""
    tok, sizes = data["tokens"], data["conditions"][1:]
    out = {}
    for m in data["models"]:
        r = {s: st.mean([a / t for a, t in zip(tok[m][s], tok[m]["text"])]) for s in sizes}
        r["mean_over_sizes"] = st.mean([r[s] for s in sizes])
        out[inp.name(m)] = r
    return out


def claude_gaps_report(cfg, inputs, copies_by_bench, seed=rs.SEED, n_boot=rs.N_BOOT,
                       control_seed=ctm.CONTROL_SEED, n_draws=None):
    """The Claude models' own gaps (methodology addendum): Holm over their size-averaged gaps and
    one BH set over CLAUDE_BH, apart from the 5-model families. inputs[b] is the load_claude
    output and the item lengths; copies_by_bench[b] the text copies of every model."""
    n_draws = n_draws or ctm.CONTROL["draws"]
    buckets = cfg["sample"]["deveval_buckets"]
    seven = set(inp.model_set(cfg, "all"))
    rep = {"settings": {"models": [inp.name(m) for m in inp.model_set(cfg, "claude")],
                        "runs": list(range(inp.LINE_RUNS)), "seed": seed, "n_boot": n_boot,
                        "level": st.LEVEL,
                        "interval": "CR1 cluster t with G - 1 df; item line: paired t",
                        "short_cell": "stops the command",
                        "token_ratio": ("median per-item ratio, as the open models; "
                                        "token_ratio_mean is the item mean"),
                        "control_draws": n_draws, "control_seed": control_seed,
                        "bins": ctm.CONTROL["bins"]},
           "benchmarks": {}}
    for b, (data, lengths) in inputs.items():
        v = benchmark_gaps(data, lengths, buckets, f"{seed}-{b}", n_boot)
        for k in CLAUDE_DROPPED:
            del v[k]
        v["token_ratio_mean"] = token_ratio_mean(data)
        errors = Counter((r["model"], r["condition"]) for r in data["rows"]
                         if r["reason"] == "request_error")
        v["request_errors"] = {inp.name(m): {c: errors[(m, c)] for c in data["conditions"]}
                               for m in data["models"]}
        copies = {k: x for k, x in copies_by_bench[b].items() if k[0] in seven}
        v["contamination"] = ctm.claude_contamination(b, data, lengths, copies,
                                                      f"{control_seed}-{b}", n_draws)
        rep["benchmarks"][b] = v
    found = rep["benchmarks"].values()
    st.adjust([r for v in found for r in v["main"]], "holm", "holm")
    family = ([r for k in ("sizes", "size_diffs") for v in found for r in v[k]]
              + [r for v in found for r in v["contamination"]["gaps"]])
    st.adjust(family, "bh", "bh")
    rep["settings"]["holm_rows"] = sum(len(v["main"]) for v in found)
    rep["settings"]["bh_set"] = {"rows": len(family), "covers": CLAUDE_BH}
    return rep


def ranks_report(line, seed=rs.SEED, n_boot=None):
    """Rates, ranks with resample intervals and pair swap probabilities of the 7-model line, from
    the reliability code and the scripts/resample.py draws, keyed by display name."""
    n_boot = n_boot or rs.N_BOOT
    models = next(iter(line.values()))["models"]
    rep = {"settings": {"models": [inp.name(m) for m in models], "runs": list(range(inp.LINE_RUNS)),
                        "drop_rule": inp.DROP_RULE, "seed": seed, "n_boot": n_boot,
                        "interval": "95% equal-tailed, type-1 percentiles"},
           "benchmarks": {}}
    for b, data in line.items():
        items, projects = data["items"], data["projects"]
        groups = ds.clusters(b, items, dict(zip(items, projects)))
        res = rel.rank_stability(data, groups, f"{seed}-{b}", n_boot)
        shown = {rel.name(m): inp.name(m) for m in models}
        rep["benchmarks"][b] = {
            "n_items": len(items), "n_clusters": len(groups),
            "dropped": {"count": len(data["dropped"]), "items": data["dropped"]},
            "excluded": {"count": len(data["excluded"]), "items": data["excluded"]},
            "rates": {c: {shown[k]: v for k, v in x.items()} for c, x in res["rates"].items()},
            "ranks": {c: {shown[k]: v for k, v in x.items()} for c, x in res["ranks"].items()},
            "swap": [{"pair": [shown[k] for k in s["pair"]], "p": s["p"]} for s in res["swap"]]}
    return rep
