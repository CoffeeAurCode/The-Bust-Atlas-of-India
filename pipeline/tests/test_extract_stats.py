import importlib.util
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_member_stats_known_values():
    ex = _load("extract_region_stats")
    s = ex.member_stats(np.array([1.0, 2.0, 3.0, 4.0, 5.0]))
    assert s["ens_mean"] == 3.0
    assert np.isclose(s["ens_std"], np.std([1, 2, 3, 4, 5], ddof=1))
    assert s["q50"] == 3.0
    assert s["q10"] <= s["q25"] <= s["q50"] <= s["q75"] <= s["q90"]


def test_cluster_gap_bimodal_vs_gaussian():
    ex = _load("extract_region_stats")
    rng = np.random.default_rng(1)
    gauss = np.sort(rng.normal(0, 1, 50))
    bimodal = np.sort(np.concatenate([rng.normal(-3, 0.3, 25), rng.normal(3, 0.3, 25)]))
    assert ex.cluster_gap(gauss) < 0.5
    assert ex.cluster_gap(bimodal) > 1.0


def test_synthetic_validates():
    mk = _load("make_synthetic_boxstats")
    va = _load("validate_boxstats")
    df = mk.make(years=(2021,), seed=3)
    assert va.validate(df) == []
    assert len(df) == 730 * 10 * 10
