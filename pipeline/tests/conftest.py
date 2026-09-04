import importlib.util
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="session")
def synthetic() -> pd.DataFrame:
    """Three synthetic years, 12-hourly inits, 10 leads, 10 regions (~219k rows)."""
    return _load("make_synthetic_boxstats").make(years=(2020, 2021, 2022), seed=7)


@pytest.fixture(scope="session")
def synthetic_small() -> pd.DataFrame:
    return _load("make_synthetic_boxstats").make(years=(2021, 2022), seed=11)
