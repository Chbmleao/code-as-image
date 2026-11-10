import importlib.util
import json
import math
import os
import random
import statistics
from fractions import Fraction as F

import pytest
from conftest import ROOT

_spec = importlib.util.spec_from_file_location("dstudy", os.path.join(ROOT, "scripts", "dstudy.py"))
ds = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ds)

M0, M1 = list(ds.NAMES)[:2]

# items x (text, image10, image12, image14) x runs
HAND = [
    [[1, 1, 1], [0, 0, 1], [0, 1, 1], [0, 0, 0]],
    [[1, 1, 1], [0, 0, 0], [0, 0, 1], [1, 0, 0]],
    [[0, 1, 0], [0, 1, 1], [1, 1, 0], [0, 0, 0]],
]


def test_hand_example():
    # d = -2/3, -7/9, 1/9 so s^2(d) = 19/81; B = 1/9 + (6/9) / 9 = 5/27, while the pooled
    # (4/3) x mean run variance would be 7/27; A = 19/81 - 5/81.
    # SS item 1/18 (2 df), item:condition 35/18 (6 df), run:cell 14/3 (24 df), so
    # MS 1/36, 35/108, 7/36 and the G-study item (1/36 - 35/108) / 12, item:condition
    # (35/108 - 7/36) / 3, run 7/36.
    want = {"A": F(14, 81), "B": F(5, 27), "text": F(1, 9), "image10": F(2, 9),
            "image12": F(1, 3), "image14": F(1, 9), "item": F(-2, 81),
            "item_condition": F(7, 162), "run": F(7, 36)}
    se2 = {1: F(29, 243), 2: F(43, 486), 3: F(19, 243)}
    got = ds.components(ds.item_stats(HAND), range(3))
    for k, v in want.items():
        assert got[k] == pytest.approx(float(v), abs=1e-12), k
    assert got["A"] + got["B"] / 3 == pytest.approx(float(F(19, 81)), abs=1e-12)
    for j, v in se2.items():
        assert got[f"se{j}"] == pytest.approx(math.sqrt(v), abs=1e-12)
    assert got["ratio"] == pytest.approx(math.sqrt(F(43, 38)), abs=1e-12)
    assert got["run"] == pytest.approx(statistics.mean(got[c] for c in ds.CONDITIONS), abs=1e-12)


def logistic(x):
    return 1 / (1 + math.exp(-x))


def simulate(rng, n):
    probs, cells = [], []
    for _ in range(n):
        u = rng.gauss(0, 1)
        p = [logistic(u + rng.gauss(0, 0.5))]
        p += [logistic(-1.8 + 0.6 * u + rng.gauss(0, 0.5)) for _ in range(3)]
        probs.append(p)
        cells.append([[int(rng.random() < q) for _ in range(3)] for q in p])
    return probs, cells


def targets(probs):
    n, nc = len(probs), 4
    gap = [statistics.mean(p[1:]) - p[0] for p in probs]
    rows = [statistics.mean(p) for p in probs]
    cols = [statistics.mean(p[c] for p in probs) for c in range(nc)]
    grand = statistics.mean(rows)
    ss_int = sum((p[c] - rows[i] - cols[c] + grand) ** 2
                 for i, p in enumerate(probs) for c in range(nc))
    return {"A": statistics.variance(gap),
            "B": statistics.mean(p[0] * (1 - p[0]) + sum(q * (1 - q) for q in p[1:]) / 9
                                 for p in probs),
            "run": statistics.mean(q * (1 - q) for p in probs for q in p),
            "item_condition": ss_int / ((n - 1) * (nc - 1)),
            "item": statistics.variance(rows) - ss_int / ((n - 1) * (nc - 1) * nc)}


def test_estimators_are_unbiased_on_simulated_blocks():
    rng = random.Random(17)
    diffs = {k: [] for k in ("A", "B", "run", "item_condition", "item", "pooled")}
    for _ in range(200):
        probs, cells = simulate(rng, 200)
        got, want = ds.components(ds.item_stats(cells), range(200)), targets(probs)
        for k, d in diffs.items():
            d.append(4 / 3 * got["run"] - want["B"] if k == "pooled" else got[k] - want[k])
    for k, d in diffs.items():
        mc_se = statistics.stdev(d) / math.sqrt(len(d))
        if k == "pooled":
            assert abs(statistics.mean(d)) > 3 * mc_se
        else:
            assert abs(statistics.mean(d)) < 3 * mc_se, k


def test_ratio_and_decision():
    assert ds.decide(ds.ratio(29, 63)) == 2
    assert ds.decide(1.10) == 2
    assert ds.decide(math.nextafter(1.10, 2)) == 3
    assert ds.ratio(-0.01, 0.1) == pytest.approx(math.sqrt(1.5))
    assert ds.decide(ds.ratio(-0.01, 0.1)) == 3
    for a in (-0.01, 0, 0.05):
        assert ds.ratio(a, 0) == 1.0
        assert ds.decide(ds.ratio(a, 0)) == 2
    rng = random.Random(5)
    for _ in range(1000):
        r = ds.ratio(rng.uniform(-1, 1), rng.uniform(0, 1))
        assert 1 <= r <= math.sqrt(1.5) + 1e-12
    same = ds.components(ds.item_stats([HAND[0]] * 3), range(3))
    assert same["A"] < 0
    for j in (1, 2, 3):
        assert same[f"se{j}"] == pytest.approx(math.sqrt(same["B"] / j / 3), abs=1e-12)


