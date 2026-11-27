import copy
import json
import os
import random
from collections import Counter

import pytest
from conftest import ROOT, need

from codeimg import config
from codeimg.analysis import cli
from codeimg.analysis import contamination as ctm
from codeimg.analysis import figures as figs
from codeimg.analysis import gaps as gp
from codeimg.analysis import inputs as inp
from codeimg.analysis import reliability as rel
from codeimg.analysis import replies as rpl
from codeimg.analysis import report as rpt
from codeimg.analysis import resample as rs
from codeimg.analysis import stats as st
from codeimg.answers import answer_key

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
    assert inp.model_set(cfg) == list(rel.ds.NAMES)
    cfg = copy.deepcopy(cfg)
    cfg["models"] = {"six": {"repo": SIXTH}, **cfg["models"]}
    assert inp.model_set(cfg) == list(rel.ds.NAMES) + [SIXTH]


def test_each_item_weighs_the_same_and_the_gap_is_image_minus_text():
    m = next(iter(rel.ds.NAMES))
    passes = {"A": {"text": [1, 1, 0], **{c: [0, 0, 0] for c in CONDS[1:]}},
              "B": {"text": [0, 0], **{c: [1, 1] for c in CONDS[1:]}}}
    rows, items, parts = toy([m], passes, {"A": "p", "B": "q"})
    data = inp.load_benchmark("deveval", rows, items, [m], CONDS, parts)
    y = st.scores(data)
    d = st.differences(y[m], CONDS[1:], "text")
    # item A loses 2/3, item B gains 1; pooling the 5 answers instead would give 0
    assert d == pytest.approx([-2 / 3, 1])
    assert st.mean(d) == pytest.approx(1 / 6)


def test_pooled_interval_is_the_mean_gap_per_draw():
    d = {"m1": [-1, 0, -0.5, 1, -1, 0], "m2": [0, -0.5, -1, -1, 0.5, 0]}
    groups = [[0, 1], [2], [3, 4, 5]]
    got = st.pooled(d, groups, "toy-seed", 200)
    per_draw = []
    for idx in rs.cluster_draws(groups, 200, "toy-seed"):
        per_draw.append(sum(sum(d[m][j] for j in idx) / len(idx) for m in d) / 2)
    per_draw.sort()
    assert got["est"] == pytest.approx((sum(d["m1"]) / 6 + sum(d["m2"]) / 6) / 2)
    assert (got["lo"], got["hi"]) == (rel.quantile(per_draw, 0.025),
                                      rel.quantile(per_draw, 0.975))


def test_length_buckets_are_half_open():
    buckets = [[2000, 4000], [4000, 8000], [8000, 12000]]
    assert st.bucket_of(2000, buckets) == 0
    assert st.bucket_of(3999, buckets) == 0
    assert st.bucket_of(4000, buckets) == 1
    assert st.bucket_of(11999, buckets) == 2
    for n in (1999, 12000):
        with pytest.raises(ValueError, match="outside every length bucket"):
            st.bucket_of(n, buckets)


def _six_model_inputs(tmp_path):
    cfg = copy.deepcopy(config.load())
    cfg["models"]["six"] = {"repo": SIXTH}
    models = inp.model_set(cfg)
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
        parts = inp.grid_parts(b, cfg, models, str(tmp_path), str(tmp_path / "dstudy.json"))
        data = inp.load_benchmark(b, rows, items, models, CONDS, parts)
        out[b] = (data, {i: 3000 + 1000 * k for k, i in enumerate(ids)})
    return cfg, out


def test_a_sixth_model_runs_through_gaps_and_prep(tmp_path):
    cfg, inputs = _six_model_inputs(tmp_path)
    rep = gp.gaps_report(cfg, inputs, n_boot=50)
    assert rep["settings"]["models"][-1] == SIXTH
    holm = [r["holm"] for v in rep["benchmarks"].values() for r in v["main"]]
    assert len(holm) == 12 and None not in holm
    assert [r["model"] for r in rep["benchmarks"]["deveval"]["main"]][-1] == SIXTH
    rows = inp.answer_rows(inputs["deveval"][0])
    assert {r[0] for r in rows} == set(inp.model_set(cfg))
    assert len(rows) == 6 * 4 * (3 * 3 + 5 * 2)


def test_an_incomplete_grid_fails():
    m = next(iter(rel.ds.NAMES))
    passes = {"A": {c: [1, 0] for c in CONDS}, "B": {c: [0, 1] for c in CONDS}}
    rows, items, parts = toy([m], passes, {"A": "p", "B": "q"})
    with pytest.raises(ValueError, match="expected grid"):
        inp.load_benchmark("deveval", rows[1:], items, [m], CONDS, parts)


def test_a_model_without_rows_fails():
    m, other = list(rel.ds.NAMES)[:2]
    passes = {"A": {c: [1, 0] for c in CONDS}}
    rows, items, parts = toy([m], passes, {"A": "p"})
    with pytest.raises(ValueError, match="no rows for"):
        inp.load_benchmark("deveval", rows, items, [m, other], CONDS, parts)


def test_an_item_without_a_prompt_count_fails(tmp_path):
    cfg, inputs = _six_model_inputs(tmp_path)
    data, lengths = inputs["deveval"]
    del lengths[data["items"][0]]
    with pytest.raises(ValueError, match="no prompt count"):
        gp.gaps_report(cfg, {"deveval": (data, lengths)}, n_boot=10)


@pytest.fixture(scope="module")
def real():
    need(os.path.join(ROOT, "results", "full", "deveval.collected.jsonl"))
    cfg = config.load()
    return cfg, inp.read_inputs(cfg, inp.FULL)


def test_rates_match_the_reliability_results(real):
    _, inputs = real
    with open(os.path.join(ROOT, "results", "reliability", "reliability.json")) as f:
        rel_rates = json.load(f)["benchmarks"]
    for b, (data, _) in inputs.items():
        y = st.scores(data)
        sizes = data["conditions"][1:]
        for m in data["models"]:
            rate = {c: st.mean(y[m][c]) for c in data["conditions"]}
            rate["image"] = st.mean([rate[c] for c in sizes])
            for c, v in rate.items():
                assert v == pytest.approx(rel_rates[b]["rates"][c][inp.name(m)], abs=5e-7)
            gap = st.mean(st.differences(y[m], sizes, "text"))
            assert gap == pytest.approx(rate["image"] - rate["text"], abs=1e-12)


