import hashlib
import io
import os

import pytest
from conftest import FIXTURES, ROOT, SCRATCH, need, read_ids, read_jsonl

from codeimg import config
from codeimg.prompts import (
    PromptError,
    item_requests,
    load_prompts,
    segments_coderujb,
    segments_deveval,
)
from codeimg.render import render

SENTENCE = config.load()["experiment"]["sentence"]
SIZES = [10, 12, 14]


def texts(parts):
    return [p["text"] for p in parts if p["type"] == "text"]


def test_coderujb_split_keeps_the_task_as_text():
    item = next(iter(load_prompts("coderujb", os.path.join(FIXTURES, "coderujb_prompts.jsonl")).values()))
    (k1, ctx, lang), (k2, task, _) = segments_coderujb(item["text"])
    assert (k1, k2, lang) == ("ctx", "text", "java")
    assert task.startswith("You are a professional Java programmer")
    assert item["text"] == "```java\n" + ctx + "\n```\n\n" + task


def test_deveval_empty_below_block_stays_as_text():
    items = load_prompts("deveval", os.path.join(FIXTURES, "deveval_prompts.jsonl"))
    item = items["mingus.core.value.determine"]
    rows = item_requests("deveval", item, SIZES, SENTENCE)
    assert rows[0]["parts"] == [{"type": "text", "text": item["text"]}]
    for r in rows[1:]:
        t = texts(r["parts"])
        assert t[0].startswith(SENTENCE + "\n\nPlease complete the determine function")
        assert "The contexts below the function are:\n\n```Python\n\n```\n\nThe code to be completed is:" in t[-1]
        assert t[-1].endswith("Completed code:")
        assert r["n_images"] == sum(p["type"] == "image" for p in r["parts"]) > 0


def test_deveval_parts_interleave_headers_and_pages():
    items = load_prompts("deveval", os.path.join(FIXTURES, "deveval_prompts.jsonl"))
    item = items["ydata_profiling.profile_report.ProfileReport.typeset"]
    kinds = [p["type"] for p in item_requests("deveval", item, [12], SENTENCE)[1]["parts"]]
    first_img, below = kinds.index("image"), kinds.index("text", 1)
    assert kinds[0] == "text" and first_img == 1
    assert "image" in kinds[below:]
    assert kinds[-1] == "text"


def test_page_files_are_written_with_their_hash(tmp_path):
    item = next(iter(load_prompts("coderujb", os.path.join(FIXTURES, "coderujb_prompts.jsonl")).values()))
    for px in SIZES:
        (tmp_path / "img" / str(px)).mkdir(parents=True)
    rows = item_requests("coderujb", item, SIZES, SENTENCE, str(tmp_path))
    counted = item_requests("coderujb", item, SIZES, SENTENCE)
    for r, c in zip(rows, counted):
        assert r["n_images"] == c["n_images"]
        for p in r["parts"]:
            if p["type"] == "image":
                assert (tmp_path / p["path"]).exists() and len(p["sha256"]) == 64


def test_bad_prompt_names_the_item():
    with pytest.raises(PromptError, match="item-1"):
        item_requests("deveval", {"id": "item-1", "text": "Complete this."}, SIZES, SENTENCE)


def test_every_coderujb_item_splits_losslessly():
    ids = read_ids(os.path.join(ROOT, "benchmarks/coderujb/results/final_ids.txt"))
    items = load_prompts("coderujb", need(os.path.join(SCRATCH, "coderujb", "prompts.jsonl")))
    for i in ids:
        segments_coderujb(items[i]["text"])


def test_every_deveval_item_splits_losslessly():
    path = os.environ.get("DEVEVAL_PROMPTS", "")
    rows = read_jsonl(need(path)) if path else pytest.skip("set DEVEVAL_PROMPTS to the prompt file")
    ids = set(read_ids(os.path.join(ROOT, "benchmarks/deveval/results/inrange_ids.txt")))
    for r in rows:
        if r["namespace"] in ids:
            segments_deveval(r["prompt"])


def test_pages_are_a_fresh_render_of_their_slice_in_order(tmp_path):
    items = load_prompts("deveval", os.path.join(FIXTURES, "deveval_prompts.jsonl"))
    item = items["ydata_profiling.profile_report.ProfileReport.typeset"]
    (tmp_path / "img" / "10").mkdir(parents=True)
    (row,) = item_requests("deveval", item, [10], SENTENCE, str(tmp_path))[1:]
    expected = []
    for _, code, _ in [s for s in segments_deveval(item["text"]) if s[0] == "ctx" and s[1].strip()]:
        for im in render(code, 10):
            buf = io.BytesIO()
            im.save(buf, "PNG")
            expected.append((hashlib.sha256(buf.getvalue()).hexdigest(),
                             hashlib.sha256(im.tobytes()).hexdigest()))
    got = [(p["sha256"], p["pixels_sha256"]) for p in row["parts"] if p["type"] == "image"]
    assert got == expected
    assert sum(t.count(SENTENCE) for t in texts(row["parts"])) == 1
