"""Live path: pull today's Google WeatherNext 2 ensemble from Open-Meteo, score it with
the trained model, and write frontend/public/data/live.json.

    .venv\\Scripts\\python scripts\\fetch_openmeteo_wn2.py
    .venv\\Scripts\\python scripts\\fetch_openmeteo_wn2.py --dry-run   # writes to a temp file

One HTTP call: all 10 region centroids as comma-separated lat/lon lists, 64 members of
500 hPa geopotential height, 6-hourly, 11 forecast days. Endpoint and member naming are
documented (and were verified live) in pipeline/live.py. No API key. Open-Meteo's free
tier is non-commercial (https://open-meteo.com/en/license); this is a hackathon prototype.

Depends on artifacts written by scripts/run_pipeline.py and scripts/export_climo_table.py:
    data/artifacts/model.pkl                 trained LightGBM + isotonic
    data/artifacts/feature_stats.pkl         Tier-0 training statistics (fit_feature_stats)
    data/artifacts/climo_z500_boxes.parquet  ERA5 climatology per region x doy x hour
    data/artifacts/baseline.pkl              optional; baseline_prob is 0.0 without it

On ANY failure this exits non-zero and leaves an existing live.json untouched: the
frontend then keeps showing the last cached run with its "cached" badge.
"""

from __future__ import annotations

import argparse
import json
import pickle
import sys
import tempfile
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pipeline import live as live_mod  # noqa: E402
from pipeline import schemas  # noqa: E402
from pipeline.explain import drivers  # noqa: E402
from pipeline.features import build_features  # noqa: E402
from pipeline.model import BustModel  # noqa: E402

ENDPOINT = "https://ensemble-api.open-meteo.com/v1/ensemble"
MODEL_ID = "google_weathernext2_ensemble"
LEADS = list(range(1, 11))
FORECAST_DAYS = 11  # lead 10 needs day 11's 00 UTC step
BANDS = {"low": 0.0, "moderate": 0.05, "high": 0.15, "severe": 0.30}
FLAG_THRESHOLD = 0.15


class LiveError(RuntimeError):
    pass


def band_of(p: float, bands: dict[str, float]) -> str:
    b = "low"
    for name, lo in bands.items():
        if p >= lo:
            b = name
    return b


def build_url(lats: list[float], lons: list[float], forecast_days: int) -> str:
    q = [
        f"latitude={','.join(f'{v:g}' for v in lats)}",
        f"longitude={','.join(f'{v:g}' for v in lons)}",
        f"models={MODEL_ID}",
        f"hourly={live_mod.VARIABLE}",
        "temporal_resolution=hourly_6",
        f"forecast_days={forecast_days}",
        "timezone=GMT",
    ]
    return f"{ENDPOINT}?{'&'.join(q)}"


