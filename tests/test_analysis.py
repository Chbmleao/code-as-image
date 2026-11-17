import copy
import importlib.util
import json
import os
import random

import pytest
from conftest import ROOT, need

from codeimg import config
from codeimg.answers import answer_key

_spec = importlib.util.spec_from_file_location("analysis",
                                               os.path.join(ROOT, "scripts", "analysis.py"))
an = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(an)
rel, rs = an.rel, an.rs

CONDS = ["text", "image10", "image12", "image14"]
SIXTH = "toy/Model-6"


def row(m, i, c, r, passed, b="deveval", tokens=None):
    return {"key": answer_key(m, i, c, r), "model": m, "benchmark": b, "id": i, "condition": c,
            "run": r, "seed": r, "passed": bool(passed), "reason": "pass" if passed else "error",
            "truncated": False, "output_tokens": 50, "defines_target": True,
            "prompt_tokens": tokens or (1000 if c == "text" else 400)}


def toy(models, passes, projects):
    """passes[item][condition] is the list of runs; one items list for every model."""
    items = [(i, projects[i], len(passes[i]["text"])) for i in passes]
    rows = [row(m, i, c, r, y) for m in models for i in passes for c in CONDS
            for r, y in enumerate(passes[i][c])]
    parts = [([i for i, _, n in items if n == k], dict.fromkeys(models, k)) for k in (2, 3)]
    return rows, items, parts


def test_model_set_follows_the_config_with_new_models_last():
    cfg = config.load()
    assert an.model_set(cfg) == list(rel.ds.NAMES)
    cfg = copy.deepcopy(cfg)
    cfg["models"] = {"six": {"repo": SIXTH}, **cfg["models"]}
    assert an.model_set(cfg) == list(rel.ds.NAMES) + [SIXTH]


def test_each_item_weighs_the_same_and_the_gap_is_image_minus_text():
    m = next(iter(rel.ds.NAMES))
    passes = {"A": {"text": [1, 1, 0], **{c: [0, 0, 0] for c in CONDS[1:]}},
              "B": {"text": [0, 0], **{c: [1, 1] for c in CONDS[1:]}}}
    rows, items, parts = toy([m], passes, {"A": "p", "B": "q"})
    data = an.load_benchmark("deveval", rows, items, [m], CONDS, parts)
    y = an.scores(data)
    d = an.differences(y[m], CONDS[1:], "text")
    # item A loses 2/3, item B gains 1; pooling the 5 answers instead would give 0
    assert d == pytest.approx([-2 / 3, 1])
    assert an.mean(d) == pytest.approx(1 / 6)


def test_pooled_interval_is_the_mean_gap_per_draw():
    d = {"m1": [-1, 0, -0.5, 1, -1, 0], "m2": [0, -0.5, -1, -1, 0.5, 0]}
    groups = [[0, 1], [2], [3, 4, 5]]
    got = an.pooled(d, groups, "toy-seed", 200)
    per_draw = []
    for idx in rs.cluster_draws(groups, 200, "toy-seed"):
        per_draw.append(sum(sum(d[m][j] for j in idx) / len(idx) for m in d) / 2)
    per_draw.sort()
    assert got["est"] == pytest.approx((sum(d["m1"]) / 6 + sum(d["m2"]) / 6) / 2)
    assert (got["lo"], got["hi"]) == (rel.quantile(per_draw, 0.025),
                                      rel.quantile(per_draw, 0.975))


def test_length_buckets_are_half_open():
    buckets = [[2000, 4000], [4000, 8000], [8000, 12000]]
    assert an.bucket_of(2000, buckets) == 0
    assert an.bucket_of(3999, buckets) == 0
    assert an.bucket_of(4000, buckets) == 1
    assert an.bucket_of(11999, buckets) == 2
    for n in (1999, 12000):
        with pytest.raises(ValueError, match="outside every length bucket"):
            an.bucket_of(n, buckets)


def _six_model_inputs(tmp_path):
    cfg = copy.deepcopy(config.load())
    cfg["models"]["six"] = {"repo": SIXTH}
    models = an.model_set(cfg)
    inputs, dstudy = {}, {"rows": []}
    for b in ("coderujb", "deveval"):
        ids = [f"{b}{k}" for k in range(8)]
        os.makedirs(tmp_path / "block1", exist_ok=True)
        os.makedirs(tmp_path / "rest", exist_ok=True)
        (tmp_path / "block1" / f"{b}.txt").write_text("\n".join(ids[:3]) + "\n")
        (tmp_path / "rest" / f"{b}.txt").write_text("\n".join(ids[3:]) + "\n")
        dstudy["rows"] += [{"benchmark": b, "model": m, "runs": 2} for m in models]
        inputs[b] = ids
    (tmp_path / "dstudy.json").write_text(json.dumps(dstudy))
    out = {}
    rng = random.Random(7)
    for b, ids in inputs.items():
        items = [(i, f"P{k % 3}", 3 if k < 3 else 2) for k, i in enumerate(ids)]
        rows = [row(m, i, c, r, rng.random() < 0.5, b, 3000 + 1000 * k if c == "text" else 1500)
                for j, m in enumerate(models) for k, (i, _, n) in enumerate(items)
                for c in CONDS for r in range(n)]
        parts = an.grid_parts(b, cfg, models, str(tmp_path), str(tmp_path / "dstudy.json"))
        data = an.load_benchmark(b, rows, items, models, CONDS, parts)
        out[b] = (data, {i: 3000 + 1000 * k for k, i in enumerate(ids)})
    return cfg, out


