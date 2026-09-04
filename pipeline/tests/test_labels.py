import numpy as np
import pandas as pd

from pipeline.labels import KEY, add_error, apply_labels, fit_thresholds, label


def test_positive_rate_on_training_years_is_five_percent(synthetic):
    labelled, thr = label(synthetic, train_years=[2020, 2021], pct=95)
    train = labelled[labelled.year.isin([2020, 2021])]
    rates = train.groupby(KEY, observed=True).bust.mean()
    assert len(rates) == 10 * 10 * 4
    # per-cell rate is 5% up to quantile discreteness (cells have ~90-180 rows)
    assert rates.between(0.03, 0.07).all(), rates.describe()
    assert abs(train.bust.mean() - 0.05) < 0.005


def test_thresholds_use_training_years_only(synthetic_small):
    d = add_error(synthetic_small)
    thr_a = fit_thresholds(d[d.year == 2021])
    d2 = d.copy()
    d2.loc[d2.year == 2022, "error"] *= 100  # perturb the test year wildly
    thr_b = fit_thresholds(d2[d2.year == 2021])
    pd.testing.assert_frame_equal(thr_a, thr_b)


def test_bust_monotone_in_error(synthetic_small):
    labelled, _ = label(synthetic_small, train_years=[2021])
    for _, cell in labelled.groupby(KEY, observed=True):
        s = cell.sort_values("error")
        b = s.bust.to_numpy()
        # once True, stays True
        assert not np.any(b[:-1] & ~b[1:])


def test_apply_labels_raises_on_unknown_cell(synthetic_small):
    d = add_error(synthetic_small)
    thr = fit_thresholds(d[(d.year == 2021) & (d.lead_days <= 5)])
    try:
        apply_labels(d, thr)
    except ValueError as e:
        assert "no threshold" in str(e)
    else:
        raise AssertionError("expected ValueError")


def test_error_is_abs_mean_minus_truth(synthetic_small):
    d = add_error(synthetic_small.head(100))
    np.testing.assert_allclose(d.error, (d.ens_mean - d.truth).abs())
