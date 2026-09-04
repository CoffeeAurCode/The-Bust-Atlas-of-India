"""Part 11: the confidence layer must be ensemble-agnostic.

Trains the whole pipeline on one synthetic ensemble, then scores that trained model,
unchanged, on box-stats from a different synthetic ensemble with a different member
count and a different source string. Everything runs in tmp dirs via subprocess so the
committed artifacts and frontend/public/data are untouched.
"""

from __future__ import annotations

import importlib.util
import json
import pickle
import subprocess
import sys
from pathlib import Path

import pytest

from pipeline import schemas
from pipeline.features import FEATURES, build_features
from pipeline.labels import add_error, apply_labels

ROOT = Path(__file__).resolve().parents[2]


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _run(script: str, *args: str) -> str:
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / script), *args],
        cwd=ROOT, text=True, capture_output=True,
    )
    assert proc.returncode == 0, f"{script} failed:\n{proc.stdout}\n{proc.stderr}"
    return proc.stdout


@pytest.fixture(scope="module")
def cross_run(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("cross_model")
    mk = _load("make_synthetic_boxstats")

    ifs_pq = tmp / "ifs.parquet"
    fgn_pq = tmp / "fgn.parquet"
    mk.make(years=(2020, 2021, 2022), members=50, seed=1, source="synthetic").to_parquet(ifs_pq, index=False)
    mk.make(years=(2022,), members=64, seed=2, source="fgn").to_parquet(fgn_pq, index=False)

    out, art = tmp / "out", tmp / "art"
    _run("run_pipeline.py", "--input", str(ifs_pq), "--out", str(out), "--artifacts", str(art),
         "--rounds", "60")
    stdout = _run("cross_model.py", "--model", str(art / "model.pkl"),
                  "--thresholds", str(art / "thresholds.parquet"),
                  "--stats", str(art / "feature_stats.pkl"),
                  "--baseline", str(art / "baseline.pkl"),
                  "--input", str(fgn_pq), "--test", "2022",
                  "--out", str(out / "eval.json"))
    return {"tmp": tmp, "out": out, "art": art, "ifs": ifs_pq, "fgn": fgn_pq, "stdout": stdout}


def test_run_pipeline_persists_the_cross_model_artifacts(cross_run):
    for name in ("model.pkl", "thresholds.parquet", "feature_stats.pkl", "baseline.pkl"):
        assert (cross_run["art"] / name).exists(), name
    with open(cross_run["art"] / "feature_stats.pkl", "rb") as f:
        stats = pickle.load(f)
    assert set(stats) == {"spread_quantiles", "base_rate"}


def test_eval_json_validates_and_carries_the_cross_model_block(cross_run):
    doc = schemas.Eval.model_validate_json((cross_run["out"] / "eval.json").read_text(encoding="utf-8"))
    cm = doc.cross_model
    assert cm is not None
    assert cm.source == "fgn"
    assert cm.members == 64
    assert cm.n > 0
    assert cm.positives > 0
    assert 0.0 <= cm.base_rate <= 1.0
    assert len(cm.by_lead) == 10
    assert sorted(r["lead"] for r in cm.by_lead) == list(range(1, 11))
    # the untouched IFS block is still there
    assert doc.n > 0 and doc.test_years == [2022]


def test_stdout_prints_a_comparison_table(cross_run):
    for token in ("Brier", "BSS(clim)", "PR-AUC", "ROC-AUC", "fgn"):
        assert token in cross_run["stdout"], token


def test_feature_columns_are_identical_for_both_sources(cross_run):
    """The data contract is the ensemble-agnostic boundary: same columns, same order."""
    import pandas as pd

    with open(cross_run["art"] / "feature_stats.pkl", "rb") as f:
        stats = pickle.load(f)
    thresholds = pd.read_parquet(cross_run["art"] / "thresholds.parquet")
    frames = []
    for path in (cross_run["ifs"], cross_run["fgn"]):
        df = pd.read_parquet(path)
        df = df[df.init.dt.year == 2022]
        frames.append(build_features(apply_labels(add_error(df), thresholds), stats))
    a, b = frames
    assert list(a.columns) == list(b.columns)
    assert set(FEATURES) <= set(a.columns)
    assert list(a[FEATURES].dtypes.astype(str)) == list(b[FEATURES].dtypes.astype(str))
    assert not b[FEATURES].isna().all().any(), "a feature is entirely NaN on the second ensemble"


def test_frontend_eval_json_if_present_still_validates():
    p = ROOT / "frontend/public/data/eval.json"
    if not p.exists():
        pytest.skip("run scripts/run_pipeline.py first")
    doc = schemas.Eval.model_validate_json(p.read_text(encoding="utf-8"))
    if doc.cross_model is not None:
        assert doc.cross_model.n > 0
        assert len(doc.cross_model.by_lead) == len(doc.by_lead)
        json.dumps(doc.model_dump())
