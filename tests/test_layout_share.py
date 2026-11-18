import copy
import csv
import importlib.util
import json
import os
import statistics

import pytest
from conftest import FIXTURES, ROOT

from codeimg import config
from codeimg.prompts import item_requests, load_prompts
from codeimg.render import NEWLINE_MARK, render

_spec = importlib.util.spec_from_file_location("layout_share",
                                               os.path.join(ROOT, "scripts", "layout_share.py"))
ls = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ls)

SENTENCE = config.load()["experiment"]["sentence"]
SIZES = [10, 12, 14]


def test_leading_spaces_are_counted_per_line():
    m = ls.measure("def f():\n    return 1   \n", [12])
    assert (m["leading"], m["chars"]) == (4, len("def f():" + NEWLINE_MARK + "    return 1" + NEWLINE_MARK))


def test_tabs_count_as_four_spaces_and_blank_lines_as_none():
    assert ls.measure("\tx\n      \ny", [10])["leading"] == 4


def test_a_wrapped_line_counts_its_indentation_once():
    # 86 columns at 12 px: the line wraps, and the spaces that start its second row are not indentation
    line = "        " + "x" * 78 + "   y"
    m = ls.measure(line, [12])
    assert m["sizes"][12]["pages"] == 1 and m["chars"] > 86
    assert m["leading"] == 8


def test_the_what_if_removes_exactly_the_counted_spaces():
    for bench in ("coderujb", "deveval"):
        for item in load_prompts(bench, os.path.join(FIXTURES, f"{bench}_prompts.jsonl")).values():
            for seg in ls.segments(bench, item["text"]):
                m = ls.measure(seg, SIZES)
                assert m["leading"] > 0
                assert m["chars"] - m["chars2"] == m["leading"]
                assert all(s["pages2"] <= s["pages"] and s["area2"] < s["area"]
                           for s in m["sizes"].values())


def test_area_is_the_size_render_gives_each_page():
    code = "\n".join("    " + "z" * 70 for _ in range(400))
    pages = render(code, 10)
    assert len(pages) >= 2
    assert ls.measure(code, [10])["sizes"][10]["area"] == sum(w * h for w, h in (im.size for im in pages))


def test_a_newline_marker_in_the_source_stops_the_item():
    with pytest.raises(ls.Mismatch, match="newline marker"):
        ls.measure_item("deveval", "x", ["a = '" + NEWLINE_MARK + "'"], SIZES)


def test_step_is_the_14_to_12_px_drop():
    assert ls.step(SIZES) == pytest.approx(1 - (15 / 86) / (18 / 75))


def _item(bench, i, leading, chars, saved):
    return {"benchmark": bench, "id": str(i), "chars": chars, "leading": leading,
            "sizes": {px: {"pages": 2, "pages2": 1, "area": 1000, "area2": round(1000 * (1 - saved))}
                      for px in SIZES}}


def test_summary_uses_type_1_quantiles_and_the_threshold():
    saved = [0.1, 0.2, 0.3, 0.4]
    items = [_item("b", i, leading, 100, s) for i, (leading, s) in enumerate(zip([10, 20, 30, 40], saved))]
    s = ls.summarize(items, SIZES)
    e = s["benchmarks"]["b"]
    # type 1 with even n takes the lower middle value, not the mean of the two
    assert e["share"]["median"] == 0.2 and e["share"]["pooled"] == 0.25
    assert (e["share"]["p25"], e["share"]["p75"]) == (0.1, 0.3)
    assert e["share"]["mean"] == pytest.approx(0.25)
    assert e["share"]["sd"] == pytest.approx(statistics.stdev([0.1, 0.2, 0.3, 0.4]))
    saved12 = e["sizes"]["12"]["area_saved"]
    assert (saved12["median"], saved12["p25"], saved12["p75"]) == pytest.approx((0.2, 0.1, 0.3))
    assert e["sizes"]["12"]["pages"] == 8 and e["sizes"]["12"]["pages2"] == 4
    assert s["verdict"] == "small"


