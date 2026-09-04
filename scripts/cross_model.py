"""Cross-model validation: score the SAME trained model on a DIFFERENT ensemble.

The confidence layer is trained on IFS ENS box-stats (50 members). This script loads
that trained model unchanged, plus the thresholds, the Tier-0 feature statistics and the
calibrated spread baseline that the IFS run produced, and applies all of them to
box-stats extracted from another ensemble (WeatherNext 2 / FGN, 64 members) for the same
test year. Nothing is refitted. A drop in skill is expected and is reported honestly.

    python scripts/cross_model.py \
        --model data/artifacts/model.pkl \
        --thresholds data/artifacts/thresholds.parquet \
        --stats data/artifacts/feature_stats.pkl \
        --baseline data/artifacts/baseline.pkl \
        --input data/cache/fgn_z500_boxstats.parquet \
        --test 2022 --out frontend/public/data/eval.json
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import pickle
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pipeline import schemas  # noqa: E402
from pipeline.eval import brier, bss, evaluate, pr_auc, roc_auc  # noqa: E402
from pipeline.features import build_features  # noqa: E402
from pipeline.labels import add_error, apply_labels  # noqa: E402
from pipeline.model import BustModel  # noqa: E402

FALLBACK_LABELS = {"fgn": ("Google WeatherNext 2 (WeatherBench 2 archive)", 64)}


def source_labels() -> dict:
    """Reuse run_pipeline.SOURCE_LABELS so the two scripts never disagree."""
    try:
        spec = importlib.util.spec_from_file_location("_run_pipeline", ROOT / "scripts" / "run_pipeline.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return dict(mod.SOURCE_LABELS)
    except Exception:
        return dict(FALLBACK_LABELS)


def score(te: pd.DataFrame) -> dict:
    """evaluate() plus the same by_lead block run_pipeline writes."""
    ev = evaluate(te.bust.to_numpy(), te.p_model.to_numpy(), te.p_base.to_numpy())
    by_lead = []
    for lead, g in te.groupby("lead_days"):
        by_lead.append({
            "lead": int(lead), "n": int(len(g)), "positives": int(g.bust.sum()),
            "model_pr_auc": pr_auc(g.bust, g.p_model), "baseline_pr_auc": pr_auc(g.bust, g.p_base),
            "model_bss_vs_spread": bss(g.bust, g.p_model, g.p_base),
            "model_brier": brier(g.bust, g.p_model), "baseline_brier": brier(g.bust, g.p_base),
        })
    ev["by_lead"] = by_lead
    return ev


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="data/artifacts/model.pkl")
    ap.add_argument("--thresholds", default="data/artifacts/thresholds.parquet")
    ap.add_argument("--stats", default="data/artifacts/feature_stats.pkl")
    ap.add_argument("--baseline", default="data/artifacts/baseline.pkl")
    ap.add_argument("--input", required=True)
    ap.add_argument("--test", nargs="+", type=int, default=[2022])
    ap.add_argument("--out", default="frontend/public/data/eval.json")
    args = ap.parse_args()

    out_path = Path(args.out)
    if not out_path.is_absolute():
        out_path = ROOT / out_path
    if not out_path.exists():
        raise SystemExit(f"{out_path} does not exist: run scripts/run_pipeline.py first")

    df = pd.read_parquet(args.input)
    source = str(df.source.iloc[0])
    label, members = source_labels().get(source, (source, int(df.attrs.get("members", 0))))

    # 1. labels: the SAME thresholds the training run fitted. Never refit on the new ensemble.
    thresholds = pd.read_parquet(args.thresholds)
    labelled = apply_labels(add_error(df), thresholds)

    # 2. features: the SAME Tier-0 training statistics.
    with open(args.stats, "rb") as f:
        stats = pickle.load(f)
    feat = build_features(labelled, stats)

    # 3. warm-up filter, identical to run_pipeline (jumpiness needs the previous run).
    warm = feat.init > feat.init.min() + pd.Timedelta(days=2)
    te = feat[warm & feat.year.isin(args.test)].copy()
    if te.empty:
        raise SystemExit(f"no rows for test years {args.test} in {args.input}")

    # 4. the SAME calibrated baseline and the SAME trained model. No fitting happens here.
    with open(args.baseline, "rb") as f:
        base = pickle.load(f)
    model = BustModel.load(args.model)
    te["p_base"] = base.predict_proba(te)
    te["p_model"] = model.predict_proba(te)

    ev_new = score(te)
    block = {
        "source": source, "source_label": label, "members": int(members),
        "n": ev_new["n"], "positives": ev_new["positives"], "base_rate": ev_new["base_rate"],
        "model": ev_new["model"], "baseline": ev_new["baseline"],
        "by_lead": ev_new["by_lead"], "test_years": list(args.test),
    }

    existing = json.loads(out_path.read_text(encoding="utf-8"))
    existing["cross_model"] = block
    doc = schemas.Eval(**existing)  # validates before it is written
    out_path.write_text(doc.model_dump_json(), encoding="utf-8")

    # 5. the honest comparison
    meta_path = out_path.parent / "meta.json"
    trained = "the training ensemble"
    trained_short = "trained"
    if meta_path.exists():
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        trained = f"{meta.get('source_label', meta.get('source'))}, {meta.get('members')} members"
        trained_short = str(meta.get("source", "trained"))
    print(f"\n[cross-model] trained on {trained}; scored unchanged on {label}, {members} members")
    print(f"              test years {args.test}: n={block['n']} positives={block['positives']} "
          f"base_rate={block['base_rate']:.3f}")
    print(f"\n{'':22s}{'Brier':>9s}{'BSS(clim)':>11s}{'PR-AUC':>9s}{'ROC-AUC':>9s}")
    for name, sc in ((f"{trained_short:10s} model", existing["model"]),
                     (f"{trained_short:10s} baseline", existing["baseline"]),
                     (f"{source:10s} model", block["model"]),
                     (f"{source:10s} baseline", block["baseline"])):
        print(f"{name:22s}{sc['brier']:9.4f}{sc['bss_vs_climatology']:11.3f}"
              f"{sc['pr_auc']:9.3f}{sc['roc_auc']:9.3f}")
    print(f"\nmodel BSS vs spread baseline: {trained_short} {existing['model']['bss_vs_spread']:.3f}  "
          f"{source} {block['model']['bss_vs_spread']:.3f}")
    print(f"[cross-model] wrote cross_model block into {out_path}\n")


if __name__ == "__main__":
    main()
