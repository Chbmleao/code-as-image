import math

import pytest
from scipy import stats

from codeimg.analysis import stats as st


def test_cluster_t_by_hand_with_unequal_clusters():
    values = [1, 2, 3, 4, 10, 0]
    labels = ["a", "a", "b", "b", "b", "c"]
    est = 20 / 6
    # residuals summed per cluster: a 3 - 2 est, b 17 - 3 est, c 0 - est
    sums = [3 - 2 * est, 17 - 3 * est, -est]
    se = math.sqrt(3 / 2 * sum(s * s for s in sums)) / 6
    got = st.cluster_t(values, labels)
    assert got["est"] == pytest.approx(est)
    assert (got["clusters"], got["df"]) == (3, 2)
    assert got["se"] == pytest.approx(se, rel=1e-12)
    q = stats.t.ppf(0.975, 2)
    assert (got["lo"], got["hi"]) == pytest.approx((est - q * se, est + q * se), rel=1e-12)
    assert got["p"] == pytest.approx(2 * stats.t.sf(est / se, 2), rel=1e-12)
    # neither the version without G / (G - 1) nor the one summing raw values matches
    assert got["se"] != pytest.approx(math.sqrt(sum(s * s for s in sums)) / 6)
    assert got["se"] != pytest.approx(math.sqrt(3 / 2 * (3 ** 2 + 17 ** 2)) / 6)


def test_item_t_is_the_paired_t():
    values = [0.5, -1, -1 / 3, 0, -0.5, -2 / 3, 1 / 3, -1]
    got = st.item_t(values)
    want = stats.ttest_1samp(values, 0)
    ci = want.confidence_interval(0.95)
    assert got["df"] == len(values) - 1
    assert got["p"] == pytest.approx(want.pvalue, rel=1e-10)
    assert (got["lo"], got["hi"]) == pytest.approx((ci.low, ci.high), rel=1e-10)


def test_one_cluster_and_zero_se_give_no_test():
    one = st.cluster_t([0.1, 0.3], ["a", "a"])
    assert one["est"] == pytest.approx(0.2)
    assert one["se"] is one["lo"] is one["p"] is None
    flat = st.cluster_t([1.0, 1.0, 1.0], ["a", "b", "c"])
    assert flat["se"] == 0 and flat["lo"] == flat["hi"] == 1.0 and flat["p"] is None


def test_cluster_t_rejects_mismatched_input():
    with pytest.raises(ValueError):
        st.cluster_t([1, 2], ["a"])


P = [0.01, 0.04, 0.03, None, 0.04, 0.5, 0.002]


def test_holm_matches_r_p_adjust():
    # p.adjust(c(0.01, 0.04, 0.03, NA, 0.04, 0.5, 0.002), "holm") in R 4.5.3
    want = [0.05, 0.12, 0.12, None, 0.12, 0.5, 0.012]
    got = st.holm(P)
    assert got[3] is None
    assert [g for g in got if g is not None] == pytest.approx([w for w in want if w is not None])


def test_bh_matches_r_p_adjust():
    # p.adjust(c(0.01, 0.04, 0.03, NA, 0.04, 0.5, 0.002), "BH") in R 4.5.3
    want = [0.03, 0.048, 0.048, None, 0.048, 0.5, 0.012]
    got = st.bh(P)
    assert got[3] is None
    assert [g for g in got if g is not None] == pytest.approx([w for w in want if w is not None])


def test_wald_contrast_by_hand():
    est = [1.0, 2.0, -0.5]
    cov = [[0.04, 0.01, 0.0], [0.01, 0.09, -0.02], [0.0, -0.02, 0.16]]
    w = [0.5, 0.5, -1.0]
    # w' S w = 0.25 * 0.04 + 0.25 * 0.09 + 0.16 + 2 * 0.25 * 0.01 + 2 * 0.5 * -1 * -0.02
    var = 0.01 + 0.0225 + 0.16 + 0.005 + 0.02
    got = st.wald_contrast(est, cov, w)
    q = stats.norm.ppf(0.975)
    assert got["est"] == pytest.approx(2.0)
    assert got["se"] == pytest.approx(math.sqrt(var))
    assert (got["lo"], got["hi"]) == pytest.approx((2.0 - q * math.sqrt(var),
                                                    2.0 + q * math.sqrt(var)))


def test_wald_contrast_with_a_diagonal_cov_is_the_independent_se():
    got = st.wald_contrast([1, 1], [[4, 0], [0, 9]], [1, -1])
    assert got["est"] == 0 and got["se"] == pytest.approx(math.sqrt(13))


def test_a_positive_covariance_between_same_sign_weights_raises_the_se():
    flat = st.wald_contrast([1, 1, 1], [[1, 0, 0], [0, 1, 0], [0, 0, 1]], [0.5, 0.5, -1])
    tied = st.wald_contrast([1, 1, 1], [[1, 0.5, 0], [0.5, 1, 0], [0, 0, 1]], [0.5, 0.5, -1])
    assert tied["se"] > flat["se"]


def test_wald_contrast_rejects_mismatched_sizes():
    with pytest.raises(ValueError, match="matching sizes"):
        st.wald_contrast([1, 2], [[1, 0], [0, 1]], [1, 0, -1])
    with pytest.raises(ValueError, match="matching sizes"):
        st.wald_contrast([1, 2], [[1, 0]], [1, -1])


def test_wald_contrast_rejects_a_negative_variance():
    with pytest.raises(ValueError, match="negative variance"):
        st.wald_contrast([1, 1], [[1, 2], [2, 1]], [1, -1])
