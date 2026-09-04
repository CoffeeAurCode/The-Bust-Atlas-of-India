import numpy as np
import pandas as pd

from pipeline.baseline import SpreadBaseline
from pipeline.eval import pr_auc
from pipeline.features import FEATURES, build_features, fit_feature_stats
from pipeline.labels import label
from pipeline.model import BustModel


def _frame(synthetic):
    labelled, _ = label(synthetic, train_years=[2020, 2021])
    stats = fit_feature_stats(labelled[labelled.year.isin([2020, 2021])])
    f = build_features(labelled, stats)
    return f[f.init > f.init.min() + pd.Timedelta(days=2)]


def test_model_learns_planted_signal(synthetic):
    f = _frame(synthetic)
    # plant a label that is a known function of an issue-time feature
    rng = np.random.default_rng(0)
    f = f.copy()
    f["bust"] = (f["std_growth_rel"] > f["std_growth_rel"].quantile(0.93)) & (rng.random(len(f)) < 0.9)
    tr, ca, te = f[f.year == 2020], f[f.year == 2021], f[f.year == 2022]
    m = BustModel().fit(tr, ca, num_rounds=200)
    assert pr_auc(te.bust, m.predict_proba(te)) > 0.8


def test_calibration_monotone_and_bounded(synthetic_small):
    labelled, _ = label(synthetic_small, train_years=[2021])
    stats = fit_feature_stats(labelled[labelled.year == 2021])
    f = build_features(labelled, stats)
    f = f[f.init > f.init.min() + pd.Timedelta(days=2)]
    tr = f[(f.year == 2021) & (f.init.dt.month <= 8)]
    ca = f[(f.year == 2021) & (f.init.dt.month > 8)]
    te = f[f.year == 2022]
    m = BustModel().fit(tr, ca, num_rounds=100)
    raw = m.predict_raw(te)
    p = m.predict_proba(te)
    assert p.min() >= 0 and p.max() <= 1
    order = np.argsort(raw)
    assert np.all(np.diff(p[order]) >= -1e-12)


def test_save_load_roundtrip(synthetic_small, tmp_path):
    labelled, _ = label(synthetic_small, train_years=[2021])
    stats = fit_feature_stats(labelled[labelled.year == 2021])
    f = build_features(labelled, stats)
    f = f[f.init > f.init.min() + pd.Timedelta(days=2)]
    tr = f[(f.year == 2021) & (f.init.dt.month <= 8)]
    ca = f[(f.year == 2021) & (f.init.dt.month > 8)]
    te = f[f.year == 2022].head(500)
    m = BustModel().fit(tr, ca, num_rounds=50)
    m.save(tmp_path / "m.pkl")
    m2 = BustModel.load(tmp_path / "m.pkl")
    np.testing.assert_array_equal(m.predict_proba(te), m2.predict_proba(te))
    assert m2.meta["features"] == FEATURES
    c = m2.contributions(te)
    assert c.shape == (len(te), len(FEATURES))


def test_baseline_fits_and_predicts(synthetic_small):
    labelled, _ = label(synthetic_small, train_years=[2021])
    stats = fit_feature_stats(labelled[labelled.year == 2021])
    f = build_features(labelled, stats)
    ca = f[f.year == 2021]
    te = f[f.year == 2022]
    b = SpreadBaseline().fit(ca)
    p = b.predict_proba(te)
    assert p.shape == (len(te),) and p.min() >= 0 and p.max() <= 1