def fetch(url: str, timeout: float = 60.0) -> list[dict]:
    req = urllib.request.Request(url, headers={"User-Agent": "vishwas-bust-atlas/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310 (fixed https host)
        payload = json.loads(r.read().decode("utf-8"))
    if isinstance(payload, dict):
        if payload.get("error"):
            raise LiveError(f"Open-Meteo error: {payload.get('reason')}")
        payload = [payload]
    if not isinstance(payload, list) or not payload:
        raise LiveError("unexpected Open-Meteo response shape (expected a list of locations)")
    return payload


def load_artifacts(art: Path) -> tuple[BustModel, dict, pd.DataFrame, object | None]:
    model_path = art / "model.pkl"
    stats_path = art / "feature_stats.pkl"
    climo_path = art / "climo_z500_boxes.parquet"
    if not model_path.exists():
        raise LiveError(f"missing {model_path}. Run scripts/run_pipeline.py first.")
    if not stats_path.exists():
        raise LiveError(
            f"missing {stats_path}. It holds the Tier-0 training statistics returned by "
            "pipeline.features.fit_feature_stats; rerun scripts/run_pipeline.py to write it."
        )
    if not climo_path.exists():
        raise LiveError(f"missing {climo_path}. Run scripts/export_climo_table.py once.")
    model = BustModel.load(model_path)
    with open(stats_path, "rb") as f:
        stats = pickle.load(f)
    climo = pd.read_parquet(climo_path)
    base = None
    bpath = art / "baseline.pkl"
    if bpath.exists():
        with open(bpath, "rb") as f:
            base = pickle.load(f)
    return model, stats, climo, base


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="frontend/public/data/live.json")
    ap.add_argument("--artifacts", default="data/artifacts")
    ap.add_argument("--dry-run", action="store_true", help="write to a temp file instead")
    ap.add_argument("--save-payload", default="", help="debug: dump the raw response here")
    ap.add_argument("--timeout", type=float, default=60.0)
    args = ap.parse_args()

    art = ROOT / args.artifacts
    try:
        model, stats, climo, base = load_artifacts(art)

        ids, lats, lons = live_mod.region_points()
        url = build_url(lats, lons, FORECAST_DAYS)
        print(f"[fetch] {url}")
        payload = fetch(url, args.timeout)
        if len(payload) != len(ids):
            raise LiveError(f"asked for {len(ids)} points, got {len(payload)}")
        if args.save_payload:
            Path(args.save_payload).write_text(json.dumps(payload), encoding="utf-8")

        by_region = dict(zip(ids, payload))
        first = by_region[ids[0]]["hourly"]["time"][0]
        init = pd.Timestamp(first)  # start of the forecast window = today's 00 UTC run
        n_members = len(live_mod.member_keys(by_region[ids[0]]["hourly"]))
        print(f"[run] init {init} UTC, {n_members} members, {len(ids)} regions")

        rows = live_mod.rows_from_openmeteo(by_region, init, LEADS, climo)
        rows["year"] = init.year
        feat = build_features(rows, stats)
        # jumpiness needs the run initialised 24 h earlier at lead+1; Open-Meteo serves no
        # previous run for pressure-level ensemble variables (`_previous_day1` -> HTTP 400),
        # so jumpiness/jump_rel stay NaN. LightGBM handles NaN natively.
        feat["p_model"] = model.predict_proba(feat)
        feat["p_base"] = base.predict_proba(feat) if base is not None else 0.0
        feat["drivers"] = drivers(model.contributions(feat), feat, k=3)

        meta_path = ROOT / "frontend/public/data/meta.json"
        bands, flag = BANDS, FLAG_THRESHOLD
        if meta_path.exists():
            m = json.loads(meta_path.read_text(encoding="utf-8"))
            bands = m.get("bands", BANDS)
            flag = float(m.get("flag_threshold", FLAG_THRESHOLD))

        regions: dict[str, dict] = {}
        for r, g in feat.sort_values(["region", "lead_days"]).groupby("region"):
            leads = []
            for _, row in g.iterrows():
                p = float(row.p_model)
                leads.append({
                    "lead": int(row.lead_days), "prob": round(p, 4),
                    "baseline_prob": round(float(row.p_base), 4),
                    "band": band_of(p, bands), "flag": bool(p >= flag),
                    "std": round(float(row["std"]), 1),
                    "std_pct_climo": round(float(row.std_pct_climo), 2),
                    "cluster_gap": round(float(row.cluster_gap), 2),
                    "jumpiness": None if pd.isna(row.jumpiness) else round(float(row.jumpiness), 1),
                    "drivers": [{"feature": d["feature"], "contribution": d["contribution"]}
                                for d in row.drivers],
                    "outcome": None,
                })
            regions[str(r)] = {"leads": leads}

        doc = schemas.Live(
            fetched_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            init=init.strftime("%Y-%m-%dT%H"),
            source=live_mod.SOURCE,
            source_label=live_mod.SOURCE_LABEL,
            members=n_members,
            regions=regions,
        )
        text = doc.model_dump_json()
    except Exception as exc:  # noqa: BLE001 - the whole point is to never half-write
        print(f"[fail] {type(exc).__name__}: {exc}", file=sys.stderr)
        print("[fail] live.json left untouched; the app keeps the cached run.", file=sys.stderr)
        return 1

    if args.dry_run:
        out = Path(tempfile.gettempdir()) / "live.json"
    else:
        out = ROOT / args.out
        out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    print(f"[done] {out} ({out.stat().st_size / 1e3:.0f} KB) init={doc.init} members={doc.members}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
