"""Live path: Open-Meteo payload -> box-stats rows.

The fixture is a real response from
https://ensemble-api.open-meteo.com/v1/ensemble?...&models=google_weathernext2_ensemble
fetched 5 Sep 2026, trimmed to 2 regions x 6 members x 3 days to stay small.
"""

from __future__ import annotations

import importlib.util
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from pipeline.live import (
    BOXSTATS_COLUMNS,
    G,
    is_stale,
    member_stats_from_series,
    rows_from_openmeteo,
)

FIXTURE = Path(__file__).parent / "fixtures" / "openmeteo_wn2_sample.json"
SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "extract_region_stats.py"


def _canonical():
    """Import the canonical stat functions straight from the Colab extract script."""
    spec = importlib.util.spec_from_file_location("_extract_region_stats", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def payload():
    d = json.loads(FIXTURE.read_text(encoding="utf-8"))
    return dict(zip(d["regions"], d["locations"]))


@pytest.fixture(scope="module")
def init(payload):
    first = next(iter(payload.values()))["hourly"]["time"][0]
    return pd.Timestamp(first)


@pytest.fixture(scope="module")
def climo(payload, init):
    regions = list(payload)
    rows = []
    for doy in range(1, 367):
        for hour in (0, 6, 12, 18):
            for i, r in enumerate(regions):
                rows.append({"dayofyear": doy, "hour": hour, "region": r,
                             "climo": 55000.0 + 100 * i})
    return pd.DataFrame(rows)


@pytest.fixture(scope="module")
def rows(payload, init, climo):
    return rows_from_openmeteo(payload, init, [1, 2], climo)


def test_columns_are_exactly_the_box_stats_contract(rows):
    assert list(rows.columns) == BOXSTATS_COLUMNS
    assert len(rows) == 4  # 2 regions x 2 leads
    assert set(rows["region"]) == {"western_himalaya", "north_west"}
    assert set(rows["lead_days"]) == {1, 2}
    assert (rows["source"] == "openmeteo_wn2").all()
    assert (rows["var"] == "z500").all()
    assert rows["truth"].isna().all()
    assert rows["climo"].notna().all()


def test_spread_is_positive_and_quantiles_ordered(rows):
    assert (rows["ens_std"] > 0).all()
    assert (rows["q10"] <= rows["q25"]).all()
    assert (rows["q25"] <= rows["q50"]).all()
    assert (rows["q50"] <= rows["q75"]).all()
    assert (rows["q75"] <= rows["q90"]).all()
    assert (rows["cluster_gap"] >= 0).all()


def test_units_are_converted_from_height_to_geopotential(rows):
    # Open-Meteo gives metres; the archive the model was trained on is m^2 s^-2.
    assert abs(5700.0 * G - 55897.9) < 0.5
    assert (rows["ens_mean"] > 40_000).all()
    assert (rows["ens_mean"] < 70_000).all()


def test_valid_time_is_init_plus_lead_days(payload, init, climo):
    hourly = next(iter(payload.values()))["hourly"]
    assert (init + pd.Timedelta(days=2)).strftime("%Y-%m-%dT%H:%M") in hourly["time"]
    with pytest.raises(KeyError):
        rows_from_openmeteo(payload, init, [9], climo)  # beyond the fixture's window


def test_stats_match_the_canonical_extract_script():
    mod = _canonical()
    rng = np.random.default_rng(0)
    for vals in (rng.normal(55000, 120, 64),
                 np.concatenate([rng.normal(54800, 40, 32), rng.normal(55400, 40, 32)]),
                 np.full(20, 55000.0)):
        assert member_stats_from_series(vals) == mod.member_stats(vals)
        s = np.sort(vals)
        assert mod.cluster_gap(s) == pytest.approx(member_stats_from_series(vals)["cluster_gap"])


def test_cluster_gap_of_rows_matches_canonical(payload, init, rows):
    from pipeline.live import members_at

    mod = _canonical()
    for _, row in rows.iterrows():
        hourly = payload[row["region"]]["hourly"]
        vals = members_at(hourly, init + pd.Timedelta(days=int(row["lead_days"]))) * G
        assert mod.cluster_gap(np.sort(vals)) == pytest.approx(row["cluster_gap"])


def test_is_stale():
    now = datetime(2026, 9, 5, 12, 0, tzinfo=timezone.utc)
    fresh = (now - timedelta(hours=5)).isoformat()
    old = (now - timedelta(hours=40)).isoformat()
    assert not is_stale(fresh, now, 36)
    assert is_stale(old, now, 36)
    assert not is_stale(old, now, 48)
    assert not is_stale("2026-09-05T07:00:00", now, 36)  # naive stamps read as UTC


def test_live_schema_accepts_a_minimal_document():
    from pipeline.schemas import Live

    doc = Live(
        fetched_at="2026-09-05T06:00:00+00:00", init="2026-09-05T00",
        source="openmeteo_wn2", source_label="Google WeatherNext 2 Ensemble", members=64,
        regions={"central": {"leads": [{
            "lead": 1, "prob": 0.03, "baseline_prob": 0.02, "band": "low", "flag": False,
            "std": 120.0, "std_pct_climo": 0.4, "cluster_gap": 0.25, "jumpiness": None,
            "drivers": [{"feature": "std", "contribution": -0.4}], "outcome": None,
        }]}},
    )
    assert doc.stale_after_hours == 36
    assert doc.regions["central"].leads[0].outcome is None
