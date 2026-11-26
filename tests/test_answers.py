"""The answers stage must build exactly what benchmarks/*/make_answers.py built for calibration."""
import ast
import csv
import glob
import json
import os
import textwrap

import pytest
from conftest import ROOT, SCRATCH, need, read_jsonl

from codeimg.answers import answer_key, coderujb, deveval

CASES = {
    "coderujb": (coderujb, "coderujb/items.jsonl", "coderujb", "task_id", "source"),
    "deveval": (deveval, "deveval/data.jsonl", "deveval_calib", "key", "completion"),
}


@pytest.mark.parametrize("bench", sorted(CASES))
def test_calibration_answers_are_byte_identical(bench):
    mod, items_path, calib, key_field, field = CASES[bench]
    items = mod.load_items(need(os.path.join(SCRATCH, items_path)))
    old_dir = need(os.path.join(SCRATCH, calib))
    old = {r[key_field]: r for r in read_jsonl(os.path.join(old_dir, "answers.jsonl"))}
    old_skip_path = os.path.join(old_dir, "skipped.jsonl")
    old_skip = {r[key_field]: r["stage"] for r in read_jsonl(old_skip_path)} if os.path.exists(old_skip_path) else {}
    new, new_skip = {}, {}
    for path in sorted(glob.glob(os.path.join(old_dir, "gen", "gen_*.jsonl"))):
        for g in read_jsonl(path):
            g = {**g, "condition": "text", "run": 0}
            ans, skip = mod.answer(g, items[g["id"]], answer_key(g["model"], g["id"], "text", 0))
            old_key = g["model"].replace("/", "__") + "__" + g["id"]
            if ans:
                new[old_key] = ans[field]
            else:
                new_skip[old_key] = skip["stage"]
    assert new.keys() == old.keys()
    assert all(json.dumps(new[k]) == json.dumps(old[k][field]) for k in new)
    assert new_skip == old_skip


def test_key_is_unique_per_condition_and_run():
    keys = {answer_key("org/m", "x.y", c, r) for c in ("text", "image10") for r in range(3)}
    assert len(keys) == 6


def test_coderujb_reply_without_the_signature_is_skipped():
    it = {"function_signature": "public int f(int x)", "project": "Lang", "bug_id": 1,
          "source": "", "start": 0, "end": 0}
    g = {"model": "m", "id": "i", "condition": "text", "run": 0, "reply": "no code here"}
    ans, skip = coderujb.answer(g, it, "k")
    assert ans is None and skip["stage"] == "no_function"


def test_deveval_defines_target_is_recorded():
    it = {"indent": 4, "project_path": "p", "completion_path": "c", "body_position": [1, 2],
          "tests": []}
    g = {"model": "m", "id": "pkg.mod.f", "condition": "text", "run": 0,
         "reply": "```python\ndef f(x):\n    return x\n```"}
    ans, _ = deveval.answer(g, it, "k")
    assert ans["defines_target"] is True and ans["completion"] == "    return x\n"
    ans, _ = deveval.answer({**g, "reply": "```python\nreturn x\n```"}, it, "k")
    assert ans["defines_target"] is False


def test_coderujb_gold_answer_is_the_item():
    items = coderujb.load_items(need(os.path.join(SCRATCH, "coderujb/items.jsonl")))
    it = next(iter(items.values()))
    gold = coderujb.gold_answer(it)
    assert gold["source"] == it["source"] and gold["task_id"].startswith("gold__")


def test_benchmarks_dir_is_untouched():
    for b in ("coderujb", "deveval"):
        assert os.path.exists(os.path.join(ROOT, "benchmarks", b, "make_answers.py"))


# alembic/testing/env.py shape: a string whose lines sit at column 0 inside a body at 4
ALEMBIC_BODY = ('    txt = (\n        """\nfrom alembic import context\n\nconfig = context.config\n"""\n'
                '        + txt\n    )\n    return txt')


def test_adjust_indent_leaves_column_zero_string_lines_alone():
    assert deveval.adjust_indent(ALEMBIC_BODY, 4) == ALEMBIC_BODY
    assert deveval.adjust_indent(ALEMBIC_BODY, 8) == (
        '        txt = (\n            """\nfrom alembic import context\n\nconfig = context.config\n'
        '"""\n            + txt\n        )\n        return txt')


