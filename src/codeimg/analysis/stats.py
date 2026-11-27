"""Intervals and multiplicity corrections for the main analysis (methodology 3.3).

cluster_t is the clustered (CR1) t interval for a mean of item-level values: the residuals
are summed within each cluster, the variance gets the G / (G - 1) factor, and the t reference has
G - 1 df. item_t is the same with every item its own cluster, which is the ordinary paired t.
"""
import math
from collections import defaultdict

from scipy import stats

LEVEL = 0.95


def cluster_t(values, labels, level=LEVEL):
    """Mean of values with a CR1 t interval clustered by labels (one label per value)."""
    n = len(values)
    if n == 0 or n != len(labels):
        raise ValueError("values and labels must be non-empty and the same length")
    est = math.fsum(values) / n
    sums = defaultdict(float)
    for v, g in zip(values, labels):
        sums[g] += v - est
    g = len(sums)
    out = {"est": est, "n": n, "clusters": g, "df": g - 1,
           "se": None, "lo": None, "hi": None, "t": None, "p": None}
    if g < 2:
        return out
    se = math.sqrt(g / (g - 1) * math.fsum(s * s for s in sums.values())) / n
    out["se"] = se
    if se == 0:
        out.update(lo=est, hi=est)
        return out
    q = stats.t.ppf(0.5 + level / 2, g - 1)
    t = est / se
    out.update(lo=est - q * se, hi=est + q * se, t=t, p=float(2 * stats.t.sf(abs(t), g - 1)))
    return out


def item_t(values, level=LEVEL):
    return cluster_t(values, list(range(len(values))), level)


def wald_contrast(est, cov, weights, level=LEVEL):
    """sum(w * est) with its Wald interval; cov is the covariance matrix of est, as rows."""
    k = len(est)
    if len(weights) != k or len(cov) != k or any(len(r) != k for r in cov):
        raise ValueError("est, cov and weights must have matching sizes")
    c = math.fsum(w * e for w, e in zip(weights, est))
    var = math.fsum(weights[i] * cov[i][j] * weights[j] for i in range(k) for j in range(k))
    if var < 0:
        raise ValueError(f"negative variance {var}: cov is not a covariance matrix")
    se = math.sqrt(var)
    q = stats.norm.ppf(0.5 + level / 2)
    return {"est": c, "se": se, "lo": c - q * se, "hi": c + q * se}


def holm(ps):
    """Holm adjusted p-values, in the input order; None stays None and is not counted."""
    idx = sorted((k for k, p in enumerate(ps) if p is not None), key=lambda k: ps[k])
    m = len(idx)
    out = [None] * len(ps)
    running = 0.0
    for rank, k in enumerate(idx):
        running = max(running, min(1.0, (m - rank) * ps[k]))
        out[k] = running
    return out


def bh(ps):
    """Benjamini-Hochberg adjusted p-values, in the input order; None stays None."""
    idx = sorted((k for k, p in enumerate(ps) if p is not None), key=lambda k: ps[k])
    m = len(idx)
    out = [None] * len(ps)
    running = 1.0
    for rank in range(m - 1, -1, -1):
        k = idx[rank]
        running = min(running, ps[k] * m / (rank + 1))
        out[k] = running
    return out
