import csv
import json
import os

import pytest
from conftest import ROOT

from codeimg.analysis import glmm_cells as gc

ds = gc.ds

COUNTS = {"coderujb": (136, 40), "deveval": (859, 200)}


def real_design(b):
    path, key, label = ds.CLUSTERS[b]
    labels = {r[key]: r[label] for r in ds.read_jsonl(os.path.join(ROOT, path))}
    ids = ds.read_ids(os.path.join(ROOT, gc.ID_LISTS[b]))
    block = ds.read_ids(os.path.join(ROOT, "manifests", "block1", f"{b}.txt"))
    return gc.design(b, ids, block, labels), block


@pytest.mark.parametrize("b", ds.BENCHES)
def test_design_of_the_real_items(b):
    rows, block = real_design(b)
    n_items, n_block = COUNTS[b]
    assert len(rows) == n_items
    assert all(project for _, project, _ in rows)
    assert {i for i, _, n in rows if n == 3} == set(block)
    assert len(block) == n_block
    assert {n for i, _, n in rows if i not in set(block)} == {2}


def test_design_rejects_bad_ids():
    labels = {"a": "p", "b": "p"}
    with pytest.raises(ValueError, match="duplicated"):
        gc.design("deveval", ["a", "a"], [], labels)
    with pytest.raises(ValueError, match="no cluster label"):
        gc.design("deveval", ["a", "z"], [], labels)
    with pytest.raises(ValueError, match="not in the item list"):
        gc.design("deveval", ["a"], ["b"], labels)


def fixture_rows(passes):
    """passes maps (model, item, condition) to the 3 run results."""
    rows = []
    for m in ds.NAMES:
        for i in ("x", "y"):
            for c in ds.CONDITIONS:
                ys = passes.get((m, i, c), [0, 0, 0])
                rows += [{"model": m, "id": i, "condition": c, "run": r, "passed": y}
                         for r, y in enumerate(ys)]
    return rows


def test_block_cells_match_a_hand_count():
    m0, m1 = list(ds.NAMES)[:2]
    passes = {(m0, "x", "text"): [1, 1, 0], (m0, "y", "image12"): [1, 1, 1],
              (m1, "y", "text"): [0, 1, 0]}
    got = gc.block_cells("coderujb", fixture_rows(passes), ["x", "y"], {"x": "p1", "y": "p2"})
    assert len(got) == 5 * 2 * 4
    assert all(n == 3 for *_, n in got)
    by = {(m, i, c): (p, k) for m, i, c, p, k, _ in got}
    assert by[(m0, "x", "text")] == ("p1", 2)
    assert by[(m0, "y", "image12")] == ("p2", 3)
    assert by[(m1, "y", "text")] == ("p2", 1)
    assert sum(k for *_, k, _ in got) == 6


def test_block_cells_reject_unbalanced_runs():
    rows = fixture_rows({})[:-1]
    with pytest.raises(ValueError, match="runs"):
        gc.block_cells("coderujb", rows, ["x", "y"], {"x": "p1", "y": "p2"})


def test_main_writes_both_csvs(tmp_path, monkeypatch):
    b = "coderujb"
    ids = ["x", "y", "z"]
    (tmp_path / "manifests").mkdir()
    (tmp_path / "manifests" / f"{b}.txt").write_text("x\ny\n")
    (tmp_path / "block").mkdir()
    (tmp_path / "block" / f"{b}.collected.jsonl").write_text(
        "".join(json.dumps(r) + "\n" for r in fixture_rows({})))
    _, key, label = ds.CLUSTERS[b]
    gold = tmp_path / "gold.jsonl"
    gold.write_text("".join(json.dumps({key: i, label: "p"}) + "\n" for i in ids))
    (tmp_path / "ids.txt").write_text("\n".join(ids) + "\n")
    monkeypatch.setattr(ds, "BENCHES", (b,))
    monkeypatch.setattr(ds, "CLUSTERS", {b: (str(gold), key, label)})
    monkeypatch.setattr(gc, "ID_LISTS", {b: str(tmp_path / "ids.txt")})
    gc.main(["--block", str(tmp_path / "block"), "--manifests", str(tmp_path / "manifests"),
             "--out", str(tmp_path / "out")])
    with open(tmp_path / "out" / f"design_{b}.csv") as f:
        assert [(r["item"], r["n"]) for r in csv.DictReader(f)] == [("x", "3"), ("y", "3"),
                                                                    ("z", "2")]
    with open(tmp_path / "out" / f"block1_{b}_cells.csv") as f:
        assert len(list(csv.DictReader(f))) == 40
