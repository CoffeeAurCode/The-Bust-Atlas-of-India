"""End-to-end: box-stats Parquet -> labels -> Bust Atlas -> features -> baseline -> model
-> evaluation -> explanations -> frontend JSON.

    python scripts/run_pipeline.py --input data/cache/ifs_ens_z500_boxstats.parquet \
        --train 2020 --cal 2021 --test 2022 --out frontend/public/data

Prints the baseline-vs-model table; copy it into DEVLOG.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pipeline import schemas  # noqa: E402
from pipeline.atlas import build_atlas, national_summary  # noqa: E402
from pipeline.baseline import SpreadBaseline  # noqa: E402
from pipeline.eval import evaluate, pr_auc, roc_auc, brier, bss  # noqa: E402
from pipeline.explain import RULES, SEASON_WORDS, drivers  # noqa: E402
from pipeline.features import build_features, fit_feature_stats  # noqa: E402
from pipeline.labels import label  # noqa: E402
from pipeline.model import BustModel  # noqa: E402
from pipeline.regions import REGIONS, STATE_TO_REGION  # noqa: E402
from pipeline.seasons import SEASON_LABELS, SEASONS  # noqa: E402

BUST_DEFINITION = (
    "For a region R, variable V and lead time L, a forecast initialised at time t is a bust "
    "if its error exceeds the 95th percentile of the error distribution for that same region, "
    "variable, lead time and season, computed on training years only."
)
BANDS = {"low": 0.0, "moderate": 0.05, "high": 0.15, "severe": 0.30}
FLAG_THRESHOLD = 0.15
SOURCE_LABELS = {
    "ifs_ens": ("ECMWF IFS ENS (WeatherBench 2 archive)", 50),
    "fgn": ("Google WeatherNext 2 (WeatherBench 2 archive)", 64),
    "synthetic": ("Synthetic data, not real", 50),
}


def band_of(p: float) -> str:
    b = "low"
    for name, lo in BANDS.items():
        if p >= lo:
            b = name
    return b


def init_key(ts: pd.Timestamp) -> str:
    return pd.Timestamp(ts).strftime("%Y-%m-%dT%H")


def git_sha() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception:
        return "unknown"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--train", nargs="+", type=int, default=[2020])
    ap.add_argument("--cal", nargs="+", type=int, default=[2021])
    ap.add_argument("--test", nargs="+", type=int, default=[2022])
    ap.add_argument("--pct", type=float, default=95.0)
    ap.add_argument("--out", default="frontend/public/data")
    ap.add_argument("--artifacts", default="data/artifacts")
    ap.add_argument("--rounds", type=int, default=400)
    args = ap.parse_args()

    out = ROOT / args.out
    art = ROOT / args.artifacts
    out.mkdir(parents=True, exist_ok=True)
    art.mkdir(parents=True, exist_ok=True)
    pred_dir = out / "predictions"
    if pred_dir.exists():
        shutil.rmtree(pred_dir)
    pred_dir.mkdir()

    df = pd.read_parquet(args.input)
    source = str(df.source.iloc[0])
    source_label, members = SOURCE_LABELS.get(source, (source, 0))
    train_years = args.train
    fit_years = args.train + args.cal  # thresholds and Tier-0 stats may use train+cal (all pre-test)

    # 1. labels
    labelled, thresholds = label(df, train_years=fit_years, pct=args.pct)
    pos = labelled[labelled.year.isin(fit_years)].bust.sum()
    print(f"[labels] p{args.pct:.0f}: {pos} busts in {len(labelled[labelled.year.isin(fit_years)])} "
          f"train+cal rows ({pos / len(labelled[labelled.year.isin(fit_years)]):.2%})")
    thresholds.to_parquet(art / "thresholds.parquet", index=False)

    # 2. atlas (pre-test years only: it is the "historical" benchmark)
    hist = labelled[labelled.year.isin(fit_years)]
    atlas = build_atlas(hist)
    national = national_summary(hist)
    atlas.to_parquet(art / "atlas.parquet", index=False)

    # 3. features
    stats = fit_feature_stats(hist)
    feat = build_features(labelled, stats)
    warm = feat.init > feat.init.min() + pd.Timedelta(days=2)
    tr = feat[warm & feat.year.isin(train_years)]
    ca = feat[warm & feat.year.isin(args.cal)]
    te = feat[warm & feat.year.isin(args.test)].copy()

    # 4. baseline + model
    base = SpreadBaseline().fit(ca)
    model = BustModel().fit(tr, ca, num_rounds=args.rounds)
    model.save(art / "model.pkl")
    te["p_base"] = base.predict_proba(te)
    te["p_model"] = model.predict_proba(te)

    # 5. evaluation
    ev = evaluate(te.bust.to_numpy(), te.p_model.to_numpy(), te.p_base.to_numpy())
    by_lead = []
    for L, g in te.groupby("lead_days"):
        by_lead.append({
            "lead": int(L), "n": int(len(g)), "positives": int(g.bust.sum()),
            "model_pr_auc": pr_auc(g.bust, g.p_model), "baseline_pr_auc": pr_auc(g.bust, g.p_base),
            "model_bss_vs_spread": bss(g.bust, g.p_model, g.p_base),
            "model_brier": brier(g.bust, g.p_model), "baseline_brier": brier(g.bust, g.p_base),
        })
    by_region = []
    for r, g in te.groupby("region"):
        by_region.append({
            "region": r, "n": int(len(g)), "positives": int(g.bust.sum()),
            "model_pr_auc": pr_auc(g.bust, g.p_model), "baseline_pr_auc": pr_auc(g.bust, g.p_base),
            "model_bss_vs_spread": bss(g.bust, g.p_model, g.p_base),
            "model_roc_auc": roc_auc(g.bust, g.p_model), "baseline_roc_auc": roc_auc(g.bust, g.p_base),
        })
    ev.update({"by_lead": by_lead, "by_region": by_region, "test_years": args.test})
    print("\n[eval] test years", args.test, f"n={ev['n']} positives={ev['positives']} base_rate={ev['base_rate']:.3f}")
    print(f"{'':12s}{'Brier':>8s}{'BSS(clim)':>11s}{'PR-AUC':>8s}{'ROC-AUC':>9s}")
    for k in ("baseline", "model"):
        s = ev[k]
        print(f"{k:12s}{s['brier']:8.4f}{s['bss_vs_climatology']:11.3f}{s['pr_auc']:8.3f}{s['roc_auc']:9.3f}")
    print(f"model BSS vs spread baseline: {ev['model']['bss_vs_spread']:.3f}\n")

    # 6. explanations + per-init prediction files
    contribs = model.contributions(te)
    te["drivers"] = drivers(contribs, te, k=3)  # sentences kept in the Parquet, templates shipped in meta
    te = te.sort_values(["init", "region", "lead_days"])
    inits = []
    export = te[te.init.dt.hour == 0]  # one file per day keeps public/data small
    for init, g in export.groupby("init"):
        key = init_key(init)
        regions = {}
        for r, gr in g.groupby("region"):
            leads = []
            for _, row in gr.iterrows():
                p = float(row.p_model)
                leads.append({
                    "lead": int(row.lead_days), "prob": round(p, 4),
                    "baseline_prob": round(float(row.p_base), 4),
                    "band": band_of(p), "flag": bool(p >= FLAG_THRESHOLD),
                    "std": round(float(row["std"]), 1),
                    "std_pct_climo": round(float(row.std_pct_climo), 2),
                    "cluster_gap": round(float(row.cluster_gap), 2),
                    "jumpiness": None if pd.isna(row.jumpiness) else round(float(row.jumpiness), 1),
                    "drivers": [{"feature": d["feature"], "contribution": d["contribution"]} for d in row.drivers],
                    "outcome": {"error": round(float(row.error), 1),
                                "threshold": round(float(row.bust_threshold), 1),
                                "busted": bool(row.bust)},
                })
            regions[r] = {"leads": leads}
        doc = schemas.Prediction(init=key, source=source, regions=regions)
        (pred_dir / f"{key}.json").write_text(doc.model_dump_json(), encoding="utf-8")
        inits.append(key)

    # 7. atlas + meta + eval + inits
    cells = []
    for _, row in atlas.iterrows():
        cells.append({
            "region": row.region, "lead": int(row.lead_days), "season": row.season, "n": int(row.n),
            "bust_rate": round(float(row.bust_rate), 4),
            "err_p50": round(float(row.err_p50), 2), "err_p90": round(float(row.err_p90), 2),
            "err_p95": round(float(row.err_p95), 2), "err_max": round(float(row.err_max), 2),
            "spread_p50": round(float(row.spread_p50), 2), "spread_p95": round(float(row.spread_p95), 2),
            "spread_skill": round(float(row.spread_skill), 3),
            "worst_events": row.worst_events,
        })
    nat = [{"lead": int(r.lead_days), "season": r.season, "n": int(r.n), "bust_rate": round(float(r.bust_rate), 4),
            "err_p50": round(float(r.err_p50), 2), "err_p95": round(float(r.err_p95), 2)}
           for r in national.itertuples()]
    meta = {
        "product": "The Bust Atlas of India",
        "source": source, "source_label": source_label, "members": members,
        "grid": "64x32 equiangular (~5.6°)", "variable": "Z500 (500 hPa geopotential, m² s⁻²)",
        "leads": sorted(int(x) for x in df.lead_days.unique()),
        "years": {"train": train_years, "cal": args.cal, "test": args.test, "atlas": fit_years},
        "regions": [{"id": k, "label": b.label, "box": [b.lat0, b.lat1, b.lon0, b.lon1],
                     "centroid": list(b.centroid)} for k, b in REGIONS.items()],
        "state_to_region": STATE_TO_REGION,
        "seasons": [{"id": s, "label": SEASON_LABELS[s]} for s in SEASONS],
        "bust_definition": BUST_DEFINITION,
        "bands": BANDS, "flag_threshold": FLAG_THRESHOLD,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "git_sha": git_sha(),
        "model": {k: v for k, v in model.meta.items() if k != "params"},
        "rules": {k: list(v) for k, v in RULES.items()},
        "season_words": SEASON_WORDS,
        "synthetic": source == "synthetic",
    }
    files = {
        "meta.json": schemas.Meta(**meta),
        "atlas.json": schemas.Atlas(cells=cells, national=nat),
        "inits.json": schemas.Inits(inits=inits),
        "eval.json": schemas.Eval(**ev),
    }
    for name, doc in files.items():
        (out / name).write_text(doc.model_dump_json(), encoding="utf-8")
    # JSON schema for the frontend
    schema_dir = ROOT / "frontend/src/data"
    schema_dir.mkdir(parents=True, exist_ok=True)
    (schema_dir / "schema.json").write_text(json.dumps({
        name: m.model_json_schema() for name, m in {**schemas.ALL, "prediction": schemas.Prediction}.items()
    }, indent=1), encoding="utf-8")

    te.assign(drivers=te.drivers.map(lambda d: [x["feature"] for x in d])).to_parquet(art / "predictions_test.parquet", index=False)
    total = sum(p.stat().st_size for p in out.rglob("*.json"))
    print(f"[export] {len(inits)} prediction files, public/data = {total / 1e6:.2f} MB -> {out}")


if __name__ == "__main__":
    main()
