import importlib.util
import json
import os
import random

import pytest
from conftest import FIXTURES, ROOT, read_jsonl
from PIL import Image

from codeimg import config, transcribe
from codeimg.prompts import item_requests, load_prompts

CFG = config.load()["transcription"]
INSTR, SEP = CFG["instruction"], CFG["separator"]
TWO_BLOCKS = "ydata_profiling.profile_report.ProfileReport.typeset"
NO_BELOW = "mingus.core.value.determine"

_spec = importlib.util.spec_from_file_location(
    "transcription_check_ids", os.path.join(ROOT, "scripts", "transcription_check_ids.py"))
check_ids = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(check_ids)


def source(tmp_path, bench, fixture, ids=None, sizes=(12,)):
    """A main-run requests.jsonl with its pages rendered under tmp_path/bench."""
    out = tmp_path / bench
    for px in sizes:
        (out / "img" / str(px)).mkdir(parents=True)
    items = load_prompts(bench, os.path.join(FIXTURES, fixture))
    with open(out / "requests.jsonl", "w", encoding="utf-8") as f:
        for item_id in ids or items:
            rows = item_requests(bench, items[item_id], list(sizes), "SENTENCE ⏎", str(out))
            f.writelines(json.dumps(r) + "\n" for r in rows)
    return str(out / "requests.jsonl")


def texts(row):
    return [p["text"] for p in row["parts"] if p["type"] == "text"]


def test_deveval_pages_keep_their_order_with_the_separator_between_blocks(tmp_path):
    src = source(tmp_path, "deveval", "deveval_prompts.jsonl", [TWO_BLOCKS])
    main_row = next(r for r in read_jsonl(src) if r["condition"] == "image12")
    (row,) = transcribe.transcription_rows([src], INSTR, SEP)
    assert {k: row[k] for k in ("benchmark", "id", "condition")} == {
        "benchmark": "deveval", "id": TWO_BLOCKS, "condition": "image12"}
    assert texts(row) == [INSTR, SEP]
    assert row["parts"][0]["type"] == "text" and row["parts"][-1]["type"] == "image"
    images = [p for p in row["parts"] if p["type"] == "image"]
    main_images = [p for p in main_row["parts"] if p["type"] == "image"]
    assert row["n_images"] == len(images) == main_row["n_images"]
    assert [p["path"] for p in images] == [
        os.path.join(str(tmp_path / "deveval"), p["path"]) for p in main_images]
    assert all(os.path.isabs(p["path"]) for p in images)
    sep_at = row["parts"].index({"type": "text", "text": SEP})
    main_kinds = [p["type"] for p in main_row["parts"]]
    assert sep_at == main_kinds.index("text", 1)


def test_task_text_is_dropped_and_no_separator_without_a_second_block(tmp_path):
    src = source(tmp_path, "deveval", "deveval_prompts.jsonl", [NO_BELOW])
    (row,) = transcribe.transcription_rows([src], INSTR, SEP)
    assert texts(row) == [INSTR]
    assert all(p["type"] == "image" for p in row["parts"][1:])


def test_coderujb_keeps_only_the_instruction_and_the_pages(tmp_path):
    src = source(tmp_path, "coderujb", "coderujb_prompts.jsonl")
    rows = transcribe.transcription_rows([src], INSTR, SEP)
    assert rows and all(texts(r) == [INSTR] for r in rows)
    assert {r["condition"] for r in rows} == {"image12"}


def test_ids_filter_and_a_missing_id_fails(tmp_path):
    src = source(tmp_path, "deveval", "deveval_prompts.jsonl")
    rows = transcribe.transcription_rows([src], INSTR, SEP, ids={NO_BELOW})
    assert [r["id"] for r in rows] == [NO_BELOW]
    with pytest.raises(ValueError, match="no image rows"):
        transcribe.transcription_rows([src], INSTR, SEP, ids={NO_BELOW, "not.an.item"})


def test_a_row_in_two_sources_fails(tmp_path):
    src = source(tmp_path, "deveval", "deveval_prompts.jsonl", [NO_BELOW])
    with pytest.raises(ValueError, match="more than one source row"):
        transcribe.transcription_rows([src, src], INSTR, SEP)