def test_items_and_draws_are_the_reliability_ones(real):
    _, inputs = real
    for b, (data, _) in inputs.items():
        gone = rel.excluded(b)
        assert len(gone) == {"deveval": 13, "coderujb": 1}[b]
        assert data["items"] == [i for i, _, _ in rel.design(b) if i not in gone]
        assert sorted(data["excluded"]) == sorted(gone)
        groups = rel.ds.clusters(b, data["items"], dict(zip(data["items"], data["projects"])))
        d = {m: st.differences(st.scores(data)[m], data["conditions"][1:], "text")
             for m in data["models"]}
        got = st.pooled(d, groups, f"{rs.SEED}-{b}", 20)
        draws = rs.cluster_draws(groups, 20, f"{rs.SEED}-{b}")
        per = sorted(st.mean([st.mean([d[m][j] for j in idx]) for m in d]) for idx in draws)
        assert (got["lo"], got["hi"]) == (rel.quantile(per, 0.025), rel.quantile(per, 0.975))


def test_only_another_models_text_copy_flags_an_item():
    m1, m2 = list(rel.ds.NAMES)[:2]
    copies = {(m1, "A", 0): True, (m1, "A", 1): False, (m2, "A", 0): False,
              (m2, "B", 1): True, (m1, "C", 0): False}
    flags = ctm.flags_of([m1, m2], ["A", "B", "C", "D"], copies)
    # m1's own copy of A flags A for m2 only; D has no answer at all (no_code) and is not flagged
    assert flags == {m1: {"B"}, m2: {"A"}}


def test_a_graded_text_answer_without_a_reply_fails():
    m = next(iter(rel.ds.NAMES))
    passes = {"A": {c: [1, 0] for c in CONDS}, "B": {c: [0, 1] for c in CONDS}}
    rows, items, parts = toy([m], passes, {"A": "p", "B": "q"})
    for r in rows:
        if r["id"] == "B" and r["condition"] == "text" and r["run"] == 0:
            r["reason"] = "no_code"
    data = inp.load_benchmark("deveval", rows, items, [m], CONDS, parts)
    copies = {(m, "A", 0): False, (m, "A", 1): False, (m, "B", 1): False}
    ctm.check_answers("deveval", data, copies)
    del copies[(m, "A", 1)]
    with pytest.raises(ValueError, match="1 graded text answer"):
        ctm.check_answers("deveval", data, copies)


def test_matched_removals_draw_from_the_pool_by_bin():
    bins = [(k % 3, 0) for k in range(30)]
    flagged = [0, 1, 3, 4]
    pool = set(range(30)) - set(flagged) - {2}
    draws, short = ctm.matched_removals(flagged, bins, pool, 200, "toy")
    assert short == {}
    for dr in draws:
        assert len(dr) == len(set(dr)) == 4
        assert set(dr) <= pool
        assert sorted(bins[j] for j in dr) == sorted(bins[j] for j in flagged)
    assert draws == ctm.matched_removals(flagged, bins, pool, 200, "toy")[0]
    assert draws != ctm.matched_removals(flagged, bins, pool, 200, "other")[0]


def test_a_short_bin_draws_what_it_has_and_says_so():
    bins = [(0, 0)] * 3 + [(1, 0)] * 3
    draws, short = ctm.matched_removals([0, 1], bins, {2, 3}, 5, "toy")
    assert short == {"(0, 0)": 1}
    assert all(dr == [2] for dr in draws)


def test_equal_groups_break_ties_by_id():
    assert ctm.equal_groups([1, 1, 1, 1, 0, 0], ["f", "e", "d", "c", "b", "a"], 3) == [
        2, 2, 1, 1, 0, 0]


def test_contamination_needs_the_glmm_modes(tmp_path):
    with pytest.raises(ValueError, match="run analysis/glmm_main.R first"):
        ctm.read_item_modes(str(tmp_path / "glmm_item_model.csv"))


def test_report_names_the_command_of_a_missing_input(tmp_path):
    (tmp_path / "gaps.json").write_text("{}")
    with pytest.raises(ValueError, match="glmm.json is missing: run analysis/glmm_main.R first"):
        rpt.read_report_inputs(str(tmp_path))
    (tmp_path / "glmm.json").write_text("{}")
    with pytest.raises(ValueError, match="run scripts/analysis.py contamination first"):
        rpt.read_report_inputs(str(tmp_path))


def test_report_formats_points_and_missing_values():
    assert rpt.pp(-0.316585) == "-31.7"
    assert rpt.pp(0.540441, False) == "54.0"
    assert rpt.interval(None, None) == "n/a"
    assert rpt.pval(None) == "n/a" and rpt.pval(3.38e-06) == "3.38e-06"


def test_output_lengths_cover_every_run():
    m = next(iter(rel.ds.NAMES))
    passes = {"A": {c: [1, 0] for c in CONDS}, "B": {c: [0, 1] for c in CONDS}}
    rows, items, parts = toy([m], passes, {"A": "p", "B": "q"})
    for k, r in enumerate(r for r in rows if r["condition"] == "text"):
        r["output_tokens"] = 10 * (k + 1)
    data = inp.load_benchmark("deveval", rows, items, [m], CONDS, parts)
    got = gp.output_lengths(data)[inp.name(m)]
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
    rep = ctm.contamination_report({"deveval": (data, lengths)}, {"deveval": copies}, modes,
                                   n_draws=5)
    rows = rep["benchmarks"]["deveval"]["flagged_only"]
    # the copying model's own items are not flagged for it, so it gets no row
    assert [r["model"] for r in rows] == [inp.name(m) for m in models[1:]]
    y = st.scores(data)[models[1]]
    d = st.differences(y, CONDS[1:], "text")
    r = rows[0]
    assert (r["n"], r["est"]) == (1, pytest.approx(d[0]))
    assert r["text_flagged"] == pytest.approx(y["text"][0])
    assert r["text_rest"] == pytest.approx(st.mean(y["text"][1:]))
    assert r["gap_rest"] == pytest.approx(st.mean(d[1:]))


CLAUDE = ["cl/one", "cl/two"]
_OPEN_A, _OPEN_B = list(rel.ds.NAMES)[:2]
LINE_CFG = {"experiment": {"sizes": [10, 12, 14], "runs": 3},
            "models": {"a": {"repo": _OPEN_A}, "b": {"repo": _OPEN_B}},
            "claude": {"answer_budget": 2048, "one": {"model": CLAUDE[0]},
                       "two": {"model": CLAUDE[1]}}}


def claude_row(m, i, c, r, passed):
    return {**row(m, i, c, r, passed), "seed": None}


def line_fixture(monkeypatch, open_pass, claude_pass):
    """Items A to D; open models have 3 runs on A and 2 elsewhere, Claude 2 runs everywhere.
    open_pass[m] and claude_pass[m] give each model's verdict for text and for the image sizes."""
    opens = inp.model_set(LINE_CFG)
    items = [(i, "p" if i in "AB" else "q", 3 if i == "A" else 2) for i in "ABCD"]
    parts = [(["A"], dict.fromkeys(opens, 3)), (["B", "C", "D"], dict.fromkeys(opens, 2))]
    monkeypatch.setattr(inp, "grid_parts", lambda b, cfg, models: parts)
    open_rows = [row(m, i, c, r, open_pass[m][c != "text"]) for m in opens
                 for i, _, n in items for c in CONDS for r in range(n)]
    claude_rows = [claude_row(m, i, c, r, claude_pass[m][c != "text"]) for m in CLAUDE
                   for i, _, _ in items for c in CONDS for r in range(2)]
    return open_rows, claude_rows, items


