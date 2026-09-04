import numpy as np
import pandas as pd

from pipeline.features import FEATURES, build_features, fit_feature_stats
from pipeline.labels import label


def _prep(df, train_years):
    labelled, _ = label(df, train_years=train_years)
    stats = fit_feature_stats(labelled[labelled.year.isin(train_years)])
    return labelled, stats


def test_all_features_present_and_finite_after_warmup(synthetic_small):
    labelled, stats = _prep(synthetic_small, [2021])
    f = build_features(labelled, stats)
    assert set(FEATURES) <= set(f.columns)
    warm = f[(f.init > f.init.min() + pd.Timedelta(days=2)) & (f.lead_days < 10)]
    assert np.isfinite(warm[FEATURES].to_numpy(dtype=float)).all()
    # only jumpiness/jump_rel may be NaN, and only at lead 10 (no lead-11 partner)
    other = [c for c in FEATURES if c not in ("jumpiness", "jump_rel")]
    assert np.isfinite(f[other].to_numpy(dtype=float)).all()


def test_no_leakage(synthetic_small):
    """Features for init <= t must not change when rows after t are removed."""
    labelled, stats = _prep(synthetic_small, [2021])
    full = build_features(labelled, stats)
    rng = np.random.default_rng(0)
    inits = np.sort(labelled.init.unique())
    for t in rng.choice(inits[100:-100], size=3, replace=False):
        trunc = build_features(labelled[labelled.init <= t], stats)
        a = full[full.init <= t].sort_values(["region", "init", "lead_days"]).reset_index(drop=True)
        b = trunc.sort_values(["region", "init", "lead_days"]).reset_index(drop=True)
        pd.testing.assert_frame_equal(a[FEATURES], b[FEATURES], check_exact=False, rtol=1e-12)


def test_jumpiness_nan_only_when_previous_run_missing(synthetic_small):
    labelled, stats = _prep(synthetic_small, [2021])
    f = build_features(labelled, stats)
    first = f.init == f.init.min()
    # the first init has no run 24 h earlier -> NaN; lead 10 never has a lead-11 partner -> NaN
    assert f.loc[first, "jumpiness"].isna().all()
    assert f.loc[f.lead_days == 10, "jumpiness"].isna().all()
    later = (~first) & (f.lead_days < 10) & (f.init > f.init.min() + pd.Timedelta(days=1))
    assert f.loc[later, "jumpiness"].notna().all()


def test_base_rate_uses_training_years_only(synthetic_small):
    labelled, _ = label(synthetic_small, train_years=[2021])
    stats_a = fit_feature_stats(labelled[labelled.year == 2021])
    perturbed = labelled.copy()
    perturbed.loc[perturbed.year == 2022, "bust"] = True
    stats_b = fit_feature_stats(perturbed[perturbed.year == 2021])
    pd.testing.assert_frame_equal(stats_a["base_rate"], stats_b["base_rate"])
    assert stats_a["base_rate"].base_rate.between(0.02, 0.08).all()


def test_std_pct_climo_in_unit_interval_and_monotone(synthetic_small):
    labelled, stats = _prep(synthetic_small, [2021])
    f = build_features(labelled, stats)
    assert f.std_pct_climo.between(0, 1).all()
    cell = f[(f.region == "central") & (f.lead_days == 5) & (f.season == "JJAS")].sort_values("ens_std")
    assert cell.std_pct_climo.is_monotonic_increasing
