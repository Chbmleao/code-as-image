import json
import os

import pytest
from conftest import ROOT

from codeimg import config
from codeimg.answers import answer_key
from codeimg.collect import collect

M = "org/m"
DSTUDY = os.path.join(ROOT, "results", "block1", "dstudy.json")
REQS = [{"id": "i", "condition": "text"}]


def gen(run, **kw):
    return {"model": M, "id": "i", "condition": "text", "run": run, "seed": run, "n_images": 0,
            "seconds": 1.0, "finish_reason": "stop", "prompt_tokens": 5, "output_tokens": 2, **kw}


def k(run):
    return answer_key(M, "i", "text", run)


def ujb_grade(run, stage, trigger, all_=False):
    return {"task_id": k(run), "stage": stage, "pass_trigger": trigger, "pass_all": all_, "seconds": 2}


def test_coderujb_passes_on_the_trigger_tests_not_the_suite():
    gens = [gen(0), gen(1), gen(2, finish_reason="length")]
    answers = [{"task_id": k(r), "defines_target": True} for r in (0, 1, 2)]
    grades = [ujb_grade(0, "pass", True, True), ujb_grade(1, "suite_fail", True),
              ujb_grade(2, "test_fail", False)]
    rows, problems = collect("coderujb", [M], REQS, 3, gens, answers, [], grades)
    assert problems == []
    got = {r["run"]: (r["passed"], r["reason"], r["suite"], r["truncated"]) for r in rows}
    assert got == {0: (True, "pass", "pass", False), 1: (True, "pass", "suite_fail", False),
                   2: (False, "test_fail", None, True)}


def test_deveval_reasons_and_skips():
    gens = [gen(0), gen(1), gen(2, reply=None, error="400 too long")]
    answers = [{"key": k(0), "defines_target": False}]
    skipped = [{"key": k(1), "stage": "no_body"}]
    grades = [{"key": k(0), "result": "TimeOut", "seconds": 180}]
    rows, problems = collect("deveval", [M], REQS, 3, gens, answers, skipped, grades)
    assert problems == []
    assert [(r["passed"], r["reason"]) for r in rows] == [
        (False, "timeout"), (False, "no_code"), (False, "request_error")]


def test_gaps_and_duplicates_are_problems():
    gens = [gen(0), gen(0)]
    _, problems = collect("deveval", [M], REQS, 2, gens, [{"key": k(0), "defines_target": True}],
                          [], [])
    assert any("duplicate generation" in p for p in problems)
    assert any(f"no generation row for {k(1)}" in p for p in problems)
    assert any("answer with no grade" in p for p in problems)


def test_runs_per_model():
    other = "org/other"
    gens = [gen(0), gen(1), {**gen(0), "model": other}]
    answers = [{"key": k(0), "defines_target": True}, {"key": k(1), "defines_target": True},
               {"key": answer_key(other, "i", "text", 0), "defines_target": True}]
    grades = [{"key": a["key"], "result": "Pass", "seconds": 1} for a in answers]
    rows, problems = collect("deveval", [M, other], REQS, {M: 2, other: 2}, gens, answers, [],
                             grades)
    assert len(rows) == 3
    assert problems == [f"no generation row for {answer_key(other, 'i', 'text', 1)}"]


def test_runs_from_reads_the_dstudy_rows(tmp_path):
    path = tmp_path / "dstudy.json"
    path.write_text(json.dumps({"rows": [
        {"benchmark": "deveval", "model": M, "runs": 2},
        {"benchmark": "coderujb", "model": M, "runs": 3}]}))
    assert config.runs_from(str(path), "deveval", [M]) == {M: 2}
    assert config.runs_from(str(path), "coderujb", [M]) == {M: 3}
    with pytest.raises(ValueError, match="no deveval row for org/other"):
        config.runs_from(str(path), "deveval", [M, "org/other"])


def test_committed_dstudy_covers_every_model():
    models = [m["repo"] for m in config.load()["models"].values()]
    for bench in ("coderujb", "deveval"):
        assert config.runs_from(DSTUDY, bench, models) == dict.fromkeys(models, 2)