def plain_fixture(monkeypatch):
    opens = inp.model_set(LINE_CFG)
    return line_fixture(monkeypatch, dict.fromkeys(opens, (1, 0)), dict.fromkeys(CLAUDE, (0, 1)))


def test_the_all_set_adds_the_claude_models_in_config_order():
    cfg = config.load()
    claude = [v["model"] for v in config.claude_models(cfg).values()]
    assert claude == ["claude-sonnet-5-5", "claude-opus-5-5"]
    assert inp.model_set(cfg, "all") == list(rel.ds.NAMES) + claude
    assert inp.model_set(cfg) == list(rel.ds.NAMES)
    assert [inp.name(m) for m in claude] == ["Claude Sonnet 5.5", "Claude Opus 5.5"]
    assert inp.name(SIXTH) == SIXTH


def test_the_all_set_needs_a_claude_table():
    cfg = {k: v for k, v in LINE_CFG.items() if k != "claude"}
    with pytest.raises(ValueError, match=r"needs the \[claude\] table"):
        inp.model_set(cfg, "all")


def test_the_line_keeps_runs_0_and_1_of_every_model(monkeypatch):
    open_rows, claude_rows, items = plain_fixture(monkeypatch)
    data = inp.load_line("deveval", open_rows, claude_rows, items, LINE_CFG)
    assert data["models"] == inp.model_set(LINE_CFG) + CLAUDE
    assert data["dropped"] == [] and data["items"] == list("ABCD")
    assert all(len(ys) == 2 for m in data["models"] for c in CONDS for ys in data["cells"][m][c])
    assert {r[4] for r in inp.answer_rows(data)} == {0, 1}
    # the copy check still sees run 2 of the open models
    assert any(r["run"] == 2 for r in data["rows"])


def test_a_claude_null_seed_passes_and_an_open_seed_mismatch_fails(monkeypatch):
    open_rows, claude_rows, items = plain_fixture(monkeypatch)
    inp.load_line("deveval", open_rows, claude_rows, items, LINE_CFG)
    open_rows[0]["seed"] = None
    with pytest.raises(ValueError, match="seed_not_run"):
        inp.load_line("deveval", open_rows, claude_rows, items, LINE_CFG)


@pytest.mark.parametrize("change, problem", [
    (lambda rows: rows[1:], "missing"),
    (lambda rows: rows + [claude_row(CLAUDE[0], "A", "text", 2, True)], "extra"),
    (lambda rows: rows + rows[:1], "duplicates"),
])
def test_a_claude_grid_problem_fails(monkeypatch, change, problem):
    open_rows, claude_rows, items = plain_fixture(monkeypatch)
    with pytest.raises(ValueError, match=problem):
        inp.load_line("deveval", open_rows, change(claude_rows), items, LINE_CFG)


def test_a_null_verdict_other_than_a_request_error_fails(monkeypatch):
    open_rows, claude_rows, items = plain_fixture(monkeypatch)
    claude_rows[0]["passed"] = None
    with pytest.raises(ValueError, match="null_passed"):
        inp.load_line("deveval", open_rows, claude_rows, items, LINE_CFG)


def test_a_request_error_drops_its_item_from_every_condition_and_model(monkeypatch):
    open_rows, claude_rows, items = plain_fixture(monkeypatch)
    r = next(r for r in claude_rows if (r["id"], r["condition"]) == ("B", "image12"))
    r.update(passed=None, reason="request_error")
    data = inp.load_line("deveval", open_rows, claude_rows, items, LINE_CFG)
    assert data["dropped"] == ["B"] and data["items"] == ["A", "C", "D"]
    assert {i for _, i, *_ in inp.answer_rows(data)} == {"A", "C", "D"}
    assert "B" in data["all_items"]


def test_fewer_than_two_items_left_fails(monkeypatch):
    open_rows, claude_rows, items = plain_fixture(monkeypatch)
    for r in claude_rows:
        if r["id"] != "A" and r["run"] == 0 and r["condition"] == "text":
            r.update(passed=None, reason="request_error")
    with pytest.raises(ValueError, match="1 item"):
        inp.load_line("deveval", open_rows, claude_rows, items, LINE_CFG)


def test_line_ranks_and_swaps_match_a_known_order(monkeypatch):
    opens = inp.model_set(LINE_CFG)
    # text order: opens[0] > CLAUDE[0] > CLAUDE[1] = opens[1]; image order reversed for the first
    # two, so that pair swaps in every draw and the tied pair counts half
    open_rows, claude_rows, items = line_fixture(
        monkeypatch, {opens[0]: (1, 0), opens[1]: (0, 0)},
        {CLAUDE[0]: (1, 1), CLAUDE[1]: (0, 0)})
    for r in claude_rows:
        if r["model"] == CLAUDE[0] and r["condition"] == "text" and r["run"] == 1:
            r["passed"] = False
    line = {"deveval": inp.load_line("deveval", open_rows, claude_rows, items, LINE_CFG)}
    rep = gp.ranks_report(line, n_boot=40)["benchmarks"]["deveval"]
    n = [inp.name(m) for m in opens + CLAUDE]
    assert (rep["n_items"], rep["n_clusters"], rep["dropped"]["count"]) == (4, 2, 0)
    assert rep["rates"]["text"] == {n[0]: 1, n[1]: 0, n[2]: 0.5, n[3]: 0}
    assert rep["rates"]["image"] == {n[0]: 0, n[1]: 0, n[2]: 1, n[3]: 0}
    assert {m: v["rank"] for m, v in rep["ranks"]["text"].items()} == {n[0]: 1, n[1]: 3.5,
                                                                      n[2]: 2, n[3]: 3.5}
    assert all(v["lo"] == v["hi"] == v["rank"] for v in rep["ranks"]["text"].values())
    swap = {tuple(s["pair"]): s["p"] for s in rep["swap"]}
    assert len(swap) == 6
    assert swap[(n[0], n[2])] == 1.0
    assert swap[(n[1], n[3])] == 0.5
    assert swap[(n[0], n[1])] == 0.5


def test_line_flags_count_open_run_2_and_ignore_own_copies(monkeypatch):
    open_rows, claude_rows, items = plain_fixture(monkeypatch)
    line = {"deveval": inp.load_line("deveval", open_rows, claude_rows, items, LINE_CFG)}
    models = line["deveval"]["models"]
    copies = {(r["model"], r["id"], r["run"]): False for r in open_rows + claude_rows
              if r["condition"] == "text"}
    copies[(models[0], "A", 2)] = True
    copies[(CLAUDE[1], "D", 0)] = True
    rep = ctm.line_flags_report(line, {"deveval": copies})["benchmarks"]["deveval"]
    flagged = {inp.name(m): k for m, k in zip(models, [1, 2, 2, 1])}
    assert rep["flagged"] == flagged
    assert (rep["copy_answers"], rep["copied_items"]) == (2, 2)