def test_labels():
    assert ds.firm(2, [1.05, 1.08], [1.05, 1.08])
    assert not ds.firm(2, [1.08, 1.12], [1.08, 1.12])
    assert not ds.firm(2, [1.05, 1.08], [1.05, 1.10])
    assert not ds.firm(3, [1.10, 1.15], [1.12, 1.15])
    assert not ds.firm(2, [1.12, 1.15], [1.12, 1.15])
    assert ds.firm(3, [1.12, 1.15], [1.12, 1.15])
    assert not ds.firm(3, [1.12, 1.15], [1.10, 1.15])
    assert not ds.firm(3, [1.12, 1.15], [1.09, 1.15])
    assert ds.weak(0.1, [0.0, 0.2])
    assert ds.weak(-0.01, [-0.02, 0.005])
    assert not ds.weak(0.1, [0.05, 0.12])


def test_tiny_negative_variance_prints_without_sign():
    assert ds.fmt_var({"est": -1e-5, "ci": [-2e-5, 3e-5]}) == "0.0000 (0.0000 to 0.0000)"
    assert ds.fmt_var({"est": -0.0123, "ci": [-0.05, 0.02]}, negative_is_zero=True) == (
        "-0.0123 (-0.0500 to 0.0200), taken as 0 in the projection")


def test_ratio_display_shows_the_side_of_the_margin():
    assert ds.fmt_ratio(1.0412) == "1.041"
    assert ds.fmt_ratio(1.1) == "1.100"
    assert ds.fmt_ratio(1.0996) == "1.0996"
    assert ds.fmt_ratio(1.10004) == "1.10004"
    assert float(ds.fmt_ratio(math.nextafter(1.1, 2))) > 1.1


def test_percentile_interval():
    assert ds.interval(range(1, 2001)) == [51, 1950]


def test_identical_items_give_a_point_item_interval():
    item = [[1, 0, 1], [0, 0, 1], [0, 0, 0], [1, 1, 0]]
    (row,) = ds.study("deveval", {M0: [item] * 8}, [[0, 1, 2], [3, 4], [5, 6, 7]], 1, 50)
    assert row["ratio"]["ci_item"] == [row["ratio"]["est"]] * 2


def test_one_cluster_gives_a_point_cluster_interval():
    _, cells = simulate(random.Random(2), 30)
    (row,) = ds.study("deveval", {M0: cells}, [list(range(30))], 1, 50)
    assert row["ratio"]["ci_cluster"] == [row["ratio"]["est"]] * 2
    assert row["ratio"]["ci_item"][0] < row["ratio"]["ci_item"][1]


def synthetic_rows(rng, ids, models=tuple(ds.NAMES)):
    rows = []
    for m in models:
        for i in ids:
            for c in ds.CONDITIONS:
                p = rng.uniform(0.2, 0.8) if c == "text" else rng.uniform(0, 0.4)
                rows += [{"model": m, "id": i, "condition": c, "run": r,
                          "passed": rng.random() < p} for r in range(3)]
    return rows


def write_jsonl(path, rows):
    path.write_text("".join(json.dumps(r) + "\n" for r in rows))


def write_block(tmp_path, monkeypatch, n=12):
    rng = random.Random(4)
    block, manifests = tmp_path / "block", tmp_path / "manifests"
    block.mkdir()
    manifests.mkdir()
    clusters = {}
    for b in ds.BENCHES:
        ids = [f"{b}{i:02d}" for i in range(n)]
        (manifests / f"{b}.txt").write_text("\n".join(ids) + "\n")
        write_jsonl(block / f"{b}.collected.jsonl", synthetic_rows(rng, ids))
        _, key, label = ds.CLUSTERS[b]
        write_jsonl(tmp_path / f"{b}_gold.jsonl", [{key: i, label: f"p{j % 4}"}
                                                   for j, i in enumerate(ids)])
        clusters[b] = (str(tmp_path / f"{b}_gold.jsonl"), key, label)
    monkeypatch.setattr(ds, "CLUSTERS", clusters)
    monkeypatch.setattr(ds, "N_BOOT", 50)
    return ["--block", str(block), "--manifests", str(manifests)]


def run_main(args, out):
    ds.main(args + ["--out", str(out)])
    return json.loads((out / "dstudy.json").read_text()), (out / "dstudy.json").read_bytes()


