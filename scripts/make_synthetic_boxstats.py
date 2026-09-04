"""Generate a fake box-stats Parquet with the real schema so Parts 2-4 can be built
before the Colab extraction finishes. Numbers are meaningless; shape is real.

    python scripts/make_synthetic_boxstats.py --out data/cache/synthetic_z500_boxstats.parquet
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pipeline.regions import REGIONS  # noqa: E402

COLUMNS = [
    "source", "init", "lead_days", "region", "var", "ens_mean", "ens_std",
    "q10", "q25", "q50", "q75", "q90", "cluster_gap", "truth", "climo",
]


def make(years=(2020, 2021, 2022), leads=range(1, 11), members=50, seed=0,
         source="synthetic") -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    inits = pd.date_range(f"{years[0]}-01-01", f"{years[-1]}-12-31 12:00", freq="12h")
    rows = []
    Z0 = 57000.0  # z500 in m^2/s^2 ~ 5700 m * 9.8
    for r_i, region in enumerate(REGIONS):
        # each region has its own climatological amplitude and a seasonal cycle
        amp = 600 + 80 * r_i
        for init in inits:
            doy = init.dayofyear
            season = np.cos(2 * np.pi * (doy - 15) / 365.25)
            # a slowly varying "regime" driving error growth
            regime = np.sin(2 * np.pi * doy / 45 + r_i)
            for lead in leads:
                valid = init + pd.Timedelta(days=lead)
                climo = Z0 + amp * np.cos(2 * np.pi * (valid.dayofyear - 15) / 365.25)
                spread = (60 + 25 * lead) * (1 + 0.4 * regime) * rng.lognormal(0, 0.15)
                bimodal = rng.random() < 0.06 + 0.03 * lead / 10
                mem = rng.normal(0, spread, members)
                if bimodal:
                    mem[: members // 2] += spread * 1.5
                mem += climo + 120 * season
                mem = np.sort(mem)
                ens_mean = mem.mean()
                err_scale = (25 + 18 * lead) * (1 + 0.5 * regime + (0.8 if bimodal else 0))
                truth = ens_mean + rng.normal(0, err_scale)
                rows.append((
                    source, init, lead, region, "z500", ens_mean, mem.std(ddof=1),
                    *np.quantile(mem, [0.1, 0.25, 0.5, 0.75, 0.9]),
                    float(np.diff(mem[members // 10: -(members // 10)]).max() / mem.std()), truth, climo,
                ))
    df = pd.DataFrame(rows, columns=COLUMNS)
    return df.sort_values(["init", "lead_days", "region"]).reset_index(drop=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data/cache/synthetic_z500_boxstats.parquet")
    ap.add_argument("--years", nargs="+", type=int, default=[2020, 2021, 2022])
    ap.add_argument("--source", default="synthetic", help="value written to the source column")
    ap.add_argument("--members", type=int, default=50)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()
    df = make(years=tuple(args.years), members=args.members, seed=args.seed, source=args.source)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(args.out, index=False)
    print(f"wrote {args.out}: {len(df)} rows, source={args.source}, members={args.members}")