def test_a_claude_answer_that_never_reached_grading_needs_no_reply(monkeypatch):
    open_rows, claude_rows, items = plain_fixture(monkeypatch)
    r = next(r for r in claude_rows if r["condition"] == "text")
    r.update(passed=False, reason="over_budget", defines_target=None)
    data = inp.load_line("deveval", open_rows, claude_rows, items, LINE_CFG)
    copies = {(r["model"], r["id"], r["run"]): False for r in open_rows + claude_rows
              if r["condition"] == "text"}
    del copies[(r["model"], r["id"], r["run"])]
    ctm.check_answers("deveval", data, copies)
    del copies[(CLAUDE[1], "A", 0)]
    with pytest.raises(ValueError, match="1 graded text answer"):
        ctm.check_answers("deveval", data, copies)


def test_the_claude_replies_file_is_required(tmp_path):
    with pytest.raises(ValueError, match="claude_deveval_text.jsonl is missing"):
        ctm.text_copies("deveval", str(tmp_path), ("claude",))


def _line_report_inputs(models):
    """A line report's inputs for any model list: the committed GLMM fit with its model list and
    Wald df set to match, ranks and flags made up."""
    with open(os.path.join(ROOT, "results", "analysis", "glmm.json")) as f:
        glmm = json.load(f)
    for v in glmm["benchmarks"].values():
        v["models"] = models
        v["wald"]["df"] = len(models) - 1
    ranked = {c: {m: {"rank": k + 1, "lo": 1, "hi": len(models)} for k, m in enumerate(models)}
              for c in ("text", "image", "image10", "image12", "image14")}
    ranks = {"settings": {"models": models, "runs": [0, 1], "drop_rule": inp.DROP_RULE,
                          "n_boot": 123, "interval": "95%"},
             "benchmarks": {b: {"n_items": v["n_items"], "n_clusters": v["n_clusters"],
                                "dropped": {"count": 0, "items": []},
                                "rates": {c: dict.fromkeys(models, 0.5) for c in ranked},
                                "ranks": ranked,
                                "swap": [{"pair": [models[0], models[1]], "p": 0.25}]}
                            for b, v in glmm["benchmarks"].items()}}
    ranks["benchmarks"]["deveval"]["dropped"]["count"] = 4
    cont = {"benchmarks": {b: {"copy_answers": 3, "copied_items": 2,
                               "flagged": dict.fromkeys(models, 1)} for b in glmm["benchmarks"]}}
    return {"ranks": ranks, "glmm": glmm, "contamination": cont}


def _main_reports():
    with open(os.path.join(ROOT, "results", "analysis", "glmm.json")) as f:
        glmm = json.load(f)
    with open(os.path.join(ROOT, "results", "analysis", "gaps.json")) as f:
        gaps = json.load(f)
    return gaps, glmm


def _line_text(inputs):
    gaps5, glmm5 = _main_reports()
    rpt.check_line(inputs)
    return "\n".join(rpt.line_sections(inputs, glmm5) + rpt.rank_and_flag_sections(inputs, gaps5))


def test_the_line_report_takes_its_counts_from_the_inputs():
    need(os.path.join(ROOT, "results", "analysis", "glmm.json"))
    seven = _line_text(_line_report_inputs([f"M{k}" for k in range(7)]))
    three = _line_text(_line_report_inputs([f"M{k}" for k in range(3)]))
    assert seven.startswith("## 7-model line") and three.startswith("## 3-model line")
    assert "other 6 models" in seven and "other 2 models" in three
    assert "on 6 df" in seven and "on 2 df" in three
    assert "runs 0 and 1 only" in seven and "use 123 joint cluster draws" in seven
    dv = _main_reports()[1]["benchmarks"]["deveval"]
    assert "CoderUJB 0, DevEval 4" in seven
    assert f"{dv['n_items']} items in {dv['n_clusters']} clusters, 4 dropped." in seven
    assert "Item flags" not in seven
    assert "| M6 |" in seven and "| M6 |" not in three
    # the 5-model column comes from results/analysis
    assert "| 5-model | 7-model |" in seven and "5-model ranks, every run" in seven


def test_the_excluded_note_cites_each_benchmark_decision():
    assert rpt.excluded_note("deveval", {"excluded": {"count": 13}}) == (
        " (13 excluded, see docs/decisions.md 2026-11-25)")
    assert rpt.excluded_note("coderujb", {"excluded": {"count": 1}}) == (
        " (1 excluded, see docs/decisions.md 2026-11-26)")
    assert rpt.excluded_note("coderujb", {"excluded": {"count": 0}}) == ""


def test_the_line_report_fails_when_its_inputs_disagree():
    need(os.path.join(ROOT, "results", "analysis", "glmm.json"))
    inputs = _line_report_inputs(["M0", "M1"])
    n = inputs["glmm"]["benchmarks"]["deveval"]["n_items"]
    inputs["ranks"]["benchmarks"]["deveval"]["n_items"] -= 1
    with pytest.raises(ValueError, match=rf"glmm.json \(2 models, {n} items\) does not match "
                                         rf"ranks.json \(2 models, {n - 1} items\)"):
        rpt.check_line(inputs)
    # a 5-model fit has the line's item count when nothing is dropped
    inputs = _line_report_inputs([f"M{k}" for k in range(7)])
    for v in inputs["glmm"]["benchmarks"].values():
        v["models"] = v["models"][:5]
    n = inputs["glmm"]["benchmarks"]["coderujb"]["n_items"]
    with pytest.raises(ValueError, match=rf"\(5 models, {n} items\) does not match ranks.json "
                                         r"\(7 models"):
        rpt.check_line(inputs)
    inputs = _line_report_inputs(["M0", "M1"])
    del inputs["contamination"]["benchmarks"]["coderujb"]["flagged"]["M1"]
    with pytest.raises(ValueError, match="contamination.json does not flag"):
        rpt.check_line(inputs)


def test_an_open_grid_problem_fails_before_the_trim(monkeypatch):
    open_rows, claude_rows, items = plain_fixture(monkeypatch)
    # run 2 of a block-1 item leaves the line, but its absence is still a hole in the open grid
    open_rows = [r for r in open_rows if not (r["id"] == "A" and r["run"] == 2
                                              and r["condition"] == "image10")]
    with pytest.raises(ValueError, match="missing"):
        inp.load_line("deveval", open_rows, claude_rows, items, LINE_CFG)


