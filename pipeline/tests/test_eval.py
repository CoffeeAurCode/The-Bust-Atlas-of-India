import numpy as np
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score

from pipeline.eval import brier, bss, evaluate, pr_auc, reliability_bins, roc_auc


def _data(n=5000, seed=0):
    rng = np.random.default_rng(seed)
    p = rng.beta(1, 8, n)
    y = (rng.random(n) < p).astype(int)
    return y, p


def test_metrics_match_sklearn():
    y, p = _data()
    assert abs(brier(y, p) - brier_score_loss(y, p)) < 1e-9
    assert abs(pr_auc(y, p) - average_precision_score(y, p)) < 1e-9
    assert abs(roc_auc(y, p) - roc_auc_score(y, p)) < 1e-9


def test_bss_perfect_and_reference():
    y, p = _data()
    assert bss(y, y.astype(float), 0.1) == 1.0
    assert bss(y, np.full_like(p, 0.1), 0.1) == 0.0
    assert bss(y, p, p) == 0.0


def test_reliability_bins_sum_to_n():
    y, p = _data()
    bins = reliability_bins(y, p, n=10)
    assert sum(b["n"] for b in bins) == len(y)
    assert len(bins) == 10


def test_evaluate_structure():
    y, p = _data()
    out = evaluate(y, p, np.full_like(p, y.mean()))
    assert set(out) == {"n", "positives", "base_rate", "model", "baseline"}
    assert out["model"]["bss_vs_spread"] > 0  # informative beats constant
