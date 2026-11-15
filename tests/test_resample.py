import importlib.util
import os
from collections import Counter

from conftest import ROOT

_spec = importlib.util.spec_from_file_location("resample",
                                               os.path.join(ROOT, "scripts", "resample.py"))
rs = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rs)

GROUPS = [[0, 1], [2], [3, 4, 5]]


def test_same_seed_same_draws():
    assert rs.cluster_draws(GROUPS, 50, "7-x") == rs.cluster_draws(GROUPS, 50, "7-x")
    assert rs.cluster_draws(GROUPS, 50, "7-x") != rs.cluster_draws(GROUPS, 50, "7-y")


def test_draws_are_whole_clusters():
    draws = rs.cluster_draws(GROUPS, 200, 1)
    assert len(draws) == 200
    for d in draws:
        n = Counter(d)
        for g in GROUPS:
            assert len({n[j] for j in g}) == 1
        assert sum(n[g[0]] for g in GROUPS) == len(GROUPS)
    assert {tuple(sorted(d)) for d in draws} >= {(0, 0, 1, 1, 2), (2, 2, 2)}