def test_a_page_whose_pixels_changed_fails(tmp_path):
    src = source(tmp_path, "deveval", "deveval_prompts.jsonl", [NO_BELOW])
    row = next(r for r in read_jsonl(src) if r["condition"] == "image12")
    first = next(p for p in row["parts"] if p["type"] == "image")
    path = tmp_path / "deveval" / first["path"]
    with Image.open(path) as im:
        im = im.convert("RGB")
    im.putpixel((0, 0), (0, 0, 0))
    im.save(path)
    with pytest.raises(transcribe.PixelMismatch):
        transcribe.transcription_rows([src], INSTR, SEP)


def test_main_writes_one_requests_file(tmp_path):
    src = source(tmp_path, "deveval", "deveval_prompts.jsonl", [TWO_BLOCKS, NO_BELOW])
    transcribe.main(["--source", src, "--out", str(tmp_path / "transcribe")])
    out = tmp_path / "transcribe" / "deveval"
    rows = read_jsonl(out / "requests.jsonl")
    assert sorted(r["id"] for r in rows) == sorted([TWO_BLOCKS, NO_BELOW])
    assert not (out / "requests.jsonl.tmp").exists()


def test_the_instruction_names_the_marker_and_the_limits_fit():
    assert "⏎" in INSTR
    # worst main-run image prompt (10,040 tokens) plus max_tokens must not exceed the server limit
    assert 10040 + CFG["max_tokens"] <= CFG["max_model_len"]


def row(model, item, condition, tokens, run=0):
    return {"model": model, "id": item, "condition": condition, "run": run, "prompt_tokens": tokens}


def test_check_ids_take_the_top_items_per_model_and_their_union():
    rows = []
    for item, (t, i) in {"a": (100, 50), "b": (90, 70), "c": (10, 10), "d": (95, 55)}.items():
        rows += [row("m1", item, "text", t), row("m1", item, "image14", i)]
    rows += [row("m2", "c", "text", 999), row("m2", "c", "image14", 1),
             row("m2", "a", "text", 1), row("m2", "a", "image14", 1),
             row("m1", "c", "text", 10**6, run=1), row("m1", "c", "image10", 10**6)]
    assert check_ids.largest(rows, top=2) == ["a", "b", "c"]


def test_check_ids_break_ties_by_id():
    rows = [row("m", i, c, 5) for i in ("z", "y", "x") for c in ("text", "image14")]
    assert check_ids.largest(rows, top=2) == ["x", "y"]


_spec = importlib.util.spec_from_file_location(
    "transcription_score", os.path.join(ROOT, "scripts", "transcription_score.py"))
ts = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ts)


def dev_prompt(above, below=""):
    return ("Please complete the f function in the middle of a repository.\n\n"
            f"The contexts above the function are:\n```Python\n{above}\n```\n\n"
            f"The contexts below the function are:\n```Python\n{below}\n```\n\n"
            "The code to be completed is:\n```Python\ndef f():\n```\n\nCompleted code:")


def test_worked_example():
    cols = ts.capacity(12)[0]
    assert cols > 45
    comment = "# " + "z" * (cols - 4)
    # line 2 starts one column before a row end, so its 4 leading spaces are split by it
    above = f"{comment}\n    total = compute(arg)\ndef helper(arg):\n    return total + arg"
    below = "class Thing:\n    name = my_label"
    src = ts.source("deveval", dev_prompt(above, below), [12])
    assert src["names"] == ["Thing", "arg", "compute", "helper", "my_label", "name", "total"]
    reply = ("Here it is.\n```text\n" + comment + "\ntotal = compute(arg)\ndef helpr(arg):\n"
             "  return total + arg⏎class Thi\nng:\n    name = mylabel\n```")
    assert ts.score(src, 12, reply) == {
        "n_names": 7, "n_exact": 5, "n_underscore": 1, "n_near": 1, "R": 5 / 7,
        "mean_edit_distance": 2 / 7, "src_tokens": 24, "copy_tokens": 25,
        "text_match": 21 / 24, "copy_match": 21 / 25, "n_marks": 1, "src_lines": 6,
        "line_match": 3 / 6, "indent_match": 1 / 2, "indent_lost_rows": 1}


def test_python_names_skip_comments_strings_numbers_and_keywords():
    code = ('x = f"{hidden}" # cmt name\ny = 0x1F + 1e-5 + 10j + 1_000\n'
            "class Foo(Bar): pass\nrb's' + u'''t\nmulti'''\nonly_in_comment = 1 # only_here")
    assert ts.names("deveval", code) == {"x", "y", "Foo", "Bar", "only_in_comment"}


