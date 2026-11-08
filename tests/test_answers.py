"""The answers stage must build exactly what benchmarks/*/make_answers.py built for calibration."""
import glob
import json
import os

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
