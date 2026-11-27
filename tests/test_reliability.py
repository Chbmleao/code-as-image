import csv
import json
import os
from collections import defaultdict

import pytest
from conftest import ROOT

from codeimg.analysis import reliability as rel

ds = rel.ds

M0, M1 = list(ds.NAMES)[:2]
COMP = {"s2_model": 0.035, "s2_project": 0.01, "s2_item": 0.05, "s2_model_project": 0.02,
        "s2_model_item": 0.03, "s2_run": 0.11}


def test_quantile_and_summary_are_type_1():
    v = list(range(1, 41))
    assert rel.summarize(reversed(v)) == {"median": 20, "lo": 1, "hi": 39}
    assert rel.quantile(list(range(2000)), 0.975) == 1949


def test_spearman_brown():
    # T = 0.01 + 0.05 + 0.02 + 0.03 = 0.11 = s2_run, so rho_1 = 1/2, rho_2 = 2/3, rho_3 = 3/4
    for n, want in ((1, 1 / 2), (2, 2 / 3), (3, 3 / 4)):
        assert rel.reliability(COMP, n) == pytest.approx(want, abs=1e-12)


def test_g_with_clusters_and_mixed_runs():
    d = rel.design_terms(["A", "A", "A", "B"], [3, 2, 2, 3])
    assert d["cluster_weight"] == pytest.approx(10 / 16)
    assert d["h"] == pytest.approx(5 / 12)
    # E = s2_model_project * 10/16 + (s2_model_item + s2_run * 5/12) / 4
    e = 0.02 * 10 / 16 + (0.03 + 0.11 * 5 / 12) / 4
    assert rel.error_variance(COMP, d) == pytest.approx(e, abs=1e-12)
    assert rel.g_random(COMP, d) == pytest.approx(0.035 / (0.035 + e), abs=1e-12)
    # five effects with mean 0 and sum of squares 0.1: v = 0.1 / 4
    assert rel.g_finite(COMP, [0.1, -0.1, 0.2, -0.2, 0.0], d) == pytest.approx(
        0.025 / (0.025 + e), abs=1e-12)


def test_within_cell_variance():
    assert rel.within_cell([[1, 0], [1, 1, 0], [0, 0]]) == pytest.approx(5 / 18, abs=1e-12)


def test_run_correlation():
    cells = {M0: [[1, 1], [0, 0], [1, 0], [0, 1]], M1: [[1, 1], [0, 0], [1, 1], [0, 0]]}
    per, pooled = rel.run_correlation(cells)
    assert per[M0] == pytest.approx(0.0, abs=1e-12)
    assert per[M1] == pytest.approx(1.0)
    assert pooled == pytest.approx(0.5)
    per, pooled = rel.run_correlation({M0: [[1, 0], [1, 1]]})
    assert per[M0] is None and pooled is None


def test_all_none_shares():
    cells = {M0: [[1, 1, 1], [0, 0], [1, 0]], M1: [[1, 1, 1], [0, 0], [0, 0]]}
    assert rel.all_none_shares(cells) == (1 / 3, 1 / 3)


def test_ranks_and_swap():
    assert rel.average_ranks([0.5, 0.7, 0.5, 0.1]) == [2.5, 1.0, 2.5, 4.0]
    assert rel.swap_probability([1, 2], [-1, -3]) == 1
    assert rel.swap_probability([1, 2], [2, 3]) == 0
    assert rel.swap_probability([0, 0], [1, -1]) == 0.5
    assert [rel.sixths(r) for r in ([1, 0], [1, 1, 0], [1, 1, 1], [0, 0])] == [3, 4, 6, 0]


def test_sensitivity_rule():
    assert rel.sensitivity({"median": 0.1}, {"median": 0.104})["moved"] is False
    assert rel.sensitivity({"median": 0.1}, {"median": 0.106})["moved"] is True
    assert rel.sensitivity({"median": 0.005}, {"median": 0.0065})["moved"] is False
    assert rel.sensitivity({"median": 0.005}, {"median": 0.0075})["moved"] is True


# two models, items i0 (project A, 3 runs), i1 (A, 2 runs), i2 (B, 2 runs); text puts M0 ahead,
# every image size puts M1 ahead
TOY = {M0: {"text": [[1, 1, 1], [1, 0], [0, 0]], "image": [[0, 0, 0], [0, 0], [0, 0]]},
       M1: {"text": [[1, 0, 0], [0, 0], [1, 1]], "image": [[1, 1, 1], [1, 1], [0, 0]]}}
