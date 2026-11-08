import os

from conftest import ROOT, read_jsonl

from codeimg import config, sample


def test_largest_remainder_matches_the_methods():
    assert sample.largest_remainder({"a": 389, "b": 350, "c": 120}, 200) == {"a": 91, "b": 81, "c": 28}
    assert sample.largest_remainder({"x": 1, "y": 1}, 1) == {"x": 1, "y": 0}


def test_committed_manifests_match_a_fresh_draw():
    pages = {b: read_jsonl(os.path.join(ROOT, "manifests", "pages", f"{b}.jsonl"))
             for b in ("deveval", "coderujb")}
    for (name, bench), ids in sample.build(config.load(), pages).items():
        with open(os.path.join(ROOT, "manifests", name, f"{bench}.txt")) as f:
            assert f.read().split() == ids, (name, bench)


def test_smoke_takes_the_largest_item_and_draws_the_rest_without_it():
    import random
    pages = [{"id": "a", "image14": 3}, {"id": "b", "image14": 9}, {"id": "c", "image14": 9}]
    picked = sample.smoke(["b", "x", "y", "z"], pages, 3, random.Random(0))
    assert "b" in picked and len(set(picked)) == 3