@pytest.mark.parametrize("argv, key, want", [
    (["prep"], "scratch", inp.SCRATCH["main"]),
    (["prep", "--models", "all"], "scratch", inp.SCRATCH["all"]),
    (["ranks"], "out", inp.ALL_OUT),
    (["report"], "out", inp.OUT),
    (["report", "--models", "all"], "out", inp.ALL_OUT),
    (["contamination", "--answers", "x"], "out", inp.OUT),
    (["contamination", "--answers", "x", "--models", "all"], "out", inp.ALL_OUT),
    (["gaps"], "out", inp.OUT),
    (["gaps", "--models", "claude", "--answers", "x"], "out", inp.ALL_OUT),
    (["replies", "--run-dir", "x"], "out", inp.ALL_OUT),
])
def test_default_folders_follow_the_model_set(monkeypatch, argv, key, want):
    got = {}
    monkeypatch.setitem(cli.COMMANDS, argv[0], lambda args: got.update(vars(args)))
    cli.main(argv)
    assert got[key] == want
    if argv[0] not in ("report", "replies"):
        assert (got["full"], got["claude_full"]) == (inp.FULL, inp.CLAUDE_FULL)


def simulate_line(full, claude_full, seed=11):
    """Writes open and Claude tables with the keys of the collected ones and random verdicts, and
    one Claude request_error on the first DevEval item. Returns that item."""
    rng = random.Random(seed)
    lost = None
    for src, dst, claude in ((inp.FULL, full, False), (inp.CLAUDE_FULL, claude_full, True)):
        os.makedirs(dst, exist_ok=True)
        for b in rel.ds.BENCHES:
            rows = rel.ds.read_jsonl(need(os.path.join(src, f"{b}.collected.jsonl")))
            for r in rows:
                ok = rng.random() < 0.5
                r.update(passed=ok, reason="pass" if ok else "error", defines_target=True)
            if claude and b == "deveval":
                lost = rel.design(b)[0][0]
                r = next(r for r in rows if r["id"] == lost and r["condition"] == "image14")
                r.update(passed=None, reason="request_error", defines_target=None)
            with open(os.path.join(dst, f"{b}.collected.jsonl"), "w") as f:
                f.writelines(json.dumps(r) + "\n" for r in rows)
    return lost


def test_a_simulated_seven_model_line_runs_through_prep_and_ranks(tmp_path, monkeypatch):
    full, claude_full = str(tmp_path / "full"), str(tmp_path / "claude")
    lost = simulate_line(full, claude_full)
    monkeypatch.setattr(rs, "N_BOOT", 20)
    scratch, out = tmp_path / "scratch", tmp_path / "out"
    src = ["--full", full, "--claude-full", claude_full]
    cli.main(["prep", "--models", "all", *src, "--scratch", str(scratch)])
    cli.main(["ranks", *src, "--out", str(out)])
    cfg = config.load()
    models = inp.model_set(cfg, "all")
    rep = json.loads((out / "ranks.json").read_text())
    assert rep["settings"]["models"] == [inp.name(m) for m in models]
    assert rep["settings"]["n_boot"] == 20
    for b in rel.ds.BENCHES:
        csv = rel.read_csv(str(scratch / f"{b}_answers.csv"), rel.ANSWER_FIELDS)
        assert list(dict.fromkeys(r["model"] for r in csv)) == models
        assert {r["run"] for r in csv} == {"0", "1"}
        n = len(rel.design(b)) - len(rel.excluded(b)) - (b == "deveval")
        v = rep["benchmarks"][b]
        assert v["n_items"] == n == len({r["item"] for r in csv})
        assert v["dropped"] == ({"count": 1, "items": [lost]} if b == "deveval"
                                else {"count": 0, "items": []})
        assert v["excluded"]["count"] == len(rel.excluded(b))
        assert all(len(x) == 7 for x in v["ranks"].values())
        assert len(v["swap"]) == 21
    assert lost not in {r["item"] for r in rel.read_csv(str(scratch / "deveval_answers.csv"),
                                                        rel.ANSWER_FIELDS)}


def test_line_contamination_runs_through_the_command(tmp_path, monkeypatch):
    full, claude_full = str(tmp_path / "full"), str(tmp_path / "claude")
    simulate_line(full, claude_full)
    answers, out = tmp_path / "answers", tmp_path / "out"
    answers.mkdir()
    copied = None
    gone = set(rel.excluded("deveval"))
    for b in rel.ds.BENCHES:
        for src, part in ((full, "block1"), (claude_full, "claude")):
            text = [r for r in rel.ds.read_jsonl(os.path.join(src, f"{b}.collected.jsonl"))
                    if r["condition"] == "text"]
            if b == "deveval" and part == "block1":
                copied = next(r for r in text if r["run"] == 2 and r["id"] not in gone)
            # an exact copy of an excluded item must not be counted anywhere
            excluded_copy = next((r for r in text if r["id"] in gone), None)
            replies = [{"key": r["key"], "task_id": r["key"], "model": r["model"], "id": r["id"],
                        "completion": "x = 1" if r is copied or r is excluded_copy else "y = 2",
                        "source": "class X {}" if r is copied else "class Y {}"} for r in text]
            with open(answers / f"{part}_{b}_text.jsonl", "w") as f:
                f.writelines(json.dumps(a) + "\n" for a in replies)
        (answers / f"rest_{b}_text.jsonl").write_text("")
        ids = {r["id"] for r in rel.ds.read_jsonl(os.path.join(full, f"{b}.collected.jsonl"))}
        refs = ([{"id": i, "completion": "x = 1"} for i in ids] if b == "deveval" else
                [{"task_id": i, "source": "class Z {}", "start": 0, "end": 0} for i in ids])
        name = "deveval_gold.jsonl" if b == "deveval" else "coderujb_items.jsonl"
        with open(answers / name, "w") as f:
            f.writelines(json.dumps(r) + "\n" for r in refs)
    cli.main(["contamination", "--models", "all", "--full", full, "--claude-full", claude_full,
             "--answers", str(answers), "--out", str(out)])
    rep = json.loads((out / "contamination.json").read_text())
    models = inp.model_set(config.load(), "all")
    dv = rep["benchmarks"]["deveval"]
    assert dv["flagged"] == {inp.name(m): int(m != copied["model"]) for m in models}
    assert (dv["copy_answers"], dv["copied_items"]) == (1, 1)
    assert rep["benchmarks"]["coderujb"]["copy_answers"] == 0
    flags = rel.read_csv(str(out / "contamination_flags.csv"), inp.FLAG_FIELDS)
    assert [(r["item"], r["copied_by"], r["run"]) for r in flags] == [
        (copied["id"], copied["model"], "2")]


CLAUDE_CFG = {**LINE_CFG, "sample": {"deveval_buckets": [[0, 10 ** 6]]}}
ITEMS8 = [(i, f"p{k % 4}", 2) for k, i in enumerate("ABCDEFGH")]


