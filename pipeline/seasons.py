"""Indian meteorological seasons, as used by IMD."""

from __future__ import annotations

import numpy as np
import pandas as pd

SEASONS: list[str] = ["DJF", "MAM", "JJAS", "ON"]
SEASON_CODES: dict[str, int] = {s: i for i, s in enumerate(SEASONS)}
SEASON_LABELS: dict[str, str] = {
    "DJF": "Winter (Dec–Feb)",
    "MAM": "Pre-monsoon (Mar–May)",
    "JJAS": "Monsoon (Jun–Sep)",
    "ON": "Post-monsoon (Oct–Nov)",
}

_MONTH_TO_SEASON = {
    12: "DJF", 1: "DJF", 2: "DJF",
    3: "MAM", 4: "MAM", 5: "MAM",
    6: "JJAS", 7: "JJAS", 8: "JJAS", 9: "JJAS",
    10: "ON", 11: "ON",
}


def season_of(ts) -> str:
    return _MONTH_TO_SEASON[pd.Timestamp(ts).month]


def season_series(s: pd.Series) -> pd.Series:
    months = pd.to_datetime(s).dt.month
    return months.map(_MONTH_TO_SEASON).astype("string")


def season_code_series(s: pd.Series) -> np.ndarray:
    return season_series(s).map(SEASON_CODES).to_numpy(dtype=int)
