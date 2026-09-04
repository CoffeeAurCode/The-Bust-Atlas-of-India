"""Issue-time features for bust prediction.

LEAKAGE RULE: every feature for a row with init time t is a function only of rows with
init <= t (and of training-year statistics). test_features.py::test_no_leakage enforces
this by recomputing on a truncated frame.

Feature | inputs | why it is issue-time-safe
--------|--------|--------------------------
std            | this row's ens_std                              | member spread at issue
std_pct_climo  | ens_std vs spread distribution of the TRAIN years for this cell | Tier 0, climatological context
std_growth     | ens_std at lead L minus at lead L-1, same init  | same forecast run
std_growth_rel | std_growth / std at L-1                          | same forecast run
iqr            | q75 - q25, this row                              | same run
tail           | (q90 - q10) / std, this row                      | same run
cluster_gap    | this row                                         | same run
anom           | (ens_mean - climo), this row                     | forecast anomaly, no truth used
jumpiness      | ens_mean(init t, lead L) - ens_mean(init t-24h, lead L+1) | previous run, same valid time
jump_rel       | |jumpiness| / std                                | as above
base_rate      | bust frequency for this cell in TRAIN years      | climatology of the label
lead_days, season_code, region_code | metadata                   | -
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from pipeline.labels import KEY
from pipeline.regions import REGION_CODES
from pipeline.seasons import SEASON_CODES, season_series

FEATURES = [
    "std", "std_pct_climo", "std_growth", "std_growth_rel", "iqr", "tail", "cluster_gap",
    "anom", "jumpiness", "jump_rel", "base_rate", "lead_days", "season_code", "region_code",
]


def fit_feature_stats(df_train_labelled: pd.DataFrame) -> dict:
    """Training-year statistics needed by Tier 0 features."""
    g = df_train_labelled.groupby(KEY, observed=True)
    spread_q = g["ens_std"].quantile([0.1, 0.25, 0.5, 0.75, 0.9]).unstack()
    spread_q.columns = [f"sq{int(c * 100)}" for c in spread_q.columns]
    base = g["bust"].mean().rename("base_rate")
    return {"spread_quantiles": spread_q.reset_index(), "base_rate": base.reset_index()}


def _percentile_of(x: pd.Series, qs: pd.DataFrame) -> pd.Series:
    """Piecewise-linear percentile (0..1) of x within the 5 stored quantiles."""
    probs = np.array([0.1, 0.25, 0.5, 0.75, 0.9])
    cols = ["sq10", "sq25", "sq50", "sq75", "sq90"]
    out = np.empty(len(x))
    vals = qs[cols].to_numpy()
    xv = x.to_numpy()
    for i in range(len(xv)):
        out[i] = np.interp(xv[i], vals[i], probs, left=0.0, right=1.0)
    return pd.Series(out, index=x.index)


def build_features(df: pd.DataFrame, stats: dict) -> pd.DataFrame:
    """Return df with FEATURES columns added. df must have season (from labels.add_error)."""
    d = df.copy()
    if "season" not in d:
        d["season"] = season_series(d["init"])
    d = d.sort_values(["region", "init", "lead_days"]).reset_index(drop=True)

    d["std"] = d["ens_std"]
    d["iqr"] = d["q75"] - d["q25"]
    d["tail"] = (d["q90"] - d["q10"]) / d["ens_std"]
    d["anom"] = d["ens_mean"] - d["climo"]

    # Spread growth across leads within the same init/region.
    prev = d.groupby(["region", "init"], observed=True)["ens_std"].shift(1)
    d["std_growth"] = d["ens_std"] - prev
    d["std_growth_rel"] = d["std_growth"] / prev
    d.loc[d["lead_days"] == d["lead_days"].min(), ["std_growth", "std_growth_rel"]] = 0.0

    # Jumpiness: compare with the run initialised 24 h EARLIER at lead L+1 (same valid time).
    # Row (t, L) looks up (t - 1 day, L + 1). NaN at the first init and at the last lead;
    # LightGBM handles NaN natively. Looking forward here would be a leak (test_no_leakage).
    key = d[["region", "init", "lead_days"]].copy()
    key["init"] = key["init"] - pd.Timedelta(days=1)
    key["lead_days"] = key["lead_days"] + 1
    prev_run = d[["region", "init", "lead_days", "ens_mean"]].rename(columns={"ens_mean": "prev_mean"})
    merged = key.merge(prev_run, on=["region", "init", "lead_days"], how="left")
    d["jumpiness"] = (d["ens_mean"].to_numpy() - merged["prev_mean"].to_numpy())
    d["jump_rel"] = d["jumpiness"].abs() / d["ens_std"]

    # Tier 0: climatological context from training years.
    d = d.merge(stats["spread_quantiles"], on=KEY, how="left", validate="m:1")
    d = d.merge(stats["base_rate"], on=KEY, how="left", validate="m:1")
    d["std_pct_climo"] = _percentile_of(d["ens_std"], d)
    d = d.drop(columns=["sq10", "sq25", "sq50", "sq75", "sq90"])

    d["season_code"] = d["season"].map(SEASON_CODES).astype(int)
    d["region_code"] = d["region"].map(REGION_CODES).astype(int)
    return d