def claude_tables(seed=3):
    """Random Claude verdicts on 8 items in 4 projects for both benchmarks, with prompt tokens
    that differ per item, so the token ratio has a median and a mean that differ."""
    rng = random.Random(seed)
    out = {}
    for b in rel.ds.BENCHES:
        out[b] = [{**claude_row(m, i, c, r, rng.random() < (0.8 if c == "text" else 0.6)),
                   "benchmark": b,
                   "prompt_tokens": 1000 + 10 * k if c == "text" else 400 + k * k + int(c[5:])}
                  for m in CLAUDE for k, (i, _, _) in enumerate(ITEMS8) for c in CONDS
                  for r in range(2)]
    return out


def claude_inputs(seed=3):
    return {b: (inp.load_claude(b, rows, ITEMS8, CLAUDE_CFG), {i: 100 for i, _, _ in ITEMS8})
            for b, rows in claude_tables(seed).items()}


def claude_copies():
    """Open model A copies item A, Claude one copies B, and a model outside the seven copies C."""
    seven = inp.model_set(CLAUDE_CFG, "all")
    out = {}
    for b in rel.ds.BENCHES:
        c = {(m, i, r): False for m in seven for i, _, _ in ITEMS8 for r in range(2)}
        c[(seven[0], "A", 0)] = True
        c[(CLAUDE[0], "B", 1)] = True
        c[("zz/other", "C", 0)] = True
        out[b] = c
    return out


def claude_report():
    return gp.claude_gaps_report(CLAUDE_CFG, claude_inputs(), claude_copies(), n_boot=20,
                                 n_draws=10)


def test_the_claude_set_is_the_claude_models_alone():
    assert inp.model_set(CLAUDE_CFG, "claude") == CLAUDE


def test_claude_gaps_have_their_own_holm_and_one_bh_set_of_40():
    rep = claude_report()
    found = list(rep["benchmarks"].values())
    main = [r for v in found for r in v["main"]]
    assert len(main) == rep["settings"]["holm_rows"] == 4
    assert [r["holm"] for r in main] == st.holm([r["cluster"]["p"] for r in main])
    family = ([r for k in ("sizes", "size_diffs") for v in found for r in v[k]]
              + [r for v in found for r in v["contamination"]["gaps"]])
    assert len(family) == rep["settings"]["bh_set"]["rows"] == 40
    assert [r["bh"] for r in family] == st.bh([r["cluster"]["p"] for r in family])
    for v in found:
        assert not set(gp.CLAUDE_DROPPED) & set(v)


def test_the_claude_token_ratio_mean_is_the_item_mean():
    data, _ = claude_inputs()["deveval"]
    v = claude_report()["benchmarks"]["deveval"]
    m = CLAUDE[0]
    ratios = sorted((400 + k * k + 12) / (1000 + 10 * k) for k in range(8))
    assert v["token_ratio_mean"][m]["image12"] == pytest.approx(sum(ratios) / 8)
    assert v["token_ratio"][m]["image12"] == ratios[3]
    assert v["request_errors"][m] == dict.fromkeys(CONDS, 0)
    assert data["models"] == CLAUDE


def test_claude_flags_come_from_any_other_of_the_seven_models():
    for v in claude_report()["benchmarks"].values():
        k = v["contamination"]
        # A from an open model flags both; B, copied by Claude one, flags only Claude two; the
        # copy by a model outside the seven flags nothing
        assert k["flagged"] == {CLAUDE[0]: 1, CLAUDE[1]: 2}
        assert k["own_copies"] == {CLAUDE[0]: {"answers": 1, "items": 1},
                                   CLAUDE[1]: {"answers": 0, "items": 0}}
        removed = {(r["model"], r["gap"]): r["removed"] for r in k["gaps"]}
        assert len(k["gaps"]) == 8 and removed[(CLAUDE[1], "mean")] == 2
        assert [r["model"] for r in k["flagged_only"]] == CLAUDE
        assert set(k["control"]) == set(CLAUDE)
        assert all("shortfall" in c for c in k["control"].values())


def test_a_short_claude_cell_stops_the_claude_gaps():
    rows = claude_tables()["deveval"]
    rows[5].update(passed=None, reason="request_error")
    with pytest.raises(ValueError, match="1 Claude cell"):
        inp.load_claude("deveval", rows, ITEMS8, CLAUDE_CFG)


def test_a_claude_text_answer_without_a_reply_stops_the_claude_gaps():
    copies = claude_copies()
    del copies["deveval"][(CLAUDE[1], "D", 1)]
    with pytest.raises(ValueError, match="1 graded text answer"):
        gp.claude_gaps_report(CLAUDE_CFG, claude_inputs(), copies, n_boot=20, n_draws=10)


@pytest.mark.parametrize("argv", [["gaps", "--models", "claude"], ["gaps", "--answers", "x"]])
def test_answers_goes_with_the_claude_gaps_only(argv):
    with pytest.raises(SystemExit):
        cli.main(argv)


@pytest.fixture
def fresh_names():
    """inp.name caches the Claude names of the first config it reads, so a test that patches
    config.load starts and ends with an empty cache."""
    inp._claude_names.cache_clear()
    yield
    inp._claude_names.cache_clear()


def test_the_claude_gaps_write_no_figures(tmp_path, monkeypatch, fresh_names):
    monkeypatch.setattr(config, "load", lambda: CLAUDE_CFG)
    monkeypatch.setattr(inp, "read_claude", lambda cfg, path: claude_inputs())
    monkeypatch.setattr(ctm, "text_copies", lambda b, path, parts: claude_copies()[b])
    monkeypatch.setattr(rs, "N_BOOT", 20)
    cli.main(["gaps", "--models", "claude", "--answers", "x", "--out", str(tmp_path)])
    assert os.listdir(tmp_path) == ["gaps.json"]


def fake_run():
    """Claude replies on items A and B, run 0, with one of each event: a refusal and a max_tokens
    stop for Claude one (text), a reply with thinking and cache tokens and a request_error for
    Claude two (image10), and an over_budget reply for Claude two (text)."""
    collected, gens, logs = [], {}, {}
    for short, m in (("one", CLAUDE[0]), ("two", CLAUDE[1])):
        gens[short], logs[short] = [], []
        for i in "AB":
            for c in CONDS:
                collected.append(claude_row(m, i, c, 0, True))
                gens[short].append({"id": i, "condition": c, "run": 0, "fail_reason": None})
                logs[short].append({"kind": "result", "key": ["deveval", i, c, 0],
                                    "type": "succeeded", "stop_reason": "end_turn",
                                    "stop_details": None,
                                    "usage": {"input_tokens": 10, "output_tokens": 100,
                                              "thinking_tokens": 0,
                                              "cache_creation_input_tokens": 0,
                                              "cache_read_input_tokens": 0}})
        logs[short].append({"kind": "batch"})

    def at(table, short, i, c):
        rows = table[short] if isinstance(table, dict) else table
        model = {"one": CLAUDE[0], "two": CLAUDE[1]}[short]
        return next(r for r in rows if r.get("model", model) == model
                    and (r.get("id") or r["key"][1]) == i
                    and (r.get("condition") or r["key"][2]) == c)

    at(logs, "one", "A", "text").update(stop_reason="refusal", stop_details={"category": "cyber"})
    at(logs, "one", "B", "text")["stop_reason"] = "max_tokens"
    at(collected, "one", "B", "text")["truncated"] = True
    at(logs, "two", "A", "image10")["usage"].update(
        thinking_tokens=30, cache_creation_input_tokens=7, cache_read_input_tokens=5)
    logs["two"].remove(at(logs, "two", "B", "image10"))
    at(gens, "two", "B", "image10")["fail_reason"] = "request_error"
    at(collected, "two", "B", "image10").update(passed=None, reason="request_error")
    at(gens, "two", "A", "text")["fail_reason"] = "over_budget"
    at(collected, "two", "A", "text").update(passed=False, reason="over_budget")
    return collected, gens, logs, at


