"""The graders moved into the package unchanged; these tests hold them to the calibration code.

Run under Python 3.9 too (the DevEval venv): uv run --python 3.9 pytest tests/test_grade.py
"""
import ast
import os

import pytest
from conftest import ROOT

PAIRS = [
    ("src/codeimg/grade/coderujb.py", "benchmarks/coderujb/gold_check.py", None),
    ("src/codeimg/grade/deveval.py", "benchmarks/deveval/gold_check.py", {"run_item", "ITEM_BUDGET"}),
    ("src/codeimg/grade/deveval.py", "benchmarks/deveval/grade_answers.py", {"grade_repo", "main"}),
    ("src/codeimg/answers/coderujb.py", "benchmarks/coderujb/make_answers.py",
     {"remove_line_comment", "clean_signature", "stop_at_function", "extract"}),
    ("src/codeimg/answers/deveval.py", "benchmarks/deveval/make_answers.py",
     {"FENCE", "adjust_indent", "body_via_ast", "body_after_def", "extract"}),
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
