import numpy as np
import pandas as pd

from pipeline.explain import RULES, drivers, sentence
from pipeline.features import FEATURES


def test_every_feature_has_a_rule():
    assert set(FEATURES) <= set(RULES)


def test_sentences_name_the_lead_day():
    row = pd.Series({"lead_days": 7, "season": "JJAS", "std_pct_climo": 0.97})
    for f in ("std", "std_growth", "cluster_gap", "base_rate", "std_pct_climo"):
        s = sentence(f, +1.0, row)
        assert "Day 7" in s or "monsoon" in s, (f, s)
    assert "top 3%" in sentence("std_pct_climo", 1.0, row)


def test_drivers_ordered_and_positive_first():
    rows = pd.DataFrame({"lead_days": [5, 5], "season": ["MAM", "ON"], "std_pct_climo": [0.5, 0.9]})
    c = np.zeros((2, len(FEATURES)))
    c[0, FEATURES.index("cluster_gap")] = 0.9
    c[0, FEATURES.index("std_growth")] = 0.4
    c[0, FEATURES.index("jump_rel")] = -0.7
    c[1, :] = -0.1  # all negative -> padded with negatives
    d = drivers(c, rows, k=3)
    assert [x["feature"] for x in d[0]][:2] == ["cluster_gap", "std_growth"]
    assert d[0][2]["contribution"] < 0
    assert len(d[1]) == 3 and all(x["contribution"] <= 0 for x in d[1])