def write_run(path, gens, logs):
    os.makedirs(path / "deveval" / "gen")
    os.makedirs(path / "claude")
    for short in gens:
        with open(path / "deveval" / "gen" / f"claude_{short}.jsonl", "w") as f:
            f.writelines(json.dumps(r) + "\n" for r in gens[short])
        with open(path / "claude" / f"{short}.log.jsonl", "w") as f:
            f.writelines(json.dumps(r) + "\n" for r in logs[short])


def replies_of(path, collected):
    return rpl.replies_report(LINE_CFG, str(path), {"deveval": collected}, benches=("deveval",))


def test_replies_count_each_event_per_model_and_condition(tmp_path):
    collected, gens, logs, _ = fake_run()
    write_run(tmp_path, gens, logs)
    rep = replies_of(tmp_path, collected)["benchmarks"]["deveval"]
    one, two = rep[CLAUDE[0]], rep[CLAUDE[1]]
    assert (one["text"]["replies"], one["text"]["refusals"], one["text"]["max_tokens"]) == (
        2, {"cyber": 1}, 1)
    assert one["image10"]["refusals"] == {} and one["image10"]["max_tokens"] == 0
    x = two["image10"]
    assert (x["replies"], x["request_errors"], x["with_thinking"]) == (2, 1, 1)
    assert x["thinking_share"] == pytest.approx(0.3)
    assert x["output_tokens"]["median"] == x["output_tokens"]["mean"] == 70
    assert (x["cache_creation_tokens"], x["cache_read_tokens"]) == (7, 5)
    assert two["text"]["over_budget"] == 1 and two["image12"]["over_budget"] == 0
    assert two["image12"]["thinking_share"] == 0 and two["image12"]["other_stops"] == {}


def test_replies_stop_when_a_reply_has_no_succeeded_result(tmp_path):
    collected, gens, logs, at = fake_run()
    logs["one"].remove(at(logs, "one", "A", "image14"))
    write_run(tmp_path, gens, logs)
    with pytest.raises(ValueError, match="has 0 succeeded results"):
        replies_of(tmp_path, collected)


def test_replies_stop_when_the_gen_rows_differ_from_the_collected_ones(tmp_path):
    collected, gens, logs, at = fake_run()
    gens["two"].remove(at(gens, "two", "B", "text"))
    write_run(tmp_path, gens, logs)
    with pytest.raises(ValueError, match="key for key"):
        replies_of(tmp_path, collected)


def test_replies_stop_when_a_fail_reason_differs_from_the_collected_reason(tmp_path):
    collected, gens, logs, at = fake_run()
    at(gens, "one", "A", "image12")["fail_reason"] = "over_budget"
    write_run(tmp_path, gens, logs)
    with pytest.raises(ValueError, match="gen fail_reason over_budget but the collected reason "
                                         "is pass"):
        replies_of(tmp_path, collected)


def test_replies_stop_when_max_tokens_differs_from_the_truncated_count(tmp_path):
    collected, gens, logs, at = fake_run()
    at(collected, "one", "B", "text")["truncated"] = False
    write_run(tmp_path, gens, logs)
    with pytest.raises(ValueError, match="1 replies at max_tokens but 0 truncated"):
        replies_of(tmp_path, collected)


C_MODELS = ["o1", "o2", "o3", "c1", "c2"]


def c_glmm(ses=(0.1, 0.2, 0.3, 0.4, 0.5)):
    est = [-1.0, -2.0, -3.0, -0.5, -0.1]
    return {"models": C_MODELS, "contrast": [{"model": m, "est": e, "se": s}
                                             for m, e, s in zip(C_MODELS, est, ses)]}


def c_cov(ses=(0.1, 0.2, 0.3, 0.4, 0.5), off=0.001):
    return {(a, b): (ses[i] ** 2 if a == b else off) for i, a in enumerate(C_MODELS)
            for b in C_MODELS}


def test_c_is_the_claude_mean_minus_the_open_mean():
    c = rpt.open_closed(c_glmm(), c_cov(), {"c1", "c2"})
    # (-0.5 - 0.1) / 2 - (-1 - 2 - 3) / 3
    assert c["est"] == pytest.approx(1.7)
    w = [-1 / 3] * 3 + [1 / 2] * 2
    want = st.wald_contrast([-1.0, -2.0, -3.0, -0.5, -0.1],
                            [[c_cov()[(a, b)] for b in C_MODELS] for a in C_MODELS], w)
    assert c["se"] == pytest.approx(want["se"]) and (c["closed"], c["open"]) == (2, 3)
    assert rpt.c_reading(c) == "Claude loses less (interval above 0)"


def test_c_needs_every_contrast_and_both_kinds_of_model():
    v = c_glmm()
    v["contrast"].pop()
    with pytest.raises(ValueError, match="no logit contrast for c2"):
        rpt.open_closed(v, c_cov(), {"c1", "c2"})
    with pytest.raises(ValueError, match="needs Claude and open models"):
        rpt.open_closed(c_glmm(), c_cov(), set())


def write_cov(path, cov):
    rows = [("coderujb", a, b, x) for (a, b), x in cov.items()]
    rel.gc.write_csv(str(path), rpt.COV_FIELDS, rows)


@pytest.mark.parametrize("change, problem", [
    (lambda cov: cov.pop(("o1", "c2")), "has no entry for"),
    (lambda cov: cov.update({("o1", "c2"): 0.002}), "is not symmetric"),
    (lambda cov: cov.update({("c1", "c1"): 0.17}), "does not match the glmm.json SE"),
])
def test_a_bad_covariance_file_stops_the_report(tmp_path, change, problem):
    glmm = {"benchmarks": {"coderujb": c_glmm()}}
    cov = c_cov()
    write_cov(tmp_path / "cov.csv", cov)
    assert rpt.read_cov(str(tmp_path / "cov.csv"), glmm)["coderujb"] == cov
    change(cov)
    write_cov(tmp_path / "cov.csv", cov)
    with pytest.raises(ValueError, match=problem):
        rpt.read_cov(str(tmp_path / "cov.csv"), glmm)
    with pytest.raises(ValueError, match="is missing; rerun analysis/glmm_main.R"):
        rpt.read_cov(str(tmp_path / "none.csv"), glmm)