def test_adjust_indent_leaves_column_zero_fstring_lines_alone():
    body = '    write(\n        f"""# {a}\nrevision = \'{a}\'\n""",\n    )\n    return a'
    assert deveval.adjust_indent(body, 4) == body
    assert deveval.adjust_indent(body, 8) == (
        '        write(\n            f"""# {a}\nrevision = \'{a}\'\n""",\n        )\n        return a')


@pytest.mark.parametrize("body", [
    "x = 1\nif x:\n    return x",
    '    sql = """\n        select 1\n\n        from t\n    """\n    return sql',
    '    x = 1\n    s = """\nkey = 1\n',
    "        a = 1\n    b = 2\n  c = 3",
    "  \tx = 1\n\n  \ty = 2",
])
def test_adjust_indent_is_textwrap_everywhere_else(body):
    for n in (0, 4, 8):
        assert deveval.adjust_indent(body, n) == textwrap.indent(textwrap.dedent(body), " " * n)


def test_load_items_fixes_the_datasette_spans(tmp_path):
    rows = [{"namespace": "datasette.utils.asgi.Request.full_path", "body_position": [95, 96]},
            {"namespace": "pkg.mod.f", "body_position": [10, 12]}]
    path = tmp_path / "data.jsonl"
    path.write_text("".join(json.dumps(r) + "\n" for r in rows))
    items = deveval.load_items(str(path))
    assert items["datasette.utils.asgi.Request.full_path"]["body_position"] == [96, 97]
    assert items["pkg.mod.f"]["body_position"] == [10, 12]


def _function(path, qualname):
    """The ast node of Class.method or function `qualname` (dotted, relative to the module)."""
    with open(path) as f:
        nodes = ast.parse(f.read()).body
    *outer, name = qualname.split(".")
    for part in outer:
        nodes = next(n for n in nodes if isinstance(n, ast.ClassDef) and n.name == part).body
    return next(n for n in nodes if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                and n.name == name)


def _flagged():
    with open(os.path.join(ROOT, "results", "audit", "harness_suspects.csv")) as f:
        return [r["item"] for r in csv.DictReader(f)]


def _qualname(it):
    module = it["completion_path"].split("/", 2)[-1][:-len(".py")].replace("/", ".")
    return it["namespace"][len(module) + 1:]


def test_body_position_fix_matches_the_source():
    src = need(os.path.join(SCRATCH, "deveval", "Source_Code"))
    with open(need(os.path.join(SCRATCH, "deveval", "data.jsonl"))) as f:
        raw = {r["namespace"]: r for r in map(json.loads, f)}
    assert len(deveval.BODY_POSITION_FIX) == 9
    for ns, span in deveval.BODY_POSITION_FIX.items():
        it = raw[ns]
        node = _function(os.path.join(src, it["completion_path"]), _qualname(it))
        first = node.body[0]
        has_doc = isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant)
        start = first.end_lineno + 1 if has_doc else first.lineno
        assert span == [start, node.end_lineno], ns
        shift = 1 if it["body_position"][0] < 110 else 2
        assert span == [p + shift for p in it["body_position"]], ns


@pytest.mark.parametrize("ns", _flagged())
def test_a_perfect_reply_splices_back_to_the_same_file(ns):
    src = need(os.path.join(SCRATCH, "deveval", "Source_Code"))
    it = deveval.load_items(need(os.path.join(SCRATCH, "deveval", "data.jsonl")))[ns]
    path = os.path.join(src, it["completion_path"])
    with open(path) as f:
        text = f.read()
    lines = text.splitlines(keepends=True)
    node = _function(path, _qualname(it))
    start = min([node.lineno] + [d.lineno for d in node.decorator_list])
    reply = "```python\n" + "".join(lines[start - 1:node.end_lineno]) + "```"
    g = {"model": "gold", "id": ns, "condition": "text", "run": 0, "reply": reply}
    ans, _ = deveval.answer(g, it, "k")
    s, e = ans["body_position"][0] - 1, ans["body_position"][1]
    spliced = "".join(lines[:s] + ["\n", ans["completion"], "\n"] + lines[e:])
    assert ast.dump(ast.parse(spliced)) == ast.dump(ast.parse(text))
