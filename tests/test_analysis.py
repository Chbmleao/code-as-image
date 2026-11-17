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
    opens = an.model_set(LINE_CFG)
    items = [(i, "p" if i in "AB" else "q", 3 if i == "A" else 2) for i in "ABCD"]
    parts = [(["A"], dict.fromkeys(opens, 3)), (["B", "C", "D"], dict.fromkeys(opens, 2))]
    monkeypatch.setattr(an, "grid_parts", lambda b, cfg, models: parts)
    open_rows = [row(m, i, c, r, open_pass[m][c != "text"]) for m in opens
                 for i, _, n in items for c in CONDS for r in range(n)]
    claude_rows = [claude_row(m, i, c, r, claude_pass[m][c != "text"]) for m in CLAUDE
                   for i, _, _ in items for c in CONDS for r in range(2)]
    return open_rows, claude_rows, items


def plain_fixture(monkeypatch):
    opens = an.model_set(LINE_CFG)
    return line_fixture(monkeypatch, dict.fromkeys(opens, (1, 0)), dict.fromkeys(CLAUDE, (0, 1)))


def test_the_all_set_adds_the_claude_models_in_config_order():
    cfg = config.load()
    claude = [v["model"] for v in config.claude_models(cfg).values()]
    assert claude == ["claude-sonnet-5-5", "claude-opus-5-5"]
    assert an.model_set(cfg, "all") == list(rel.ds.NAMES) + claude
    assert an.model_set(cfg) == list(rel.ds.NAMES)
    assert [an.name(m) for m in claude] == ["Claude Sonnet 5.5", "Claude Opus 5.5"]
    assert an.name(SIXTH) == SIXTH


def test_the_all_set_needs_a_claude_table():
    cfg = {k: v for k, v in LINE_CFG.items() if k != "claude"}
    with pytest.raises(ValueError, match=r"needs the \[claude\] table"):
        an.model_set(cfg, "all")


def test_the_line_keeps_runs_0_and_1_of_every_model(monkeypatch):
    open_rows, claude_rows, items = plain_fixture(monkeypatch)
    data = an.load_line("deveval", open_rows, claude_rows, items, LINE_CFG)
    assert data["models"] == an.model_set(LINE_CFG) + CLAUDE
    assert data["dropped"] == [] and data["items"] == list("ABCD")
    assert all(len(ys) == 2 for m in data["models"] for c in CONDS for ys in data["cells"][m][c])
    assert {r[4] for r in an.answer_rows(data)} == {0, 1}
    # the copy check still sees run 2 of the open models
    assert any(r["run"] == 2 for r in data["rows"])


def test_a_claude_null_seed_passes_and_an_open_seed_mismatch_fails(monkeypatch):
    open_rows, claude_rows, items = plain_fixture(monkeypatch)
    an.load_line("deveval", open_rows, claude_rows, items, LINE_CFG)
    open_rows[0]["seed"] = None
    with pytest.raises(ValueError, match="seed_not_run"):
        an.load_line("deveval", open_rows, claude_rows, items, LINE_CFG)


@pytest.mark.parametrize("change, problem", [
    (lambda rows: rows[1:], "missing"),
    (lambda rows: rows + [claude_row(CLAUDE[0], "A", "text", 2, True)], "extra"),
    (lambda rows: rows + rows[:1], "duplicates"),
])
def test_a_claude_grid_problem_fails(monkeypatch, change, problem):
    open_rows, claude_rows, items = plain_fixture(monkeypatch)
    with pytest.raises(ValueError, match=problem):
        an.load_line("deveval", open_rows, change(claude_rows), items, LINE_CFG)


def test_a_null_verdict_other_than_a_request_error_fails(monkeypatch):
    open_rows, claude_rows, items = plain_fixture(monkeypatch)
    claude_rows[0]["passed"] = None
    with pytest.raises(ValueError, match="null_passed"):
        an.load_line("deveval", open_rows, claude_rows, items, LINE_CFG)


def test_a_request_error_drops_its_item_from_every_condition_and_model(monkeypatch):
    open_rows, claude_rows, items = plain_fixture(monkeypatch)
    r = next(r for r in claude_rows if (r["id"], r["condition"]) == ("B", "image12"))
    r.update(passed=None, reason="request_error")
    data = an.load_line("deveval", open_rows, claude_rows, items, LINE_CFG)
    assert data["dropped"] == ["B"] and data["items"] == ["A", "C", "D"]
    assert {i for _, i, *_ in an.answer_rows(data)} == {"A", "C", "D"}
    assert "B" in data["all_items"]


