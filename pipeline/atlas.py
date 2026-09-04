"""The Bust Atlas of India: historical bust climatology per region x lead x season."""

from __future__ import annotations

import pandas as pd

from pipeline.labels import KEY
from pipeline.regions import REGIONS
from pipeline.seasons import SEASONS


def build_atlas(df: pd.DataFrame, worst_k: int = 5) -> pd.DataFrame:
    """One row per region x lead x season (10 x 10 x 4 = 400 on the full design).

    Requires the labelled frame (columns from labels.apply_labels).
    """
    g = df.groupby(KEY, observed=True)
    atlas = pd.DataFrame({
        "n": g.size(),
        "bust_rate": g["bust"].mean(),
        "err_p50": g["error"].quantile(0.50),
        "err_p90": g["error"].quantile(0.90),
        "err_p95": g["error"].quantile(0.95),
        "err_max": g["error"].max(),
        "spread_p50": g["ens_std"].quantile(0.50),
        "spread_p95": g["ens_std"].quantile(0.95),
        "spread_skill": g["ens_std"].median() / g["error"].median(),
    }).reset_index()

    worst = (
        df.sort_values("error", ascending=False)
        .groupby(KEY, observed=True)
        .head(worst_k)
        .groupby(KEY, observed=True)
        .apply(lambda x: [
            {"init": pd.Timestamp(i).strftime("%Y-%m-%d %HZ"), "error": round(float(e), 1)}
            for i, e in zip(x["init"], x["error"])
        ], include_groups=False)
        .rename("worst_events")
        .reset_index()
    )
    atlas = atlas.merge(worst, on=KEY, how="left")

    # Stable ordering: region order, lead, season order.
    atlas["_r"] = atlas["region"].map({r: i for i, r in enumerate(REGIONS)})
    atlas["_s"] = atlas["season"].map({s: i for i, s in enumerate(SEASONS)})
    atlas = atlas.sort_values(["_r", "lead_days", "_s"]).drop(columns=["_r", "_s"]).reset_index(drop=True)
    return atlas


def national_summary(df: pd.DataFrame) -> pd.DataFrame:
    """Bust rate and error percentiles by lead x season across all regions."""
    g = df.groupby(["lead_days", "season"], observed=True)
    return pd.DataFrame({
        "n": g.size(),
        "bust_rate": g["bust"].mean(),
        "err_p50": g["error"].quantile(0.50),
        "err_p95": g["error"].quantile(0.95),
    }).reset_index()
