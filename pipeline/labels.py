"""Bust definition and labelling.

A forecast for (region, lead, season) is a bust when its anomaly error exceeds the
p-th percentile (default 95) of the error distribution for that same cell, with the
percentile computed on the TRAINING years only. Relative, lead-conditioned,
season-conditioned, region-specific, data-driven.
"""

from __future__ import annotations

import pandas as pd

from pipeline.seasons import season_series

KEY = ["region", "lead_days", "season"]


def add_error(df: pd.DataFrame) -> pd.DataFrame:
    """Anomaly error of the ensemble mean, |(mean - climo) - (truth - climo)| = |mean - truth|.

    Written out in anomaly form so the definition matches the slide; numerically the
    climatology cancels. Also adds `season` and `year`.
    """
    out = df.copy()
    out["season"] = season_series(out["init"])
    out["year"] = pd.to_datetime(out["init"]).dt.year
    out["error"] = ((out["ens_mean"] - out["climo"]) - (out["truth"] - out["climo"])).abs()
    return out


def fit_thresholds(df_train: pd.DataFrame, pct: float = 95.0) -> pd.DataFrame:
    """Per region x lead x season: error percentiles from training rows only."""
    g = df_train.groupby(KEY, observed=True)["error"]
    thr = pd.DataFrame({
        "err_p50": g.quantile(0.50),
        "err_p90": g.quantile(0.90),
        "err_p95": g.quantile(0.95),
        "bust_threshold": g.quantile(pct / 100.0),
        "n_train": g.size(),
    }).reset_index()
    thr.attrs["pct"] = pct
    return thr


def apply_labels(df: pd.DataFrame, thresholds: pd.DataFrame) -> pd.DataFrame:
    out = df.merge(thresholds[KEY + ["bust_threshold"]], on=KEY, how="left", validate="m:1")
    if out["bust_threshold"].isna().any():
        missing = out.loc[out["bust_threshold"].isna(), KEY].drop_duplicates()
        raise ValueError(f"no threshold for cells:\n{missing}")
    out["bust"] = out["error"] > out["bust_threshold"]
    return out


def label(df: pd.DataFrame, train_years: list[int], pct: float = 95.0) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Convenience: add_error -> fit on train_years -> apply to everything."""
    d = add_error(df)
    thr = fit_thresholds(d[d["year"].isin(train_years)], pct=pct)
    return apply_labels(d, thr), thr