def test_fewer_than_two_items_left_fails(monkeypatch):
    open_rows, claude_rows, items = plain_fixture(monkeypatch)
    for r in claude_rows:
        if r["id"] != "A" and r["run"] == 0 and r["condition"] == "text":
            r.update(passed=None, reason="request_error")
    with pytest.raises(ValueError, match="1 item"):
        an.load_line("deveval", open_rows, claude_rows, items, LINE_CFG)


def test_line_ranks_and_swaps_match_a_known_order(monkeypatch):
    opens = an.model_set(LINE_CFG)
    # text order: opens[0] > CLAUDE[0] > CLAUDE[1] = opens[1]; image order reversed for the first
    # two, so that pair swaps in every draw and the tied pair counts half
    open_rows, claude_rows, items = line_fixture(
        monkeypatch, {opens[0]: (1, 0), opens[1]: (0, 0)},
        {CLAUDE[0]: (1, 1), CLAUDE[1]: (0, 0)})
    for r in claude_rows:
        if r["model"] == CLAUDE[0] and r["condition"] == "text" and r["run"] == 1:
            r["passed"] = False
    line = {"deveval": an.load_line("deveval", open_rows, claude_rows, items, LINE_CFG)}
    rep = an.ranks_report(line, n_boot=40)["benchmarks"]["deveval"]
    n = [an.name(m) for m in opens + CLAUDE]
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
    line = {"deveval": an.load_line("deveval", open_rows, claude_rows, items, LINE_CFG)}
    models = line["deveval"]["models"]
    copies = {(r["model"], r["id"], r["run"]): False for r in open_rows + claude_rows
              if r["condition"] == "text"}
    copies[(models[0], "A", 2)] = True
    copies[(CLAUDE[1], "D", 0)] = True
    rep = an.line_flags_report(line, {"deveval": copies})["benchmarks"]["deveval"]
    flagged = {an.name(m): k for m, k in zip(models, [1, 2, 2, 1])}
    assert rep["flagged"] == flagged
    assert (rep["copy_answers"], rep["copied_items"]) == (2, 2)


def test_a_claude_answer_that_never_reached_grading_needs_no_reply(monkeypatch):
    open_rows, claude_rows, items = plain_fixture(monkeypatch)
    r = next(r for r in claude_rows if r["condition"] == "text")
    r.update(passed=False, reason="over_budget", defines_target=None)
    data = an.load_line("deveval", open_rows, claude_rows, items, LINE_CFG)
    copies = {(r["model"], r["id"], r["run"]): False for r in open_rows + claude_rows
              if r["condition"] == "text"}
    del copies[(r["model"], r["id"], r["run"])]
    an.check_answers("deveval", data, copies)
    del copies[(CLAUDE[1], "A", 0)]
    with pytest.raises(ValueError, match="1 graded text answer"):
        an.check_answers("deveval", data, copies)