def test_seed_moves_intervals_not_estimates(tmp_path, monkeypatch):
    args = write_block(tmp_path, monkeypatch)
    first, first_bytes = run_main(args, tmp_path / "a")
    _, again_bytes = run_main(args, tmp_path / "b")
    assert again_bytes == first_bytes
    assert (tmp_path / "a" / "dstudy.md").read_bytes() == (tmp_path / "b" / "dstudy.md").read_bytes()
    monkeypatch.setattr(ds, "SEED", ds.SEED + 1)
    other, _ = run_main(args, tmp_path / "c")

    def leaves(x, path=()):
        if isinstance(x, list) and x and isinstance(x[0], dict):
            x = dict(enumerate(x))
        if isinstance(x, dict):
            for k, v in x.items():
                yield from leaves(v, path + (k,))
        else:
            yield path, x

    a, c = dict(leaves(first["rows"])), dict(leaves(other["rows"]))
    est = [p for p in a if p[-1] == "est" or p[-1] == "run" and p[-2] == "gstudy"]
    ci = [p for p in a if p[-1] in ("ci", "ci_item", "ci_cluster")]
    assert est and all(a[p] == c[p] for p in est)
    assert any(a[p] != c[p] for p in ci)


@pytest.mark.parametrize("case, match", [
    ("two runs", f"deveval {M0} b image12: runs [0, 1], expected [0, 1, 2]"),
    ("duplicated run", f"deveval {M0} b text: runs [0, 1, 1, 2]"),
    ("missing condition", f"deveval {M0} b image14: missing condition"),
    ("model missing an item", f"deveval {M1} c: manifest item with no rows"),
    ("model missing", f"deveval {M1} a: manifest item with no rows"),
    ("duplicated manifest id", "deveval a: duplicated in the manifest"),
    ("id outside the manifest", f"deveval {min(ds.NAMES)} c: id not in the manifest"),
    ("unknown model", "deveval: unknown model org/unknown"),
    ("unknown condition", f"deveval {M0} b image16: unknown condition"),
    ("missing cluster label", "deveval b: no cluster label"),
])
def test_bad_input_raises(case, match):
    ids = ["a", "b", "c"]
    rows = synthetic_rows(random.Random(3), ids)
    labels = {i: "p" for i in ids}

    def cell(r, m, i, c=None):
        return r["model"] == m and r["id"] == i and c in (None, r["condition"])

    if case == "two runs":
        rows = [r for r in rows if not (cell(r, M0, "b", "image12") and r["run"] == 2)]
    elif case == "duplicated run":
        rows += [r for r in rows if cell(r, M0, "b", "text") and r["run"] == 1]
    elif case == "missing condition":
        rows = [r for r in rows if not cell(r, M0, "b", "image14")]
    elif case == "model missing an item":
        rows = [r for r in rows if not cell(r, M1, "c")]
    elif case == "model missing":
        rows = [r for r in rows if r["model"] != M1]
    elif case == "duplicated manifest id":
        ids = ["a", "b", "c", "a"]
    elif case == "id outside the manifest":
        ids = ["a", "b"]
    elif case == "unknown condition":
        rows += [dict(r, condition="image16") for r in rows if cell(r, M0, "b", "text")]
    elif case == "unknown model":
        rows += [dict(r, model="org/unknown") for r in rows if r["model"] == M1]
    else:
        del labels["b"]
    with pytest.raises(ValueError) as e:
        ds.load("deveval", rows, ids, labels)
    assert match in str(e.value)


def test_bad_input_exits_1(tmp_path, monkeypatch, capsys):
    args = write_block(tmp_path, monkeypatch)
    path = tmp_path / "block" / "deveval.collected.jsonl"
    path.write_text("".join(path.read_text().splitlines(keepends=True)[1:]))
    with pytest.raises(SystemExit) as e:
        ds.main(args + ["--out", str(tmp_path / "out")])
    assert e.value.code == 1
    assert "runs [1, 2]" in capsys.readouterr().err


def test_real_block_matches_committed_outputs(tmp_path):
    block = os.path.join(ROOT, "results", "block1")
    ds.main(["--block", block, "--manifests", os.path.join(ROOT, "manifests", "block1"),
             "--out", str(tmp_path)])
    for name in ("dstudy.json", "dstudy.md"):
        with open(os.path.join(block, name), "rb") as f:
            assert (tmp_path / name).read_bytes() == f.read(), name
    doc = json.loads((tmp_path / "dstudy.json").read_text())
    assert set(doc) == {"margin", "n_boot", "seed", "rows"}
    rows = doc["rows"]
    assert len(rows) == 10
    keys = {"benchmark", "model", "name", "n_items", "n_clusters", "gap", "run_by_condition", "se",
            "ratio", "runs", "firm", "weak", "gstudy"}
    assert all(set(r) == keys for r in rows)
    for r in rows:
        assert set(r["gap"]) == {"A", "B"} and set(r["se"]) == {"1", "2", "3"}
        assert set(r["run_by_condition"]) == set(ds.CONDITIONS)
        assert set(r["ratio"]) == {"est", "ci_item", "ci_cluster"}
        assert set(r["gstudy"]) == {"item", "item_condition", "run"}
        assert r["runs"] in (2, 3)
    assert [r["n_items"] for r in rows] == [40] * 5 + [200] * 5
    assert [r["n_clusters"] for r in rows] == [10] * 5 + [56] * 5
    md = (tmp_path / "dstudy.md").read_text(encoding="utf-8")
    assert not set(md) & set("\u2014\u2013\u2026\u2018\u2019\u201c\u201d")