def test_the_claude_flag_counts_must_match_the_line_flags():
    g = claude_report()
    line_c = {"benchmarks": {b: {"flagged": {CLAUDE[0]: 1, CLAUDE[1]: 2, "M0": 9}}
                             for b in g["benchmarks"]}}
    rpt.check_claude_flags(g, line_c)
    line_c["benchmarks"]["deveval"]["flagged"][CLAUDE[1]] = 3
    with pytest.raises(ValueError, match="deveval: the Claude flag counts of gaps.json"):
        rpt.check_claude_flags(g, line_c)


def test_the_claude_findings_go_next_to_the_analysis_folder(tmp_path, monkeypatch, fresh_names):
    out = tmp_path / "claude" / "analysis"
    out.mkdir(parents=True)
    got = {}
    monkeypatch.setattr(config, "load", lambda: CLAUDE_CFG)
    monkeypatch.setattr(rpt, "read_report_inputs", lambda path, wanted: {"gaps": {}, "glmm": {}})
    monkeypatch.setattr(rpt, "read_cov", lambda path, glmm: got.update(cov=path))
    monkeypatch.setattr(rpt, "claude_findings", lambda *a: "text\n")
    monkeypatch.setattr(figs, "claude_figures", lambda g, g5, path: got.update(figures=path))
    cli.main(["report", "--models", "all", "--out", str(out)])
    assert (tmp_path / "claude" / "findings.md").read_text() == "text\n"
    assert not (out / "findings.md").exists()
    assert got == {"cov": str(out / "glmm_contrast_cov.csv"), "figures": str(out / "figures")}


def test_the_paper_paragraph_takes_its_values_and_directions_from_the_inputs():
    g = claude_report()
    g5 = {"benchmarks": {b: {"main": [{"est": -0.30}, {"est": -0.12}]} for b in g["benchmarks"]}}
    gl = {"benchmarks": {b: {"wald": {"stat": 12.34, "df": 6, "p": 0.0123}}
                         for b in g["benchmarks"]}}

    def text(c):
        return rpt.paper_paragraph(g, g5, gl, {b: dict(c) for b in g["benchmarks"]})

    up = text({"est": 0.5, "lo": 0.2, "hi": 0.8})
    r = g["benchmarks"]["deveval"]["main"][1]
    assert f"{rpt.pp(r['est'])} pp" in up and "0.50 [0.20, 0.80]" in up
    assert "-30.0 to -12.0 pp" in up and "on 6 df" in up and "chi2 12.3, p 0.0123" in up
    assert "Claude loses less" in up and "loses more" not in up
    down = text({"est": -0.5, "lo": -0.8, "hi": -0.2})
    assert "Claude loses more" in down and "loses less" not in down
    both = text({"est": 0.1, "lo": -0.2, "hi": 0.4})
    assert "the interval includes 0" in both and "loses" not in both
    k = sum(rpt.excludes_zero(r["cluster"]["lo"], r["cluster"]["hi"])
            for v in g["benchmarks"].values() for r in v["main"])
    assert ("all 4 cluster intervals exclude 0" if k == 4
            else f"{k} of the 4 cluster intervals exclude 0") in up


def test_claude_removal_checks_bin_on_the_claude_text_score():
    inputs = claude_inputs()
    rep = claude_report()["benchmarks"]
    assert sum(len(v["contamination"]["gaps"]) for v in rep.values()) == 16
    for b, (data, lengths) in inputs.items():
        k = rep[b]["contamination"]
        y = st.scores(data)
        items = data["items"]
        text = [st.mean([y[m]["text"][j] for m in CLAUDE]) for j in range(len(items))]
        bins = list(zip(ctm.equal_groups(text, items, ctm.CONTROL["bins"][0]),
                        ctm.equal_groups([lengths[i] for i in items], items,
                                         ctm.CONTROL["bins"][1])))
        m = CLAUDE[1]
        flagged, rest = [0, 1], list(range(2, 8))
        need = Counter(bins[j] for j in flagged)
        have = Counter(bins[j] for j in rest)
        short = {str(x): need[x] - have[x] for x in sorted(need) if need[x] > have[x]}
        c = k["control"][m]
        assert (c["flagged"], c["shortfall"]) == (2, short)
        assert c["removed_per_draw"] == 2 - sum(short.values())
        d = st.differences(y[m], data["conditions"][1:], "text")
        row = next(r for r in k["flagged_only"] if r["model"] == m)
        assert row["text_flagged"] == pytest.approx(st.mean([y[m]["text"][j] for j in flagged]))
        assert row["text_rest"] == pytest.approx(st.mean([y[m]["text"][j] for j in rest]))
        assert row["gap_rest"] == pytest.approx(st.mean([d[j] for j in rest]))
        mean_row = next(r for r in k["gaps"] if r["model"] == m and r["gap"] == "mean")
        assert mean_row["all_items"] == pytest.approx(st.mean(d))
        assert mean_row["est"] == pytest.approx(st.mean([d[j] for j in rest]))
        assert mean_row["removed"] == 2


def test_a_control_with_one_possible_draw_says_it_carries_no_information():
    c = {"flagged": 126, "removed_per_draw": 10}
    assert "carry no information" in rpt.control_note("S", c, 136)
    assert "carry no information" not in rpt.control_note("S", {**c, "removed_per_draw": 9}, 136)


def test_the_paper_paragraph_names_item_level_intervals_that_include_zero():
    g = claude_report()
    g5 = {"benchmarks": {b: {"main": [{"est": -0.30}]} for b in g["benchmarks"]}}
    gl = {"benchmarks": {b: {"wald": {"stat": 1.0, "df": 6, "p": 0.5}} for b in g["benchmarks"]}}
    cs = {b: {"est": 0.5, "lo": 0.2, "hi": 0.8} for b in g["benchmarks"]}
    for v in g["benchmarks"].values():
        for r in v["main"]:
            r["item"] = {**r["item"], "lo": -0.04, "hi": -0.01}
    assert "item-level interval includes 0" not in rpt.paper_paragraph(g, g5, gl, cs)
    r = g["benchmarks"]["deveval"]["main"][1]
    r["item"] = {**r["item"], "lo": -0.043, "hi": 0.004}
    text = rpt.paper_paragraph(g, g5, gl, cs)
    assert (f"item-level interval includes 0 for {r['model']} on DevEval "
            f"{rpt.interval(-0.043, 0.004)}.") in text