def test_a_sixth_model_runs_through_gaps_and_prep(tmp_path):
    cfg, inputs = _six_model_inputs(tmp_path)
    rep = an.gaps_report(cfg, inputs, n_boot=50)
    assert rep["settings"]["models"][-1] == SIXTH
    holm = [r["holm"] for v in rep["benchmarks"].values() for r in v["main"]]
    assert len(holm) == 12 and None not in holm
    assert [r["model"] for r in rep["benchmarks"]["deveval"]["main"]][-1] == SIXTH
    rows = an.answer_rows(inputs["deveval"][0])
    assert {r[0] for r in rows} == set(an.model_set(cfg))
    assert len(rows) == 6 * 4 * (3 * 3 + 5 * 2)


def test_an_incomplete_grid_fails():
    m = next(iter(rel.ds.NAMES))
    passes = {"A": {c: [1, 0] for c in CONDS}, "B": {c: [0, 1] for c in CONDS}}
    rows, items, parts = toy([m], passes, {"A": "p", "B": "q"})
    with pytest.raises(ValueError, match="expected grid"):
        an.load_benchmark("deveval", rows[1:], items, [m], CONDS, parts)


def test_a_model_without_rows_fails():
    m, other = list(rel.ds.NAMES)[:2]
    passes = {"A": {c: [1, 0] for c in CONDS}}
    rows, items, parts = toy([m], passes, {"A": "p"})
    with pytest.raises(ValueError, match="no rows for"):
        an.load_benchmark("deveval", rows, items, [m, other], CONDS, parts)


def test_an_item_without_a_prompt_count_fails(tmp_path):
    cfg, inputs = _six_model_inputs(tmp_path)
    data, lengths = inputs["deveval"]
    del lengths[data["items"][0]]
    with pytest.raises(ValueError, match="no prompt count"):
        an.gaps_report(cfg, {"deveval": (data, lengths)}, n_boot=10)


@pytest.fixture(scope="module")
def real():
    need(os.path.join(ROOT, "results", "full", "deveval.collected.jsonl"))
    cfg = config.load()
    return cfg, an.read_inputs(cfg, an.FULL)


def test_rates_match_the_reliability_results(real):
    _, inputs = real
    with open(os.path.join(ROOT, "results", "reliability", "reliability.json")) as f:
        rel_rates = json.load(f)["benchmarks"]
    for b, (data, _) in inputs.items():
        y = an.scores(data)
        sizes = data["conditions"][1:]
        for m in data["models"]:
            rate = {c: an.mean(y[m][c]) for c in data["conditions"]}
            rate["image"] = an.mean([rate[c] for c in sizes])
            for c, v in rate.items():
                assert v == pytest.approx(rel_rates[b]["rates"][c][an.name(m)], abs=5e-7)
            gap = an.mean(an.differences(y[m], sizes, "text"))
            assert gap == pytest.approx(rate["image"] - rate["text"], abs=1e-12)


def test_items_and_draws_are_the_reliability_ones(real):
    _, inputs = real
    for b, (data, _) in inputs.items():
        design = rel.design(b)
        assert data["items"] == [i for i, _, _ in design]
        groups = rel.ds.clusters(b, data["items"], dict(zip(data["items"], data["projects"])))
        d = {m: an.differences(an.scores(data)[m], data["conditions"][1:], "text")
             for m in data["models"]}
        got = an.pooled(d, groups, f"{rs.SEED}-{b}", 20)
        draws = rs.cluster_draws(groups, 20, f"{rs.SEED}-{b}")
        per = sorted(an.mean([an.mean([d[m][j] for j in idx]) for m in d]) for idx in draws)
        assert (got["lo"], got["hi"]) == (rel.quantile(per, 0.025), rel.quantile(per, 0.975))


def test_only_another_models_text_copy_flags_an_item():
    m1, m2 = list(rel.ds.NAMES)[:2]
    copies = {(m1, "A", 0): True, (m1, "A", 1): False, (m2, "A", 0): False,
              (m2, "B", 1): True, (m1, "C", 0): False}
    flags = an.flags_of([m1, m2], ["A", "B", "C", "D"], copies)
    # m1's own copy of A flags A for m2 only; D has no answer at all (no_code) and is not flagged
    assert flags == {m1: {"B"}, m2: {"A"}}