ITEMS = [("i0", "A"), ("i1", "A"), ("i2", "B")]


def write_toy(tmp_path, draws_fields=rel.DRAW_FIELDS):
    scratch, out = tmp_path / "scratch", tmp_path / "out"
    scratch.mkdir()
    out.mkdir()
    for b in ds.BENCHES:
        with open(scratch / f"{b}_answers.csv", "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(rel.ANSWER_FIELDS)
            for m, by in TOY.items():
                for c in ds.CONDITIONS:
                    for (i, p), runs in zip(ITEMS, by["text" if c == "text" else "image"]):
                        for r, y in enumerate(runs):
                            w.writerow([m, i, p, c, r, y])
        with open(out / f"draws_{b}.csv", "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(list(draws_fields) + ["a1", "a2"])
            for c in ds.CONDITIONS:
                for prior in rel.PRIORS:
                    for chain in (1, 2):
                        for k in (1, 2):
                            row = {**COMP, "benchmark": b, "condition": c, "prior": prior,
                                   "chain": chain, "draw": k}
                            w.writerow([row[x] for x in draws_fields] + [0.1, -0.1])
    with open(out / "mcmc_diagnostics.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(rel.DIAG_FIELDS)
        for b in ds.BENCHES:
            for c in ds.CONDITIONS:
                for prior in rel.PRIORS:
                    for comp in rel.COMPONENTS:
                        w.writerow([b, c, prior, comp, 1.0, 1000, 60000, 1.0, "pass"])
    return ["--scratch", str(scratch), "--out", str(out)], out


def test_report_end_to_end(tmp_path):
    args, out = write_toy(tmp_path)
    rel.main(["report"] + args)
    first = (out / "reliability.json").read_bytes()
    rel.main(["report"] + args)
    assert (out / "reliability.json").read_bytes() == first
    rep = json.loads(first)
    b = rep["benchmarks"]["coderujb"]
    assert b["design"] == {"n_items": 3, "n_clusters": 2, "cluster_weight": round(5 / 9, 6),
                           "h": round((1 / 3 + 1 / 2 + 1 / 2) / 3, 6)}
    text = b["conditions"]["text"]
    assert text["reliability"]["2"]["median"] == round(2 / 3, 6)
    assert text["components"]["ig"]["s2_run"] == {"median": 0.11, "lo": 0.11, "hi": 0.11}
    assert text["sensitivity"]["s2_model"]["moved"] is False
    n0, n1 = ds.NAMES[M0], ds.NAMES[M1]
    assert text["empirical"]["within_cell"]["by_model"][n0] == round((0 + 0.5 + 0) / 3, 6)
    assert text["all_pass_share"] == 0 and text["none_pass_share"] == 0
    # text: M0 (1 + 1/2 + 0) / 3, M1 (1/3 + 0 + 1) / 3; image is the mean of three equal sizes
    assert b["rates"]["text"] == {n0: 0.5, n1: round(4 / 9, 6)}
    assert b["rates"]["image"] == {n0: 0.0, n1: round(2 / 3, 6)}
    assert b["ranks"]["text"][n0]["rank"] == 1 and b["ranks"]["image"][n0]["rank"] == 2
    # every draw reverses the pair except a draw of project B twice, where image ties (0.5)
    draws = rel.rs.cluster_draws([[0, 1], [2]], rel.rs.N_BOOT, f"{rel.rs.SEED}-coderujb")
    bb = sum(d == [2, 2] for d in draws) / len(draws)
    assert b["swap"] == [{"pair": [n0, n1], "p": round(1 - bb / 2, 6)}]
    assert rep["gate"]["passed"] == rep["gate"]["fits"] == 16
    assert "## Rank stability" in (out / "findings.md").read_text()


def test_report_missing_column_exits_1(tmp_path, capsys):
    args, _ = write_toy(tmp_path, [f for f in rel.DRAW_FIELDS if f != "s2_run"])
    with pytest.raises(SystemExit) as e:
        rel.main(["report"] + args)
    assert e.value.code == 1
    assert "missing column(s) ['s2_run']" in capsys.readouterr().err


FULL = os.path.join(ROOT, "results", "full")
needs_full = pytest.mark.skipif(not os.path.exists(os.path.join(FULL, "checks.json")),
                                reason="full answer table not present")


@needs_full
def test_prep_rejects_a_missing_row(tmp_path, capsys):
    with open(os.path.join(FULL, "coderujb.collected.jsonl")) as f:
        rows = f.read().splitlines(keepends=True)
    (tmp_path / "coderujb.collected.jsonl").write_text("".join(rows[1:]))
    with pytest.raises(SystemExit) as e:
        rel.main(["prep", "--full", str(tmp_path), "--scratch", str(tmp_path / "s"),
                  "--bench", "coderujb"])
    assert e.value.code == 1
    assert "rows do not match the expected grid" in capsys.readouterr().err


@needs_full
@pytest.mark.parametrize("b", ds.BENCHES)
def test_pooled_rates_of_the_answers_match_checks(b):
    # checks.json pools the whole graded table, the excluded items included
    rows = ds.read_jsonl(os.path.join(FULL, f"{b}.collected.jsonl"))
    tally = defaultdict(lambda: [0, 0])
    for r in rows:
        tally[(r["model"], r["condition"])][0] += int(r["passed"])
        tally[(r["model"], r["condition"])][1] += 1
    with open(os.path.join(FULL, "checks.json")) as f:
        cells = json.load(f)[b]["cells"]
    for (m, c), (k, n) in tally.items():
        assert round(k / n, 4) == cells[m][c]["pass_rate"]


def test_the_excluded_items_are_the_harness_suspects():
    with open(os.path.join(ROOT, "results", "audit", "harness_suspects.csv")) as f:
        suspects = [r["item"] for r in csv.DictReader(f)]
    assert rel.excluded("deveval") == suspects
    assert len(suspects) == 13


JSOUP_93 = "979ad380fd344088d8ad0f815606df2034679d982d7ec44d391b8e74812ef9b7"


def test_the_coderujb_exclusion_is_jsoup_93_alone_in_its_cluster():
    assert rel.excluded("coderujb") == [JSOUP_93]
    projects = {i: p for i, p, _ in rel.design("coderujb")}
    assert projects[JSOUP_93] == "Jsoup"
    assert [i for i, p in projects.items() if p == "Jsoup"] == [JSOUP_93]


def test_every_exclusion_has_its_decision_date():
    assert {b for b in ds.BENCHES if rel.excluded(b)} == set(rel.EXCLUDED_ON)


@needs_full
def test_no_answer_passes_jsoup_93():
    rows = [r for r in ds.read_jsonl(os.path.join(FULL, "coderujb.collected.jsonl"))
            if r["id"] == JSOUP_93]
    assert len(rows) == 40
    assert not any(r["passed"] for r in rows)


def test_the_excluded_note_names_each_decision():
    rep = {"benchmarks": {"coderujb": {"excluded": {"count": 1}},
                          "deveval": {"excluded": {"count": 13}}}}
    assert rel.excluded_note(rep) == (", minus the 1 CoderUJB (2026-11-26) and 13 DevEval "
                                      "(2026-11-25) items excluded in docs/decisions.md")
    rep["benchmarks"]["coderujb"]["excluded"]["count"] = 0
    assert rel.excluded_note(rep) == (", minus the 13 DevEval (2026-11-25) items excluded in "
                                      "docs/decisions.md")


def test_an_unknown_excluded_id_stops(tmp_path):
    (tmp_path / "excluded").mkdir()
    (tmp_path / "excluded" / "deveval.txt").write_text("datasette.utils.asgi.Request.fake\nnope\n")
    with pytest.raises(ValueError, match=r"not in the deveval item list: \['nope'\]"):
        rel.excluded("deveval", manifests=str(tmp_path))
    assert rel.excluded("coderujb", manifests=str(tmp_path)) == []


def test_drop_excluded_ignores_ids_it_does_not_hold():
    items = [("A", "p", 2), ("B", "p", 2)]
    rows = [{"id": "A"}, {"id": "B"}, {"id": "B"}]
    assert rel.drop_excluded(items, rows, ["B", "Z"]) == ([("A", "p", 2)], [{"id": "A"}], ["B"])


@needs_full
@pytest.mark.parametrize("b", ds.BENCHES)
def test_the_answers_csv_leaves_the_excluded_items_out(b):
    rows = ds.read_jsonl(os.path.join(FULL, f"{b}.collected.jsonl"))
    gone = set(rel.excluded(b))
    out = rel.answers(b, rows, rel.design(b))
    assert not gone & {i for _, i, _, _, _, _ in out}
    assert len(out) == sum(r["id"] not in gone for r in rows)