def test_one_cell_at_the_threshold_makes_it_large(monkeypatch):
    monkeypatch.setattr(ls, "step", lambda sizes: 0.25)

    def verdict(deveval_14_area2):
        items = [_item(b, i, 10, 100, 0.1) for b in ("coderujb", "deveval") for i in range(3)]
        for i in items[3:]:
            i["sizes"][14]["area2"] = deveval_14_area2
        return ls.summarize(items, SIZES)["verdict"]

    assert verdict(751) == "small"
    assert verdict(750) == "large"


def _requests(tmp_path):
    """Fixture items rendered as the main run did, and the page manifest built from them."""
    out, manifests = tmp_path / "requests", tmp_path / "manifests"
    manifests.mkdir()
    for bench in ("coderujb", "deveval"):
        for px in SIZES:
            (out / bench / "img" / str(px)).mkdir(parents=True)
        rows = []
        for item in load_prompts(bench, os.path.join(FIXTURES, f"{bench}_prompts.jsonl")).values():
            rows += item_requests(bench, item, SIZES, SENTENCE, str(out / bench))
        with open(out / bench / "requests.jsonl", "w", encoding="utf-8") as f:
            f.writelines(json.dumps(r, ensure_ascii=False) + "\n" for r in rows)
        pages = {}
        for r in rows:
            if r["condition"] != "text":
                pages.setdefault(r["id"], {"id": r["id"]})[r["condition"]] = r["n_images"]
        with open(manifests / f"{bench}.jsonl", "w") as f:
            f.writelines(json.dumps(p) + "\n" for p in pages.values())
    return out, manifests


def _rows(path):
    return ls.read_jsonl(str(path))


def test_verify_passes_on_the_same_render_and_fails_on_any_difference(tmp_path):
    out, manifests = _requests(tmp_path)
    rows, manifest = _rows(out / "deveval" / "requests.jsonl"), _rows(manifests / "deveval.jsonl")
    segs, compared = ls.verify("deveval", rows, manifest, SIZES)
    assert set(segs) == {m["id"] for m in manifest}
    assert compared == sum(r["n_images"] for r in rows)

    for key, value in (("pixels_sha256", "0" * 64), ("size", [616, 1])):
        tampered = copy.deepcopy(rows)
        next(p for r in tampered for p in r["parts"] if p["type"] == "image")[key] = value
        with pytest.raises(ls.Mismatch, match="page 1"):
            ls.verify("deveval", tampered, manifest, SIZES)

    with pytest.raises(ls.Mismatch, match="no text row"):
        ls.verify("deveval", [r for r in rows if r["condition"] != "text"], manifest, SIZES)

    with pytest.raises(ls.Mismatch, match="repeated image12"):
        ls.verify("deveval", rows + [r for r in rows if r["condition"] == "image12"][:1],
                  manifest, SIZES)

    counts = copy.deepcopy(manifest)
    counts[0]["image12"] += 1
    with pytest.raises(ls.Mismatch, match="12 px"):
        ls.verify("deveval", rows, counts, SIZES)

    with pytest.raises(ls.Mismatch, match="1 manifest items missing"):
        ls.verify("deveval", [r for r in rows if r["id"] != manifest[0]["id"]], manifest, SIZES)


def test_main_writes_the_outputs_from_one_summary(tmp_path):
    out, manifests = _requests(tmp_path)
    dest = tmp_path / "layout"
    ls.main(["--requests", str(out), "--out", str(dest), "--manifests", str(manifests)])
    with open(dest / "items.csv") as f:
        items = list(csv.DictReader(f))
    summary = json.loads((dest / "layout.json").read_text())
    assert len(items) == summary["verified"]["items"] * len(SIZES) == 4 * len(SIZES)
    text = (dest / "findings.md").read_text()
    assert text == ls.findings(summary)
    assert f"**Verdict: {summary['verdict']}.**" in text
    assert ls.pct(summary["benchmarks"]["deveval"]["share"]["mean"]) in text


def test_main_writes_nothing_on_a_mismatch(tmp_path):
    out, manifests = _requests(tmp_path)
    path = out / "coderujb" / "requests.jsonl"
    rows = _rows(path)
    next(p for r in rows for p in r["parts"] if p["type"] == "image")["pixels_sha256"] = "0" * 64
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    dest = tmp_path / "layout"
    with pytest.raises(SystemExit, match="nothing written"):
        ls.main(["--requests", str(out), "--out", str(dest), "--manifests", str(manifests)])
    assert not dest.exists()