def test_java_names_skip_comments_strings_chars_text_blocks_and_numbers():
    code = ('@Override /* a b */ public int f(String s) { return 10L + 1.0f + 0xFFL + \'c\''
            ' + "q w"; } // z\nvar x = """\ntext\n""";')
    assert ts.names("coderujb", code) == {"Override", "String", "f", "s", "var", "x"}


def test_a_backslash_newline_continues_a_python_string():
    assert ts.names("deveval", "x = 'abc\\\ndef' + \"gh\\\nij\"\ny = 1") == {"x", "y"}


def test_names_keep_non_ascii_letters_and_java_dollars():
    assert ts.names("deveval", "café = 1") == {"café"}
    assert ts.names("coderujb", "int $x = a$b;") == {"$x", "a$b"}


def test_blocks_expand_tabs_cut_trailing_space_and_skip_an_empty_block():
    assert ts.blocks("deveval", dev_prompt("def g():\n\treturn 1   ")) == [
        ["def g():", "    return 1"]]


@pytest.mark.parametrize("reply, copy", [
    ("```text\na\nb\n```", "a\nb"),
    ("Sure:\n```python\na\n```\nDone.", "a"),
    ("```\na\nb", "a\nb"),
    ("a\nb", "a\nb"),
    ("```text\na\n```\nnext:\n```text\nb\n```", "a\n```\nnext:\n```text\nb"),
    ("```text\ns = '''\n```\n'''\n```", "s = '''\n```\n'''"),
])
def test_copy_runs_from_the_first_fence_to_the_last(reply, copy):
    assert ts.copy_of(reply) == copy


def small_source(code="total = compute(abc)"):
    return ts.source("deveval", dev_prompt(code), [12])


def test_a_three_character_name_is_never_near():
    s = ts.score(small_source(), 12, "total = compute(abd)")
    assert (s["n_exact"], s["n_near"], s["mean_edit_distance"]) == (2, 0, 1 / 3)


def test_an_unbalanced_quote_in_the_copy_hides_nothing():
    s = ts.score(small_source(), 12, 'x = "oops\ntotal = compute(abc)')
    assert s["R"] == 1.0


def test_a_one_line_reply_has_no_indent_match():
    s = ts.score(small_source("def g():\n    return total"), 12, "def g(): return total")
    assert (s["line_match"], s["indent_match"], s["R"]) == (0.0, None, 1.0)


def test_an_empty_reply_scores_zero_with_null_ratios():
    s = ts.score(small_source(), 12, "")
    assert (s["R"], s["text_match"], s["line_match"]) == (0.0, 0.0, 0.0)
    assert (s["copy_match"], s["mean_edit_distance"], s["indent_match"]) == (None, None, None)


def gen_row(item="i", run=0, reply="total = compute(abc)", error=None, finish="stop"):
    return {"model": "org/m", "benchmark": "deveval", "id": item, "condition": "image12",
            "run": run, "seed": run, "reply": reply, "error": error, "finish_reason": finish,
            "prompt_tokens": 5, "output_tokens": 3}


def test_an_error_row_has_null_scores_and_a_prefixed_key(monkeypatch):
    monkeypatch.setitem(ts.SOURCES, "i", small_source())
    row = ts.score_row(gen_row(reply=None, error="400 too long", finish=None))
    assert list(row) == ts.COLUMNS
    assert all(row[c] is None for c in ts.SCORES)
    assert row["key"] == "tr__org__m__i__image12__r0" and row["error"] == "400 too long"
    ok = ts.score_row(gen_row(finish="length"))
    assert (ok["R"], ok["truncated"]) == (1.0, True)


def test_grid_reports_missing_duplicate_and_extra_rows():
    reqs = [{"id": "i", "condition": "image12"}]
    rows, problems = ts.grid(["org/m"], reqs, 2, [gen_row(), gen_row(), gen_row(run=5)])
    assert [r["run"] for r in rows] == [0]
    assert sorted(p.split(" (")[0] for p in problems) == [
        "duplicate generation row", "generation row outside the grid:", "no generation row for"]


def test_lcs_matches_the_textbook_recurrence():
    rng = random.Random(1)
    for _ in range(200):
        a = [rng.choice("abc") for _ in range(rng.randint(0, 12))]
        b = [rng.choice("abc") for _ in range(rng.randint(0, 12))]
        prev = [0] * (len(b) + 1)
        for x in a:
            cur = [0]
            for j, y in enumerate(b, 1):
                cur.append(prev[j - 1] + 1 if x == y else max(prev[j], cur[-1]))
            prev = cur
        assert ts.lcs_len(a, b) == prev[-1]
