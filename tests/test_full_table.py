import importlib.util
import os

import pytest
from conftest import ROOT

from codeimg.answers import answer_key

_spec = importlib.util.spec_from_file_location(
    "full_table", os.path.join(ROOT, "scripts", "full_table.py"))
ft = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ft)

M = "org/m"


def row(item, run, **kw):
    return {"key": answer_key(M, item, "text", run), "model": M, "id": item,
            "condition": "text", "run": run, "seed": run, "passed": True, "reason": "pass",
            "truncated": False, **kw}


def grid():
    # block item "b" at 3 runs, rest item "r" at 2
    return ft.expected_keys([M], ["text"], [(["b"], {M: 3}), (["r"], {M: 2})])


def clean():
    return [row("b", 0), row("b", 1), row("b", 2), row("r", 0), row("r", 1)]


def test_clean_table_passes():
    c = ft.check(clean(), grid())
    assert c["ok"] and c["rows"] == c["expected"] == 5
    assert c["cells"][M]["text"]["pass_rate"] == 1.0


@pytest.mark.parametrize("change,field", [
    (lambda rows: rows + [rows[0]], "duplicates"),
    (lambda rows: [{**rows[0], "passed": None}] + rows[1:], "null_passed"),
    (lambda rows: rows[:-1], "missing"),
    (lambda rows: rows + [row("r", 2)], "extra"),
    (lambda rows: [{**rows[0], "seed": 7}] + rows[1:], "seed_not_run"),
])
def test_each_defect_fails_and_is_named(change, field):
    c = ft.check(change(clean()), grid())
    assert not c["ok"]
    assert c[field]


def test_sample_skips_answers_that_were_not_graded():
    rows = {"deveval": clean() + [row("x", 0, reason="request_error", passed=False)],
            "coderujb": [row("y", 0), row("z", 0, reason="no_code", passed=False)]}
    keys = ft.sample(rows, {"deveval": 5, "coderujb": 1}, 1)
    assert keys["coderujb"] == [answer_key(M, "y", "text", 0)]
    assert answer_key(M, "x", "text", 0) not in keys["deveval"]


def test_rescore_lists_a_verdict_mismatch():
    rows = {"deveval": clean(), "coderujb": []}
    k0, k1 = rows["deveval"][0]["key"], rows["deveval"][1]["key"]
    grades = [{"key": k0, "result": "Pass", "seconds": 1},
              {"key": k1, "result": "Error", "seconds": 1}]
    out = ft.rescore(rows, {"deveval": [k0, k1], "coderujb": []}, grades, [k1])
    assert out["deveval"]["verdict_mismatches"] == [
        {"key": k1, "table": "pass", "regraded": "error"}]
    assert out["deveval"]["extraction_differs"] == [k1]
    assert out["deveval"]["missing"] == []
