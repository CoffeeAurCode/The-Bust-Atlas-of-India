import numpy as np

from pipeline.atlas import build_atlas, national_summary
from pipeline.labels import KEY, label


def test_atlas_shape_and_rates(synthetic_small):
    labelled, _ = label(synthetic_small, train_years=[2021])
    atlas = build_atlas(labelled)
    assert len(atlas) == 400
    expected = labelled.groupby(KEY, observed=True).bust.mean().reset_index()
    merged = atlas.merge(expected, on=KEY)
    np.testing.assert_allclose(merged.bust_rate, merged.bust)
    assert (atlas.n > 0).all()
    assert (atlas.err_p50 <= atlas.err_p90).all() and (atlas.err_p90 <= atlas.err_p95).all()


def test_worst_events_sorted_and_capped(synthetic_small):
    labelled, _ = label(synthetic_small, train_years=[2021])
    atlas = build_atlas(labelled, worst_k=5)
    for ev in atlas.worst_events:
        errs = [e["error"] for e in ev]
        assert len(errs) == 5
        assert errs == sorted(errs, reverse=True)


def test_national_summary(synthetic_small):
    labelled, _ = label(synthetic_small, train_years=[2021])
    nat = national_summary(labelled)
    assert len(nat) == 10 * 4
    assert nat.bust_rate.between(0, 1).all()
