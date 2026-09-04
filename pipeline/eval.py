"""Probabilistic verification. Never accuracy."""

from __future__ import annotations

import numpy as np
from sklearn.metrics import average_precision_score, roc_auc_score


def brier(y: np.ndarray, p: np.ndarray) -> float:
    y = np.asarray(y, dtype=float)
    p = np.asarray(p, dtype=float)
    return float(np.mean((p - y) ** 2))


def bss(y: np.ndarray, p: np.ndarray, p_ref: np.ndarray | float) -> float:
    """Brier skill score of p relative to a reference forecast (array or constant)."""
    ref = np.broadcast_to(np.asarray(p_ref, dtype=float), np.shape(y))
    b_ref = brier(y, ref)
    if b_ref == 0:
        return 0.0
    return float(1.0 - brier(y, p) / b_ref)


def pr_auc(y, p) -> float:
    return float(average_precision_score(y, p))


def roc_auc(y, p) -> float:
    return float(roc_auc_score(y, p))


def reliability_bins(y, p, n: int = 10) -> list[dict]:
    y = np.asarray(y, dtype=float)
    p = np.asarray(p, dtype=float)
    edges = np.linspace(0, 1, n + 1)
    idx = np.clip(np.digitize(p, edges[1:-1], right=False), 0, n - 1)
    out = []
    for b in range(n):
        m = idx == b
        out.append({
            "bin": b,
            "lo": float(edges[b]),
            "hi": float(edges[b + 1]),
            "n": int(m.sum()),
            "mean_forecast": float(p[m].mean()) if m.any() else None,
            "observed_freq": float(y[m].mean()) if m.any() else None,
        })
    return out


def pr_curve(y, p, n: int = 50) -> list[dict]:
    """Precision/recall at n thresholds, for plotting."""
    y = np.asarray(y, dtype=bool)
    p = np.asarray(p, dtype=float)
    out = []
    for t in np.linspace(0, 1, n + 1):
        pred = p >= t
        tp = int((pred & y).sum())
        fp = int((pred & ~y).sum())
        fn = int((~pred & y).sum())
        out.append({
            "threshold": float(t),
            "precision": tp / (tp + fp) if tp + fp else None,
            "recall": tp / (tp + fn) if tp + fn else None,
        })
    return out


def evaluate(y, p, p_baseline, climo_rate: float | None = None) -> dict:
    y = np.asarray(y, dtype=float)
    rate = float(y.mean()) if climo_rate is None else climo_rate
    return {
        "n": int(len(y)),
        "positives": int(y.sum()),
        "base_rate": rate,
        "model": {
            "brier": brier(y, p),
            "bss_vs_climatology": bss(y, p, rate),
            "bss_vs_spread": bss(y, p, p_baseline),
            "pr_auc": pr_auc(y, p),
            "roc_auc": roc_auc(y, p),
            "reliability": reliability_bins(y, p),
            "pr_curve": pr_curve(y, p),
        },
        "baseline": {
            "brier": brier(y, p_baseline),
            "bss_vs_climatology": bss(y, p_baseline, rate),
            "pr_auc": pr_auc(y, p_baseline),
            "roc_auc": roc_auc(y, p_baseline),
            "reliability": reliability_bins(y, p_baseline),
            "pr_curve": pr_curve(y, p_baseline),
        },
    }
