"""Live path: Open-Meteo (Google WeatherNext 2 Ensemble) -> the box-stats contract.

Pure functions only; no network. `scripts/fetch_openmeteo_wn2.py` does the HTTP.

Verified against https://open-meteo.com/en/docs/google-weathernext-api on 5 Sep 2026:

  endpoint   https://ensemble-api.open-meteo.com/v1/ensemble
  model      models=google_weathernext2_ensemble
  variable   hourly=geopotential_height_500hPa (pressure levels ARE available for
             ensemble members; units are metres of geopotential HEIGHT)
  members    64 series per location: the bare `geopotential_height_500hPa` (control)
             plus `geopotential_height_500hPa_member01` .. `_member63`
  horizon    forecast_days up to 15 (we ask 11); temporal_resolution=hourly_6 halves
             the payload and still lands on 00 UTC
  points     latitude/longitude accept comma-separated lists; the response is then a
             JSON *list* of per-location objects in the order asked
  runs       no previous-run variables for pressure levels
             (`..._previous_day1` -> HTTP 400), so `jumpiness` cannot be computed
             from this API and is left NaN.

Licence: Open-Meteo data is CC-BY-4.0 and the free API is for non-commercial use
(https://open-meteo.com/en/license). WeatherNext 2 output is Google's, served by
Open-Meteo. This project is a hackathon prototype: non-commercial.

Units: Open-Meteo returns geopotential HEIGHT in m; the WeatherBench 2 archive the
model was trained on stores geopotential in m^2 s^-2. Multiply by g = 9.80665.
"""

from __future__ import annotations

from datetime import datetime, timezone

import numpy as np
import pandas as pd

from pipeline.regions import REGIONS

G = 9.80665
SOURCE = "openmeteo_wn2"
SOURCE_LABEL = "Google WeatherNext 2 Ensemble (Open-Meteo, live)"
VARIABLE = "geopotential_height_500hPa"

BOXSTATS_COLUMNS = [
    "source", "init", "lead_days", "region", "var",
    "ens_mean", "ens_std", "q10", "q25", "q50", "q75", "q90",
    "cluster_gap", "truth", "climo",
]


# --- canonical stat definitions -------------------------------------------------
# COPIED VERBATIM from scripts/extract_region_stats.py, which is CANONICAL. That file
# runs standalone in Colab and must not import the pipeline package, so the definitions
# live in both places; pipeline/tests/test_live.py asserts the two agree exactly.

def cluster_gap(sorted_vals: np.ndarray) -> float:
    """Largest gap between adjacent sorted members within the central 80%, in std units."""
    n = sorted_vals.size
    s = sorted_vals.std()
    if s == 0 or n < 5:
        return 0.0
    lo, hi = int(np.floor(0.1 * n)), int(np.ceil(0.9 * n))
    core = sorted_vals[lo:hi]
    return float(np.diff(core).max() / s)


def member_stats_from_series(values: np.ndarray) -> dict:
    """Box stats for one (region, lead): same definitions as extract_region_stats.member_stats."""
    v = np.sort(np.asarray(values, dtype=float))
    return {
        "ens_mean": float(v.mean()),
        "ens_std": float(v.std(ddof=1)),
        "q10": float(np.quantile(v, 0.10)),
        "q25": float(np.quantile(v, 0.25)),
        "q50": float(np.quantile(v, 0.50)),
        "q75": float(np.quantile(v, 0.75)),
        "q90": float(np.quantile(v, 0.90)),
        "cluster_gap": cluster_gap(v),
    }


# --- payload -> box stats -------------------------------------------------------

def member_keys(hourly: dict, variable: str = VARIABLE) -> list[str]:
    """The control series plus every `_memberNN` series, in a stable order."""
    keys = [k for k in hourly if k == variable or k.startswith(variable + "_member")]
    if not keys:
        raise KeyError(f"no {variable} series in payload (keys: {sorted(hourly)[:6]})")
    return sorted(keys)


def members_at(hourly: dict, valid: pd.Timestamp, variable: str = VARIABLE) -> np.ndarray:
    """Every member's value at `valid`, in metres, with missing members dropped."""
    times = hourly.get("time")
    if not times:
        raise KeyError("payload has no hourly.time")
    stamp = pd.Timestamp(valid).tz_localize(None).strftime("%Y-%m-%dT%H:%M")
    try:
        i = times.index(stamp)
    except ValueError as exc:
        raise KeyError(f"valid time {stamp} not in payload ({times[0]} .. {times[-1]})") from exc
    vals = [hourly[k][i] for k in member_keys(hourly, variable)]
    out = np.array([v for v in vals if v is not None], dtype=float)
    if out.size < 5:
        raise ValueError(f"only {out.size} members at {stamp}; refusing to compute stats")
    return out


def climo_lookup(climo_table: pd.DataFrame, region: str, valid: pd.Timestamp) -> float:
    """ERA5 1990-2019 climatology for this region at the valid dayofyear x hour."""
    m = climo_table[
        (climo_table["region"] == region)
        & (climo_table["dayofyear"] == int(valid.dayofyear))
        & (climo_table["hour"] == int(valid.hour))
    ]
    if m.empty:
        raise KeyError(f"no climatology for {region} doy={valid.dayofyear} hour={valid.hour}")
    return float(m["climo"].iloc[0])


def rows_from_openmeteo(
    payload_by_region: dict[str, dict],
    init: pd.Timestamp,
    leads: list[int],
    climo_table: pd.DataFrame,
    variable: str = VARIABLE,
) -> pd.DataFrame:
    """Turn one Open-Meteo ensemble response into box-stats rows.

    `payload_by_region` maps a region id to that location's response object (the one
    holding `hourly`). Valid time for lead L is init + L days at the init hour.
    `truth` is NaN (nothing has verified yet); `climo` comes from `climo_table`.
    """
    init = pd.Timestamp(init)
    rows: list[dict] = []
    for region, payload in payload_by_region.items():
        hourly = payload.get("hourly", payload)
        for lead in leads:
            valid = init + pd.Timedelta(days=int(lead))
            vals = members_at(hourly, valid, variable) * G  # m -> m^2 s^-2
            rows.append({
                "source": SOURCE,
                "init": init,
                "lead_days": int(lead),
                "region": region,
                "var": "z500",
                **member_stats_from_series(vals),
                "truth": np.nan,
                "climo": climo_lookup(climo_table, region, valid),
            })
    df = pd.DataFrame(rows, columns=BOXSTATS_COLUMNS)
    return df.sort_values(["init", "lead_days", "region"]).reset_index(drop=True)


def region_points() -> tuple[list[str], list[float], list[float]]:
    """Region ids and their centroid lat/lon, in REGIONS order."""
    ids = list(REGIONS)
    lats = [REGIONS[r].centroid[0] for r in ids]
    lons = [REGIONS[r].centroid[1] for r in ids]
    return ids, lats, lons


# --- staleness ------------------------------------------------------------------

def is_stale(fetched_at: str, now: datetime | str | None = None, hours: float = 36.0) -> bool:
    """True when a cached live.json is older than `hours`. Naive stamps are read as UTC."""
    t = pd.Timestamp(fetched_at)
    if t.tzinfo is None:
        t = t.tz_localize("UTC")
    n = pd.Timestamp(now if now is not None else datetime.now(timezone.utc))
    if n.tzinfo is None:
        n = n.tz_localize("UTC")
    return (n - t) > pd.Timedelta(hours=hours)
