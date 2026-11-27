import hashlib
import importlib.util
import json
import os

from conftest import ROOT

_spec = importlib.util.spec_from_file_location(
    "contamination_inputs", os.path.join(ROOT, "scripts", "contamination_inputs.py"))
ci = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ci)


def test_text_lines_keeps_the_text_rows_byte_for_byte(tmp_path):
    rows = ['{"condition": "text", "id": "a"}\n', '{"condition": "image10", "id": "a"}\n',
            '{"id":"b","condition":"text"}\n']
    path = tmp_path / "answers.jsonl"
    path.write_text("".join(rows))
    assert ci.text_lines(path) == [rows[0], rows[2]]


def test_gold_lines_keep_only_id_and_completion_in_id_order():
    class Dev:
        @staticmethod
        def gold_answer(it, source_root):
            return {"key": "gold__x", "id": it["namespace"], "completion": it["body"]}
    items = {"p.f": {"namespace": "p.f", "body": "    return 1\n"},
             "p.g": {"namespace": "p.g", "body": "    return 2\n"}}
    lines = ci.gold_lines(Dev, items, ["p.g", "p.f"], "unused")
    assert [json.loads(line) for line in lines] == [
        {"id": "p.g", "completion": "    return 2\n"}, {"id": "p.f", "completion": "    return 1\n"}]


def test_check_flags_a_changed_file_and_a_missing_one(tmp_path):
    (tmp_path / "a.jsonl").write_text("one\n")
    (tmp_path / "b.jsonl").write_text("two\n")
    expected = {n: hashlib.sha256(t.encode()).hexdigest()
                for n, t in (("a.jsonl", "one\n"), ("b.jsonl", "two\n"), ("c.jsonl", "three\n"))}
    assert ci.check(tmp_path, expected) == ["c.jsonl"]
    (tmp_path / "a.jsonl").write_text("one, edited\n")
    assert ci.check(tmp_path, expected) == ["a.jsonl", "c.jsonl"]


def test_the_main_run_deveval_has_no_span_fix():
    dev = ci.main_run_deveval()
    assert not hasattr(dev, "BODY_POSITION_FIX")
    assert callable(dev.answer) and callable(dev.gold_answer)