def test_a_graded_text_answer_without_a_reply_fails():
    m = next(iter(rel.ds.NAMES))
    passes = {"A": {c: [1, 0] for c in CONDS}, "B": {c: [0, 1] for c in CONDS}}
    rows, items, parts = toy([m], passes, {"A": "p", "B": "q"})
    for r in rows:
        if r["id"] == "B" and r["condition"] == "text" and r["run"] == 0:
            r["reason"] = "no_code"
    data = an.load_benchmark("deveval", rows, items, [m], CONDS, parts)
    copies = {(m, "A", 0): False, (m, "A", 1): False, (m, "B", 1): False}
    an.check_answers("deveval", data, copies)
    del copies[(m, "A", 1)]
    with pytest.raises(ValueError, match="1 graded text answer"):
        an.check_answers("deveval", data, copies)


def test_matched_removals_draw_from_the_pool_by_bin():
    bins = [(k % 3, 0) for k in range(30)]
    flagged = [0, 1, 3, 4]
    pool = set(range(30)) - set(flagged) - {2}
    draws, short = an.matched_removals(flagged, bins, pool, 200, "toy")
    assert short == {}
    for dr in draws:
        assert len(dr) == len(set(dr)) == 4
        assert set(dr) <= pool
        assert sorted(bins[j] for j in dr) == sorted(bins[j] for j in flagged)
    assert draws == an.matched_removals(flagged, bins, pool, 200, "toy")[0]
    assert draws != an.matched_removals(flagged, bins, pool, 200, "other")[0]


def test_a_short_bin_draws_what_it_has_and_says_so():
    bins = [(0, 0)] * 3 + [(1, 0)] * 3
    draws, short = an.matched_removals([0, 1], bins, {2, 3}, 5, "toy")
    assert short == {"(0, 0)": 1}
    assert all(dr == [2] for dr in draws)


def test_equal_groups_break_ties_by_id():
    assert an.equal_groups([1, 1, 1, 1, 0, 0], ["f", "e", "d", "c", "b", "a"], 3) == [2, 2, 1, 1, 0,
                                                                                        0]


def test_contamination_needs_the_glmm_modes(tmp_path):
    with pytest.raises(ValueError, match="run analysis/glmm_main.R first"):
        an.read_item_modes(str(tmp_path / "glmm_item_model.csv"))


def test_report_names_the_command_of_a_missing_input(tmp_path):
    (tmp_path / "gaps.json").write_text("{}")
    with pytest.raises(ValueError, match="glmm.json is missing: run analysis/glmm_main.R first"):
        an.read_report_inputs(str(tmp_path))
    (tmp_path / "glmm.json").write_text("{}")
    with pytest.raises(ValueError, match="run scripts/analysis.py contamination first"):
        an.read_report_inputs(str(tmp_path))


def test_report_formats_points_and_missing_values():
    assert an.pp(-0.316585) == "-31.7"
    assert an.pp(0.540441, False) == "54.0"
    assert an.interval(None, None) == "n/a"
    assert an.pval(None) == "n/a" and an.pval(3.38e-06) == "3.38e-06"


def test_output_lengths_cover_every_run():
    m = next(iter(rel.ds.NAMES))
    passes = {"A": {c: [1, 0] for c in CONDS}, "B": {c: [0, 1] for c in CONDS}}
    rows, items, parts = toy([m], passes, {"A": "p", "B": "q"})
    for k, r in enumerate(r for r in rows if r["condition"] == "text"):
        r["output_tokens"] = 10 * (k + 1)
    data = an.load_benchmark("deveval", rows, items, [m], CONDS, parts)
    got = an.output_lengths(data)[an.name(m)]
    assert got["text"]["mean"] == pytest.approx(25)
    assert got["text"]["median"] == rel.quantile([10, 20, 30, 40], 0.5)
    assert got["image10"]["mean"] == 50


def test_flagged_items_get_their_own_gap(tmp_path):
    _, inputs = _six_model_inputs(tmp_path)
    data, lengths = inputs["deveval"]
    models, items = data["models"], data["items"]
    copies = {(r["model"], r["id"], r["run"]): False for r in data["rows"]
              if r["condition"] == "text"}
    copies[(models[0], items[0], 0)] = True
    modes = {"deveval": {(m, i): float(k) for m in models for k, i in enumerate(items)}}
    rep = an.contamination_report({"deveval": (data, lengths)}, {"deveval": copies}, modes,
                                  n_draws=5)
    rows = rep["benchmarks"]["deveval"]["flagged_only"]
    # the copying model's own items are not flagged for it, so it gets no row
    assert [r["model"] for r in rows] == [an.name(m) for m in models[1:]]
    y = an.scores(data)[models[1]]
    d = an.differences(y, CONDS[1:], "text")
    r = rows[0]
    assert (r["n"], r["est"]) == (1, pytest.approx(d[0]))
    assert r["text_flagged"] == pytest.approx(y["text"][0])
    assert r["text_rest"] == pytest.approx(an.mean(y["text"][1:]))
    assert r["gap_rest"] == pytest.approx(an.mean(d[1:]))
