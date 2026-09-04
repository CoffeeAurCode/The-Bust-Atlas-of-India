"""Spread-only baseline: what a forecaster already has.

Score = percentile of today's spread within the training-year spread distribution for
the same region x lead x season, mapped to a bust probability by isotonic regression on
the calibration years. Beating this is the whole scientific claim.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.isotonic import IsotonicRegression


class SpreadBaseline:
    def __init__(self) -> None:
        self.iso: IsotonicRegression | None = None

    @staticmethod
    def raw_score(df_feat: pd.DataFrame) -> np.ndarray:
        return df_feat["std_pct_climo"].to_numpy()

    def fit(self, df_cal_feat: pd.DataFrame) -> "SpreadBaseline":
        self.iso = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0)
        self.iso.fit(self.raw_score(df_cal_feat), df_cal_feat["bust"].astype(float).to_numpy())
        return self

    def predict_proba(self, df_feat: pd.DataFrame) -> np.ndarray:
        assert self.iso is not None, "call fit first"
        return self.iso.predict(self.raw_score(df_feat))
