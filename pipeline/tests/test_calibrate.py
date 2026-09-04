"""The calibrator has to do two things at once: follow the shape of the observed bust
frequency, and not tie predictions together. Getting either wrong has already cost a
release, so both are pinned here."""

import numpy as np

from pipeline.calibrate import EPS, MonotoneCalibrator


def _convex_tail(n=40000, seed=0):
    """Scores whose bust rate is flat until the top decile, then rises sharply. This is
    the shape the real data has and the shape a single logistic slope cannot fit."""
    rng = np.random.default_rng(seed)
    raw = rng.uniform(0.02, 0.40, n)
    p = np.where(raw > 0.36, 0.30, 0.04)
    return raw, (rng.random(n) < p).astype(int)


def test_follows_a_convex_tail():
    raw, y = _convex_tail()
    c = MonotoneCalibrator().fit(raw, y)
    top = c.predict(raw[raw > 0.36])
    rest = c.predict(raw[raw <= 0.36])
    assert top.mean() > 0.20, top.mean()   # a Platt fit flattens this to well under 0.15
    assert rest.mean() < 0.08, rest.mean()


def test_strictly_increasing_so_ranking_survives():
    raw, y = _convex_tail()
    c = MonotoneCalibrator().fit(raw, y)
    x = np.unique(raw)
    p = c.predict(x)
    assert (np.diff(p) > 0).all(), "calibration must never tie two distinct scores"
    assert len(np.unique(p)) == len(x)


def test_tie_break_is_invisible_and_row_local():
    raw, y = _convex_tail()
    c = MonotoneCalibrator().fit(raw, y)
    p = c.predict(raw)
    # the tie-break shifts a probability by at most EPS, so percentages are unaffected
    assert np.abs(p - c.iso.predict(raw)).max() <= EPS + 1e-12
    # a row calibrates the same alone as in a batch: no dependence on the other rows
    assert np.isclose(c.predict(raw[:1])[0], p[0])
    assert (p >= 0).all() and (p <= 1).all()
