"""Probability calibration shared by the model and the spread baseline.

Isotonic regression, plus an infinitesimal strictly-increasing term in the raw score.

Isotonic alone is the right shape. The bust rate rises convexly in the top decile of the
score, and a single-slope logistic (Platt) cannot follow it: fitted on this data Platt
reported 7.7% for a decile that busts at 15.3%, which would have put every region below
the 15% "unreliable" flag and left that part of the product permanently empty.

Isotonic alone also has a defect: it is a step function, so it maps thousands of distinct
scores onto a few dozen values. Those ties are invisible in a Brier score but they cost
0.03 of PR-AUC, because tied predictions cannot be ranked. Adding EPS * raw restores a
strict ordering while moving any probability by at most 1e-6. It is a function of the row
alone, so a single forecast calibrates identically whether scored on its own or in a
batch.

Both the model and the baseline use this, so the headline comparison is calibrator-fair.
"""

from __future__ import annotations

import numpy as np
from sklearn.isotonic import IsotonicRegression

EPS = 1e-6
"""Tie-break size. Small enough to be invisible against a probability quoted in percent,
large enough to survive float64 arithmetic on scores of order 0.1."""


class MonotoneCalibrator:
    """Maps a raw score in (0, 1) to a calibrated probability. Strictly increasing."""

    def __init__(self) -> None:
        self.iso: IsotonicRegression | None = None

    def fit(self, raw: np.ndarray, y: np.ndarray) -> "MonotoneCalibrator":
        self.iso = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0)
        self.iso.fit(np.asarray(raw, dtype=float), np.asarray(y, dtype=float))
        return self

    def predict(self, raw: np.ndarray) -> np.ndarray:
        assert self.iso is not None, "call fit first"
        raw = np.asarray(raw, dtype=float)
        return np.clip(self.iso.predict(raw) + EPS * raw, 0.0, 1.0)
