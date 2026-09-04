"""Export the ERA5 Z500 climatology as a small per-region table.

The live path (scripts/fetch_openmeteo_wn2.py) needs the SAME climatology the training
rows used, but cannot open Zarr on a laptop for every run. The climatology Zarr is the
one cheap exception: 64x32, a single chunk, ~40 MB, anonymous GCS, exactly as
scripts/extract_region_stats.py reads it. Run this once:

    .venv\\Scripts\\python scripts\\export_climo_table.py

Writes data/artifacts/climo_z500_boxes.parquet with columns
`dayofyear, hour, region, climo` (m^2 s^-2), region-mean over pipeline.regions boxes.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pipeline.regions import REGIONS, box_weights  # noqa: E402

CLIMO = ("gs://weatherbench2/datasets/era5-hourly-climatology/"
         "1990-2019_6h_64x32_equiangular_conservative.zarr")
VAR = "geopotential"
LEVEL = 500


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data/artifacts/climo_z500_boxes.parquet")
    args = ap.parse_args()

    print(f"[open] {CLIMO}")
    ds = xr.open_zarr(CLIMO, storage_options={"token": "anon"}, consolidated=True)
    da = ds[VAR].sel(level=LEVEL)
    dims = [d for d in da.dims if d not in ("latitude", "longitude")] + ["latitude", "longitude"]
    da = da.transpose(*dims).load()  # (hour, dayofyear, lat, lon)
    lat = da.latitude.values
    lon = da.longitude.values
    hours = [int(h) for h in da.hour.values]
    doys = [int(d) for d in da.dayofyear.values]
    print(f"[climo] hours={hours} dayofyear={len(doys)} grid {lat.size}x{lon.size}")

    arr = da.values  # (hour, doy, lat, lon)
    rows: list[dict] = []
    for region, box in REGIONS.items():
        w = box_weights(lat, lon, box)
        means = np.tensordot(arr, w, axes=([-2, -1], [0, 1]))  # (hour, doy)
        for hi, hour in enumerate(hours):
            for di, doy in enumerate(doys):
                rows.append({"dayofyear": doy, "hour": hour, "region": region,
                             "climo": float(means[hi, di])})

    df = pd.DataFrame(rows).sort_values(["region", "dayofyear", "hour"]).reset_index(drop=True)
    out = ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out, index=False)
    print(f"[done] {out} rows={len(df)} size={out.stat().st_size / 1e3:.0f} KB")


if __name__ == "__main__":
    main()