def test_the_claude_replies_file_is_required(tmp_path):
    with pytest.raises(ValueError, match="claude_deveval_text.jsonl is missing"):
        an.text_copies("deveval", str(tmp_path), ("claude",))


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
    ranks = {"settings": {"models": models, "runs": [0, 1], "drop_rule": an.DROP_RULE,
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


def test_the_line_report_takes_its_counts_from_the_inputs():
    need(os.path.join(ROOT, "results", "analysis", "glmm.json"))
    seven = an.line_findings(_line_report_inputs([f"M{k}" for k in range(7)]))
    three = an.line_findings(_line_report_inputs([f"M{k}" for k in range(3)]))
    assert seven.startswith("# 7-model line") and three.startswith("# 3-model line")
    assert "other 6 models" in seven and "other 2 models" in three
    assert "on 6 df" in seven and "on 2 df" in three
    assert "runs 0 and 1 only" in seven and "use 123 joint cluster draws" in seven
    assert "CoderUJB 0, DevEval 4" in seven and "859 items in 79 clusters, 4 dropped." in seven
    assert "Item flags" not in seven
    assert "| M6 |" in seven and "| M6 |" not in three


def test_the_line_report_fails_when_its_inputs_disagree():
    need(os.path.join(ROOT, "results", "analysis", "glmm.json"))
    inputs = _line_report_inputs(["M0", "M1"])
    inputs["ranks"]["benchmarks"]["deveval"]["n_items"] -= 1
    with pytest.raises(ValueError, match=r"glmm.json \(2 models, 859 items\) does not match "
                                         r"ranks.json \(2 models, 858 items\)"):
        an.line_findings(inputs)
    # a 5-model fit has the line's item count when nothing is dropped
    inputs = _line_report_inputs([f"M{k}" for k in range(7)])
    for v in inputs["glmm"]["benchmarks"].values():
        v["models"] = v["models"][:5]
    with pytest.raises(ValueError, match=r"\(5 models, 136 items\) does not match ranks.json "
                                         r"\(7 models"):
        an.line_findings(inputs)
    inputs = _line_report_inputs(["M0", "M1"])
    del inputs["contamination"]["benchmarks"]["coderujb"]["flagged"]["M1"]
    with pytest.raises(ValueError, match="contamination.json does not flag"):
        an.line_findings(inputs)


def test_an_open_grid_problem_fails_before_the_trim(monkeypatch):
    open_rows, claude_rows, items = plain_fixture(monkeypatch)
    # run 2 of a block-1 item leaves the line, but its absence is still a hole in the open grid
    open_rows = [r for r in open_rows if not (r["id"] == "A" and r["run"] == 2
                                              and r["condition"] == "image10")]
    with pytest.raises(ValueError, match="missing"):
        an.load_line("deveval", open_rows, claude_rows, items, LINE_CFG)


@pytest.mark.parametrize("argv, key, want", [
    (["prep"], "scratch", an.SCRATCH["main"]),
    (["prep", "--models", "all"], "scratch", an.SCRATCH["all"]),
    (["ranks"], "out", an.ALL_OUT),
    (["report"], "out", an.OUT),
    (["report", "--models", "all"], "out", an.ALL_OUT),
    (["contamination", "--answers", "x"], "out", an.OUT),
    (["contamination", "--answers", "x", "--models", "all"], "out", an.ALL_OUT),
])
def test_default_folders_follow_the_model_set(monkeypatch, argv, key, want):
    got = {}
    monkeypatch.setitem(an.COMMANDS, argv[0], lambda args: got.update(vars(args)))
    an.main(argv)
    assert got[key] == want
    if argv[0] != "report":
        assert (got["full"], got["claude_full"]) == (an.FULL, an.CLAUDE_FULL)


def simulate_line(full, claude_full, seed=11):
    """Writes open and Claude tables with the keys of the collected ones and random verdicts, and
    one Claude request_error on the first DevEval item. Returns that item."""
    rng = random.Random(seed)
    lost = None
    for src, dst, claude in ((an.FULL, full, False), (an.CLAUDE_FULL, claude_full, True)):
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
    an.main(["prep", "--models", "all", *src, "--scratch", str(scratch)])
    an.main(["ranks", *src, "--out", str(out)])
    cfg = config.load()
    models = an.model_set(cfg, "all")
    rep = json.loads((out / "ranks.json").read_text())
    assert rep["settings"]["models"] == [an.name(m) for m in models]
    assert rep["settings"]["n_boot"] == 20
    for b in rel.ds.BENCHES:
        csv = rel.read_csv(str(scratch / f"{b}_answers.csv"), rel.ANSWER_FIELDS)
        assert list(dict.fromkeys(r["model"] for r in csv)) == models
        assert {r["run"] for r in csv} == {"0", "1"}
        n = len(rel.design(b)) - (b == "deveval")
        v = rep["benchmarks"][b]
        assert v["n_items"] == n == len({r["item"] for r in csv})
        assert v["dropped"] == ({"count": 1, "items": [lost]} if b == "deveval"
                                else {"count": 0, "items": []})
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
    for b in rel.ds.BENCHES:
        for src, part in ((full, "block1"), (claude_full, "claude")):
            text = [r for r in rel.ds.read_jsonl(os.path.join(src, f"{b}.collected.jsonl"))
                    if r["condition"] == "text"]
            if b == "deveval" and part == "block1":
                copied = next(r for r in text if r["run"] == 2)
            replies = [{"key": r["key"], "task_id": r["key"], "model": r["model"], "id": r["id"],
                        "completion": "x = 1" if r is copied else "y = 2",
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
    an.main(["contamination", "--models", "all", "--full", full, "--claude-full", claude_full,
             "--answers", str(answers), "--out", str(out)])
    rep = json.loads((out / "contamination.json").read_text())
    models = an.model_set(config.load(), "all")
    dv = rep["benchmarks"]["deveval"]
    assert dv["flagged"] == {an.name(m): int(m != copied["model"]) for m in models}
    assert (dv["copy_answers"], dv["copied_items"]) == (1, 1)
    assert rep["benchmarks"]["coderujb"]["copy_answers"] == 0
    flags = rel.read_csv(str(out / "contamination_flags.csv"), an.FLAG_FIELDS)
    assert [(r["item"], r["copied_by"], r["run"]) for r in flags] == [
        (copied["id"], copied["model"], "2")]
