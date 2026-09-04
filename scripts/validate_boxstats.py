"""Acceptance test for a box-stats Parquet (Part 1 done criterion).

    python scripts/validate_boxstats.py data/cache/ifs_ens_z500_boxstats.parquet
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pipeline.regions import REGIONS  # noqa: E402

REQUIRED = {
    "source": "object", "init": "datetime64", "lead_days": "int", "region": "object",
    "var": "object", "ens_mean": "float", "ens_std": "float", "q10": "float",
    "q25": "float", "q50": "float", "q75": "float", "q90": "float",
    "cluster_gap": "float", "truth": "float", "climo": "float",
}


def validate(df: pd.DataFrame) -> list[str]:
    problems: list[str] = []
    missing = set(REQUIRED) - set(df.columns)
    if missing:
        return [f"missing columns: {sorted(missing)}"]
    for c, kind in REQUIRED.items():
        dt = str(df[c].dtype)
        if kind == "datetime64" and not dt.startswith("datetime64"):
            problems.append(f"{c} dtype {dt}, expected datetime64")
        elif kind == "int" and not np.issubdtype(df[c].dtype, np.integer):
            problems.append(f"{c} dtype {dt}, expected integer")
        elif kind == "float" and not np.issubdtype(df[c].dtype, np.floating):
            problems.append(f"{c} dtype {dt}, expected float")
    regions = set(df.region.unique())
    if regions != set(REGIONS):
        problems.append(f"regions differ: extra={regions - set(REGIONS)} missing={set(REGIONS) - regions}")
    leads = sorted(df.lead_days.unique())
    n_init = df.init.nunique()
    expected = n_init * len(leads) * len(REGIONS)
    if len(df) != expected:
        problems.append(f"rows {len(df)} != inits {n_init} x leads {len(leads)} x regions {len(REGIONS)} = {expected}")
    nan_frac = df[[c for c in REQUIRED if REQUIRED[c] == "float"]].isna().mean().max()
    if nan_frac > 0.005:
        problems.append(f"NaN fraction {nan_frac:.3%} > 0.5%")
    per_init = df.groupby("init").lead_days.nunique()
    if (per_init != len(leads)).any():
        problems.append(f"{(per_init != len(leads)).sum()} inits missing leads")
    med_std = df.groupby("lead_days").ens_std.median()
    if not med_std.is_monotonic_increasing:
        problems.append(f"median ens_std not increasing with lead: {med_std.round(1).to_dict()}")
    err = (df.ens_mean - df.truth).abs()
    e1 = err[df.lead_days == leads[0]].median()
    e10 = err[df.lead_days == leads[-1]].median()
    # Error must grow strongly with lead. Threshold is loose on purpose: the ratio
    # depends on season mix (DJF D10 ~ 102, JJAS ~ 71 on IFS ENS 2020-2022) and on
    # whether short leads are dominated by analysis-increment noise.
    if not e1 < 0.40 * e10:
        problems.append(f"median |mean-truth| D{leads[0]}={e1:.1f} not < 40% of D{leads[-1]}={e10:.1f}")
    if (df.ens_std <= 0).any():
        problems.append("non-positive ens_std present")
    if not ((df.q10 <= df.q50) & (df.q50 <= df.q90)).all():
        problems.append("quantiles not ordered")
    return problems


def main() -> None:
    path = sys.argv[1]
    df = pd.read_parquet(path)
    problems = validate(df)
    print(f"{path}: {len(df)} rows, {df.init.nunique()} inits, "
          f"{df.init.min().date()} -> {df.init.max().date()}, {df.source.iloc[0]}")
    if problems:
        print("FAIL")
        for p in problems:
            print("  -", p)
        sys.exit(1)
    print("OK")


if __name__ == "__main__":
    main()
