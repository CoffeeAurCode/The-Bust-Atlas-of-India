"""Turn per-feature contributions into a forecaster's note.

Each rule maps a feature to a sentence for the direction that raises bust risk. The
sentence is written the way a duty forecaster would say it, and names the lead day.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from pipeline.features import FEATURES

# feature -> (sentence when contribution is positive, sentence when negative)
RULES: dict[str, tuple[str, str]] = {
    "std": (
        "Ensemble spread at Day {lead} is large: members disagree on the 500 hPa pattern.",
        "Ensemble spread at Day {lead} is small: members broadly agree.",
    ),
    "std_pct_climo": (
        "Today's spread sits in the top {pct}% of what this region sees at Day {lead} in {season}.",
        "Today's spread is ordinary for this region, lead and season.",
    ),
    "std_growth": (
        "Members diverge sharply between Day {lead_prev} and Day {lead}.",
        "Spread grows slowly into Day {lead}.",
    ),
    "std_growth_rel": (
        "Spread jumps by a large fraction between Day {lead_prev} and Day {lead}.",
        "Spread growth into Day {lead} is steady.",
    ),
    "iqr": (
        "The central half of the ensemble is wide at Day {lead}.",
        "The central half of the ensemble is tight at Day {lead}.",
    ),
    "tail": (
        "The ensemble has heavy tails at Day {lead}: a few members show a very different outcome.",
        "The ensemble is compact with no outlying scenarios.",
    ),
    "cluster_gap": (
        "The ensemble has split into two camps at Day {lead}; the mean is in between and may verify with neither.",
        "The ensemble forms a single coherent scenario.",
    ),
    "anom": (
        "The forecast 500 hPa anomaly is unusually strong for the season.",
        "The forecast pattern is close to climatology.",
    ),
    "jumpiness": (
        "The forecast valid on this day has moved since yesterday's run: successive runs are not converging.",
        "Yesterday's run agreed with today's for this valid time.",
    ),
    "jump_rel": (
        "Yesterday's run differed from today's by more than the spread: the run-to-run change is larger than the ensemble's own uncertainty.",
        "Run-to-run change is small relative to the spread.",
    ),
    "base_rate": (
        "This region busts more often than average at Day {lead} in {season}.",
        "This region rarely busts at Day {lead} in {season}.",
    ),
    "lead_days": ("Lead time itself raises the risk.", "Short lead time keeps the risk low."),
    "season_code": ("Season raises the risk.", "Season lowers the risk."),
    "region_code": ("Region raises the risk.", "Region lowers the risk."),
}

SEASON_WORDS = {"DJF": "winter", "MAM": "the pre-monsoon", "JJAS": "the monsoon", "ON": "the post-monsoon"}


def sentence(feature: str, contribution: float, row: pd.Series) -> str:
    pos, neg = RULES[feature]
    tpl = pos if contribution > 0 else neg
    lead = int(row["lead_days"])
    pct = int(round((1 - float(row.get("std_pct_climo", 0.5))) * 100))
    return tpl.format(
        lead=lead,
        lead_prev=max(lead - 1, 1),
        season=SEASON_WORDS.get(str(row.get("season", "")), "this season"),
        pct=max(pct, 1),
    )


def drivers(contribs: np.ndarray, rows: pd.DataFrame, k: int = 3) -> list[list[dict]]:
    """Top-k contributions per row, positive first (what raises risk), then negative."""
    out: list[list[dict]] = []
    rows = rows.reset_index(drop=True)
    for i in range(len(rows)):
        c = contribs[i]
        order = np.argsort(-c)  # most positive first
        chosen = [j for j in order if c[j] > 0][:k]
        if len(chosen) < k:  # pad with the strongest negatives so the note is never empty
            chosen += [j for j in np.argsort(c) if c[j] <= 0][: k - len(chosen)]
        out.append([
            {
                "feature": FEATURES[j],
                "contribution": round(float(c[j]), 4),
                "sentence": sentence(FEATURES[j], float(c[j]), rows.iloc[i]),
            }
            for j in chosen
        ])
    return out
