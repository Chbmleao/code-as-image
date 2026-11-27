"""Intervals and multiplicity corrections for the main analysis (methodology 3.3).

cluster_t is the clustered (CR1) t interval for a mean of item-level values: the residuals
are summed within each cluster, the variance gets the G / (G - 1) factor, and the t reference has
G - 1 df. item_t is the same with every item its own cluster, which is the ordinary paired t.
The item scores, paired differences and test rows after them are shared by the gaps and the
contamination checks.
"""
import math
from collections import defaultdict

from scipy import stats

from codeimg.analysis import inputs as inp
from codeimg.analysis import reliability as rel
from codeimg.analysis import resample as rs

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


def scores(data):
    """Y[m][c][j]: the mean of item j's runs."""
    return {m: {c: [sum(ys) / len(ys) for ys in data["cells"][m][c]] for c in data["conditions"]}
            for m in data["models"]}


def mean(xs):
    return math.fsum(xs) / len(xs)


def differences(y, a, b):
    """Per item, Y(a) - Y(b); a may be a list of conditions, averaged."""
    a = a if isinstance(a, list) else [a]
    return [mean([y[c][j] for c in a]) - y[b][j] for j in range(len(y[b]))]


def test_row(model, values, projects, **extra):
    c = cluster_t(values, projects)
    i = item_t(values)
    return {"model": inp.name(model), "repo": model, **extra, "est": c["est"], "n": c["n"],
            "cluster": {k: c[k] for k in ("clusters", "df", "se", "lo", "hi", "p")},
            "item": {k: i[k] for k in ("df", "se", "lo", "hi", "p")}}


def adjust(rows, how, key):
    ps = [r["cluster"]["p"] for r in rows]
    for r, q in zip(rows, (holm if how == "holm" else bh)(ps)):
        r[key] = q


def pooled(d_by_model, groups, seed, n_boot):
    """Mean of the model gaps, with the resample interval: each draw keeps the same items for
    every model."""
    models = list(d_by_model)
    est = mean([mean(d_by_model[m]) for m in models])
    per_draw = [mean([mean([d_by_model[m][j] for j in idx]) for m in models])
                for idx in rs.cluster_draws(groups, n_boot, seed)]
    s = rel.summarize(per_draw)
    return {"est": est, "lo": s["lo"], "hi": s["hi"], "n_boot": n_boot}


def bucket_of(n, buckets):
    for k, (lo, hi) in enumerate(buckets):
        if lo <= n < hi:
            return k
    raise ValueError(f"{n} tokens is outside every length bucket {buckets}")


def check_lengths(b, items, lengths):
    missing = [i for i in items if i not in lengths]
    if missing:
        raise ValueError(f"{b}: no prompt count for {len(missing)} item(s), first {missing[0]}")


def spread(values):
    v = sorted(values)
    return {"median": rel.quantile(v, 0.5), "q1": rel.quantile(v, 0.25),
            "q3": rel.quantile(v, 0.75)}
