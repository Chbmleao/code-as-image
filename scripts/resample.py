"""The joint cluster resample shared by the reliability analysis and the main analysis.

A draw takes as many clusters as there are (CoderUJB projects, DevEval repositories), with
replacement, and keeps every item of each drawn cluster. Callers apply one draw to every model and
condition of a benchmark, so the draws are joint. Seed with f"{SEED}-{benchmark}", as dstudy does,
so both benchmarks get their own stream and every caller gets the same draws.
"""
import random

SEED = 20261114
N_BOOT = 2000


def cluster_draws(groups, n_boot, seed):
    """Item positions of each draw; groups is dstudy.clusters output (positions per cluster)."""
    rng = random.Random(seed)
    return [[j for g in rng.choices(groups, k=len(groups)) for j in g] for _ in range(n_boot)]
