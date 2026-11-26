"""The graders moved into the package from the calibration code, and these tests hold them to it.
The DevEval grader's loop and output writing are ours (rows written per answer); its run_item and
its splice are still the calibration's.

Run under Python 3.9 too (the DevEval venv): uv run --python 3.9 pytest tests/test_grade.py
"""
import ast
import importlib.util
import json
import os
import sys
import threading
import time

import pytest
from conftest import ROOT

from codeimg.grade import deveval

PAIRS = [
    ("src/codeimg/grade/coderujb.py", "benchmarks/coderujb/gold_check.py", None),
    ("src/codeimg/grade/deveval.py", "benchmarks/deveval/gold_check.py", {"run_item", "ITEM_BUDGET"}),
    ("src/codeimg/answers/coderujb.py", "benchmarks/coderujb/make_answers.py",
     {"remove_line_comment", "clean_signature", "stop_at_function", "extract"}),
    ("src/codeimg/answers/deveval.py", "benchmarks/deveval/make_answers.py",
     {"FENCE", "body_via_ast", "body_after_def", "extract"}),
]


def top_level(path):
    with open(os.path.join(ROOT, path)) as f:
        tree = ast.parse(f.read())
    out = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            out[node.name] = ast.dump(node)
        elif isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
            out[node.targets[0].id] = ast.dump(node)
    return out


@pytest.mark.parametrize("new,old,names", PAIRS)
def test_moved_code_is_unchanged(new, old, names):
    n, o = top_level(new), top_level(old)
    names = names or set(o)
    assert names <= set(o)
    for name in sorted(names):
        assert n.get(name) == o[name], name


@pytest.mark.parametrize("module", ["codeimg.grade.coderujb", "codeimg.grade.deveval"])
def test_graders_import_without_3_11(module):
    import importlib
    importlib.import_module(module)


PASS = {"result": "Pass", "seconds": 0.0, "tail": ""}


def make_tree(tmp_path, sizes):
    """Pristine and work trees with one source file per repo, and answers.jsonl with
    sizes[repo] answers for it. Returns (paths, answers)."""
    answers = []
    for repo, n in sizes.items():
        for root in ("pristine", "work"):
            os.makedirs(tmp_path / root / repo, exist_ok=True)
            (tmp_path / root / repo / "mod.py").write_text(
                "def f():\n    '''doc'''\n    return 0\n\nX = 1\n")
        for i in range(n):
            answers.append({"key": f"{repo}__a{i}", "model": "m", "id": f"{repo}.f",
                            "project_path": repo, "completion_path": f"{repo}/mod.py",
                            "body_position": [3, 3], "completion": f"    return {i}",
                            "tests": ["t"]})
    ans = tmp_path / "answers.jsonl"
    ans.write_text("".join(json.dumps(a) + "\n" for a in answers))
    paths = (str(ans), str(tmp_path / "pristine"), str(tmp_path / "work"),
             str(tmp_path / "out.jsonl"))
    return paths, answers


def out_keys(path):
    with open(path) as f:
        return [json.loads(line)["key"] for line in f]


def test_rows_written_per_answer_and_resumed(tmp_path, monkeypatch):
    paths, answers = make_tree(tmp_path, {"r": 5})
    calls = []

    def dies_on_fourth(work, item):
        calls.append(item["namespace"])
        if len(calls) == 4:
            raise RuntimeError("killed")
        return PASS

    monkeypatch.setattr(deveval, "run_item", dies_on_fourth)
    with pytest.raises(RuntimeError):
        deveval.grade(*paths, 1)
    assert out_keys(paths[3]) == [a["key"] for a in answers[:3]]

    monkeypatch.setattr(deveval, "run_item", lambda work, item: PASS)
    deveval.grade(*paths, 1)
    assert sorted(out_keys(paths[3])) == sorted(a["key"] for a in answers)


def test_many_repos_every_key_once(tmp_path, monkeypatch):
    paths, answers = make_tree(tmp_path, {"a": 7, "b": 4, "c": 9, "d": 1})
    monkeypatch.setattr(deveval, "run_item", lambda work, item: PASS)
    deveval.grade(*paths, 3)
    assert sorted(out_keys(paths[3])) == sorted(a["key"] for a in answers)


def test_largest_repo_starts_first(tmp_path, monkeypatch):
    paths, _ = make_tree(tmp_path, {"small": 1, "big": 3, "mid": 2})
    order = []
    monkeypatch.setattr(deveval, "run_item",
                        lambda work, item: order.append(item["project_path"]) or PASS)
    deveval.grade(*paths, 1)
    assert order == ["big"] * 3 + ["mid"] * 2 + ["small"]


def test_error_stops_other_repos_after_their_current_answer(tmp_path, monkeypatch):
    # workers=2: "a" raises on its first answer while "b" is grading its first; "c" is queued
    paths, _ = make_tree(tmp_path, {"a": 3, "b": 2, "c": 1})
    b_started, raised = threading.Event(), threading.Event()

    def fake(work, item):
        if item["project_path"] == "a":
            assert b_started.wait(5)
            raised.set()
            raise RuntimeError("missing file")
        b_started.set()
        assert raised.wait(5)
        time.sleep(0.2)  # let the failing thread set the stop flag
        return PASS

    monkeypatch.setattr(deveval, "run_item", fake)
    with pytest.raises(RuntimeError, match="missing file"):
        deveval.grade(*paths, 2)
    assert out_keys(paths[3]) == ["b__a0"]


def test_torn_last_line_is_cut_and_regraded(tmp_path, monkeypatch):
    paths, _ = make_tree(tmp_path, {"r": 2})
    with open(paths[3], "w") as f:
        f.write(json.dumps({"key": "r__a0", "model": "m", "id": "r.f", "result": "Pass",
                            "seconds": 0.0, "tail": ""}) + "\n" + '{"key": "r__a1", "mo')
    graded = []
    monkeypatch.setattr(deveval, "run_item",
                        lambda work, item: graded.append(item["namespace"]) or PASS)
    deveval.grade(*paths, 1)
    assert graded == ["r__a1"]
    assert out_keys(paths[3]) == ["r__a0", "r__a1"]


def calibration_grader():
    here = os.path.join(ROOT, "benchmarks", "deveval")
    sys.path.insert(0, here)
    try:
        spec = importlib.util.spec_from_file_location(
            "grade_answers", os.path.join(here, "grade_answers.py"))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
    finally:
        sys.path.remove(here)
    return mod


def test_splice_and_restore_match_calibration(tmp_path, monkeypatch):
    paths, answers = make_tree(tmp_path, {"r": 3})
    ans, pristine, work, out = paths
    seen = {"ours": [], "calibration": []}

    def recorder(name):
        def fake(work_root, item):
            with open(os.path.join(work_root, item["completion_path"])) as f:
                seen[name].append(f.read())
            return PASS
        return fake

    monkeypatch.setattr(deveval, "run_item", recorder("ours"))
    deveval.grade(ans, pristine, work, out, 1)
    calib = calibration_grader()
    monkeypatch.setattr(calib, "run_item", recorder("calibration"))
    calib.grade_repo((pristine, work, answers))
    assert seen["ours"] == seen["calibration"]
    assert len(set(seen["ours"])) == 3
    with open(os.path.join(pristine, "r", "mod.py"), "rb") as p, \
            open(os.path.join(work, "r", "mod.py"), "rb") as w:
        assert p.read() == w.read()
