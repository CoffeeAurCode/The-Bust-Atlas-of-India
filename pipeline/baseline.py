"""Spread-only baseline: what a forecaster already has.

Score = percentile of today's spread within the training-year spread distribution for
the same region x lead x season, mapped to a bust probability by the same
calibrator the model uses (see pipeline.calibrate). Beating this is
the whole scientific claim, so the two must be calibrated identically.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from pipeline.calibrate import MonotoneCalibrator


class SpreadBaseline:
    def __init__(self) -> None:
        self.cal: MonotoneCalibrator | None = None

    @staticmethod
    def raw_score(df_feat: pd.DataFrame) -> np.ndarray:
        """Spread percentile, rescaled to (0, 1) so the calibrator can take its logit."""
        return df_feat["std_pct_climo"].to_numpy() / 100.0

    def fit(self, df_cal_feat: pd.DataFrame) -> "SpreadBaseline":
        self.cal = MonotoneCalibrator().fit(
            self.raw_score(df_cal_feat), df_cal_feat["bust"].astype(int).to_numpy()
        )
        return self

    def predict_proba(self, df_feat: pd.DataFrame) -> np.ndarray:
        assert self.cal is not None, "call fit first"
        return self.cal.predict(self.raw_score(df_feat))
