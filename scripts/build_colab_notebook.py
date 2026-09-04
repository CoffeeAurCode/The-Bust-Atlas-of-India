"""Regenerate notebooks/01-extract-region-stats.ipynb from the current regions.py and
extract_region_stats.py so the Colab copy never drifts from the repo.

    python scripts/build_colab_notebook.py
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def cell(kind: str, src: str) -> dict:
    c = {"cell_type": kind, "metadata": {}, "source": src.splitlines(keepends=True)}
    if kind == "code":
        c.update({"outputs": [], "execution_count": None})
    return c


def main() -> None:
    regions = (ROOT / "pipeline/regions.py").read_text(encoding="utf-8")
    script = (ROOT / "scripts/extract_region_stats.py").read_text(encoding="utf-8")
    nb = {
        "nbformat": 4, "nbformat_minor": 5,
        "metadata": {"kernelspec": {"name": "python3", "display_name": "Python 3"},
                     "colab": {"name": "01-extract-region-stats.ipynb"}},
        "cells": [
            cell("markdown", """# Vishwas · Part 1 — extract region stats (run in Colab)

Pulls Z500 from the ECMWF IFS ENS archive on WeatherBench 2 (no auth), computes per-region ensemble statistics for Day 1–10, and writes one small Parquet. Expected: ~15–30 min for 2020–2022 on a normal Colab CPU runtime. **No GPU needed.**

Steps: Runtime → Run all. Watch the first `[ckpt]` line: `rows` should be 8000 and `eta` under ~40 min. When `[done]` prints, the last cell downloads the Parquet. Put it in `vishwas/data/cache/`.

If Colab disconnects: reconnect and re-run the extract cell; it resumes from the last checkpoint.
"""),
            cell("code", "!pip -q install 'zarr>=2.18,<3' gcsfs xarray pyarrow\n"),
            cell("code", "%%writefile regions.py\n" + regions),
            cell("code", "%%writefile extract_region_stats.py\n" + script),
            cell("markdown", "## Sanity check: the archives open and a Z500 field over India looks like weather\n"),
            cell("code", '''import xarray as xr, numpy as np, matplotlib.pyplot as plt
S = {"token": "anon"}
ens = xr.open_zarr("gs://weatherbench2/datasets/ifs_ens/2018-2022-64x32_equiangular_conservative.zarr", storage_options=S)
print("levels:", ens.level.values, "| members:", ens.sizes["number"], "| lead index (hours):", ens.prediction_timedelta.values[:6], "...")
z = ens.geopotential.sel(level=500, time="2022-07-12T00", prediction_timedelta=120).isel(number=0).load()
z.transpose("latitude", "longitude").sel(latitude=slice(0, 45), longitude=slice(55, 110)).plot()
plt.title("IFS ENS member 0, Z500, init 2022-07-12 00Z, Day 5"); plt.show()
'''),
            cell("markdown", "## Extract (resumable; re-run this cell if Colab disconnects)\n"),
            cell("code", "!python extract_region_stats.py --source ifs_ens --years 2020 2021 2022 --out /content/out\n"),
            cell("code", '''import pandas as pd
df = pd.read_parquet("/content/out/ifs_ens_z500_boxstats.parquet")
print(df.shape)
print("median spread by lead:", df.groupby("lead_days").ens_std.median().round(0).to_dict())
print("median |mean-truth| by lead:", (df.ens_mean-df.truth).abs().groupby(df.lead_days).median().round(0).to_dict())
'''),
            cell("code", 'from google.colab import files\nfiles.download("/content/out/ifs_ens_z500_boxstats.parquet")\n'),
            cell("markdown", "## Optional bonus (only if the above finished fast): WeatherNext 2 archive for cross-model validation\n"),
            cell("code", "# !python extract_region_stats.py --source fgn --years 2022 --out /content/out\n# files.download('/content/out/fgn_z500_boxstats.parquet')\n"),
        ],
    }
    out = ROOT / "notebooks/01-extract-region-stats.ipynb"
    out.write_text(json.dumps(nb, indent=1), encoding="utf-8")
    print("wrote", out)


if __name__ == "__main__":
    main()
