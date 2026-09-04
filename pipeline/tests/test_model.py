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


def test_early_stopping_does_not_bail_immediately(synthetic):
    """Regression: with scale_pos_weight applied to training but not to the validation
    set, early stopping on binary_logloss fired at iteration 1 and the shipped model was
    a single tree. Early stopping now scores AUC, so it must actually boost."""
    f = _frame(synthetic)
    m = BustModel().fit(f[f.year == 2020], f[f.year == 2021], num_rounds=200)
    assert m.meta["params"]["metric"] == "auc"
    assert max(m.meta["best_iterations"]) > 3, m.meta["best_iterations"]


def test_calibration_preserves_ranking(synthetic):
    """The calibrator is strictly increasing, so it must not change the ordering of
    predictions. Plain isotonic flattened them onto a few dozen values and cost PR-AUC."""
    f = _frame(synthetic)
    te = f[f.year == 2022]
    m = BustModel().fit(f[f.year == 2020], f[f.year == 2021], num_rounds=100)
    raw, cal = m.predict_raw(te), m.predict_proba(te)
    assert np.array_equal(np.argsort(raw, kind="stable"), np.argsort(cal, kind="stable"))
    assert len(np.unique(cal)) == len(np.unique(raw))
    assert (cal >= 0).all() and (cal <= 1).all()


def test_fit_cv_scores_every_row_out_of_fold(synthetic):
    """fit_cv must train on the whole development period and calibrate on scores from
    boosters that never saw the row. Folds are contiguous in init date."""
    f = _frame(synthetic)
    dev = f[f.year.isin([2020, 2021])]
    m = BustModel().fit_cv(dev, n_folds=3, num_rounds=60, n_seeds=2)
    assert m.meta["cv_folds"] == 3
    assert m.meta["n_train"] == len(dev)
    # rounds are fixed up front, so every fold and the final fit use the same count and
    # no block is surrendered to early stopping
    assert len(set(m.meta["best_iterations"])) == 1
    p = m.predict_proba(f[f.year == 2022])
    assert np.isfinite(p).all() and (p >= 0).all() and (p <= 1).all()


def test_baseline_and_model_share_a_calibrator(synthetic):
    """The headline claim is model vs spread baseline, so a difference between them must
    not be a difference of calibrator."""
    f = _frame(synthetic)
    dev = f[f.year.isin([2020, 2021])]
    b = SpreadBaseline().fit(dev)
    m = BustModel().fit_cv(dev, n_folds=3, num_rounds=60, n_seeds=2)
    assert type(b.cal) is type(m.cal)
