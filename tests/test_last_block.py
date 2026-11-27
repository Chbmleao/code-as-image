import importlib.util
import json
import os

import pytest
from conftest import ROOT

from codeimg.analysis import inputs as inp
from codeimg.answers import answer_key
from codeimg.answers import deveval as dv

_spec = importlib.util.spec_from_file_location("last_block",
                                               os.path.join(ROOT, "scripts", "last_block.py"))
lb = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(lb)
an = lb.an

M = "toy/Model"
ITEM = {"project_path": "p", "completion_path": "p/m.py", "body_position": [3, 4], "tests": [],
        "indent": 4}
CONDS = ["text", "image10", "image12", "image14"]


def fence(code):
    return f"```python\n{code}\n```\n"


def gen(reply, item_id="pkg.mod.f"):
    return {"model": M, "id": item_id, "condition": "image10", "run": 0, "reply": reply}


def classify(reply):
    g = gen(reply)
    return lb.last_block(g, ITEM, answer_key(M, g["id"], g["condition"], g["run"]))


DRAFT = "def f(x):\n    return x + 1"
FIX = "def f(x):\n    y = x * 2\n    return y"


def test_a_revised_reply_is_graded_on_its_last_block():
    role, first, last = classify("Draft:\n" + fence(DRAFT) + "Wait, I need to reconsider.\n"
                                 + fence(FIX))
    assert role == "graded"
    assert first["completion"] == "    return x + 1\n"
    assert last["completion"] == "    y = x * 2\n    return y\n"
    # the same fields and re-indent as deveval.answer on a reply holding only that block
    alone, _ = dv.answer(gen(fence(FIX)), ITEM, first["key"])
    assert last == alone


def test_blocks_that_do_not_define_the_target_are_skipped():
    other = "def g():\n    return 0"
    broken = "def f(x:\n    return"
    assert classify(fence(DRAFT) + fence(other) + fence(broken)) is None
    role, _, last = classify(fence(DRAFT) + fence(FIX) + fence(other) + fence(broken))
    assert role == "graded" and "x * 2" in last["completion"]


def test_equal_blocks_are_same_and_an_empty_last_body_is_no_code():
    role, first, last = classify(fence(DRAFT) + "Same again:\n" + fence(DRAFT))
    assert role == "same" and first["completion"] == last["completion"]
    role, _, last = classify(fence(DRAFT) + fence('def f(x):\n    """Docstring only."""'))
    assert role == "no_code" and last is None


PICKED = [{"key": "a", "role": "graded"}, {"key": "b", "role": "graded"},
          {"key": "c", "role": "same"}, {"key": "d", "role": "no_code"}]


def grade(key, result):
    return {"key": key, "result": result, "seconds": "1.0"}


GRADES = [grade("first__a", "Error"), grade("last__a", "Pass"),
          grade("first__b", "Pass"), grade("last__b", "TimeOut")]


def test_verdicts_take_both_grades_of_each_graded_reply():
    assert lb.verdicts(PICKED, GRADES) == {"a": {"first": False, "last": True},
                                           "b": {"first": True, "last": False}}


@pytest.mark.parametrize("grades, message", [
    (GRADES[:-1], "1 of 4 grade"),
    (GRADES + [grade("last__b", "Pass")], "graded twice"),
    (GRADES + [grade("last__c", "Pass")], "not in answers.csv"),
    ([*GRADES[:-1], grade("last__b", "Fail")], "unknown grade result"),
])
def test_verdicts_stop_on_bad_grades(grades, message):
    with pytest.raises(ValueError, match=message):
        lb.verdicts(PICKED, grades)


def test_only_graded_and_no_code_rows_change():
    rows = [{"key": k, "passed": p} for k, p in (("a", False), ("b", True), ("c", True),
                                                 ("d", True), ("e", False))]
    got = lb.with_last(rows, PICKED, lb.verdicts(PICKED, GRADES))
    assert [r["passed"] for r in got] == [True, False, True, False, False]
    assert [r["passed"] for r in rows] == [False, True, True, True, False]


def toy_rows(models, passes):
    """passes[item][condition]: the runs of every model."""
    return [{"key": answer_key(m, i, c, r), "model": m, "id": i, "condition": c, "run": r,
             "seed": r, "passed": bool(y), "reason": "pass" if y else "error",
             "truncated": False, "prompt_tokens": 100, "output_tokens": 10,
             "defines_target": True}
            for m in models for i in passes for c in CONDS for r, y in enumerate(passes[i][c])]


def toy_lines(rows, models, items):
    parts = [([i for i, _, _ in items], dict.fromkeys(models, 2))]
    return lb.gap_lines([inp.load_benchmark("deveval", rows, items, models, CONDS, parts)])


def test_one_flip_moves_one_model_by_one_answer():
    models = list(an.ds.NAMES)[:2]
    passes = {"A": {"text": [1, 1], **{c: [0, 1] for c in CONDS[1:]}},
              "B": {"text": [1, 0], **{c: [0, 0] for c in CONDS[1:]}},
              "C": {"text": [0, 1], **{c: [1, 0] for c in CONDS[1:]}}}
    items = [("A", "p", 2), ("B", "q", 2), ("C", "q", 2)]
    rows = toy_rows(models, passes)
    first = toy_lines(rows, models, items)
    flip = answer_key(models[0], "B", "image12", 1)
    picked = [{"key": flip, "role": "graded"}]
    for result, step in (("Pass", 1), ("Error", 0)):
        grades = [grade(f"first__{flip}", "Error"), grade(f"last__{flip}", result)]
        last = toy_lines(lb.with_last(rows, picked, lb.verdicts(picked, grades)), models, items)
        # 1 / (2 runs x 3 sizes x 3 items)
        assert last[inp.name(models[0])]["est"] == pytest.approx(
            first[inp.name(models[0])]["est"] + step / 18, abs=1e-12)
        assert last[inp.name(models[1])] == first[inp.name(models[1])]
    # a pass that turns into a fail lowers the gap by the same step
    flip = answer_key(models[0], "A", "image10", 1)
    picked = [{"key": flip, "role": "graded"}]
    grades = [grade(f"first__{flip}", "Pass"), grade(f"last__{flip}", "Error")]
    last = toy_lines(lb.with_last(rows, picked, lb.verdicts(picked, grades)), models, items)
    assert last[inp.name(models[0])]["est"] == pytest.approx(
        first[inp.name(models[0])]["est"] - 1 / 18, abs=1e-12)


def test_the_first_block_line_must_be_the_committed_gap(tmp_path):
    lines = {"M": {"est": -0.1234567}}
    path = tmp_path / "gaps.json"
    path.write_text(json.dumps({"benchmarks": {"deveval": {"main": [{"model": "M",
                                                                      "est": -0.123457}]}}}))
    lb.check_committed(lines, [str(path)])
    path.write_text(json.dumps({"benchmarks": {"deveval": {"main": [{"model": "M",
                                                                      "est": -0.123456}]}}}))
    with pytest.raises(ValueError, match="is not the first-block est"):
        lb.check_committed(lines, [str(path)])
