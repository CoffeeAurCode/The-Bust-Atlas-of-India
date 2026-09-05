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

Steps: Runtime → Run all. Watch the first `[ckpt]` line: `rows` should be 8000 and `eta` under ~40 min.

**The Parquet is saved to your Google Drive**, at `MyDrive/vishwas/`. Download it from there into `vishwas/data/cache/`. Do not rely on the browser download: `google.colab.files.download()` renders a JavaScript widget that silently does nothing when the notebook is driven from VS Code or any front end that is not a real Colab tab, so the file just sits on the runtime until it is discarded.

If Colab disconnects: reconnect and re-run the extract cell; it resumes from the last checkpoint.
"""),
            cell("code", "!pip -q install 'zarr>=2.18,<3' gcsfs xarray pyarrow\n"),
            cell("code", "%%writefile regions.py\n" + regions),
            cell("code", "%%writefile extract_region_stats.py\n" + script),
            cell("markdown", "## Sanity check: the archives open and a Z500 field over India looks like weather\n"),
            cell("code", '''import xarray as xr, numpy as np, matplotlib.pyplot as plt
S = {"token": "anon"}
ens = xr.open_zarr("gs://weatherbench2/datasets/ifs_ens/2018-2022-64x32_equiangular_conservative.zarr", storage_options=S, decode_timedelta=False)
print("levels:", ens.level.values, "| members:", ens.sizes["number"], "| lead index (hours):", ens.prediction_timedelta.values[:6], "...")
z = ens.geopotential.sel(level=500, time="2022-07-12T00").isel(prediction_timedelta=20, number=0).load()  # index 20 = 120 h = Day 5
z.transpose("latitude", "longitude").sel(latitude=slice(0, 45), longitude=slice(55, 110)).plot()
plt.title("IFS ENS member 0, Z500, init 2022-07-12 00Z, Day 5"); plt.show()
'''),
            cell("markdown", """## Extract (resumable; re-run this cell if Colab disconnects)

`YEARS` is the one thing worth changing. The archive holds 2018 to 2022 and the model is
limited by how few years it has, so extract all five unless you are short of time. Cost is
roughly 5 minutes per year on a normal CPU runtime. 2022 is the held-out test year and must
always be included.
"""),
            cell("code", 'YEARS = "2018 2019 2020 2021 2022"  # short on time? "2020 2021 2022"\n'),
            cell("code", "!python extract_region_stats.py --source ifs_ens --years {YEARS} --out /content/out\n"),
            cell("code", '''import pandas as pd
df = pd.read_parquet("/content/out/ifs_ens_z500_boxstats.parquet")
print(df.shape)
print("median spread by lead:", df.groupby("lead_days").ens_std.median().round(0).to_dict())
print("median |mean-truth| by lead:", (df.ens_mean-df.truth).abs().groupby(df.lead_days).median().round(0).to_dict())
'''),
            cell("markdown", """## Save to Google Drive

This is the cell that actually gets the file off the runtime. Mounting asks for
authorisation the first time. When it prints the path, open Drive, go to `vishwas/`, and
download `ifs_ens_z500_boxstats.parquet` into `vishwas/data/cache/` in the repo.
"""),
            cell("code", '''import os, shutil

SRC = "/content/out/ifs_ens_z500_boxstats.parquet"
assert os.path.exists(SRC), f"{SRC} is missing: the extract cell did not finish"

saved = None
try:
    from google.colab import drive
    drive.mount("/content/drive")                 # prompts for authorisation once
    dest = "/content/drive/MyDrive/vishwas"
    os.makedirs(dest, exist_ok=True)
    saved = shutil.copy(SRC, dest)
except Exception as e:                            # not on Colab, or the mount was declined
    print("Drive unavailable:", e)

if saved:
    print(f"saved to Drive: {saved}  ({os.path.getsize(saved) / 1e6:.1f} MB)")
    print("Download it from Drive > vishwas > into vishwas/data/cache/")
else:
    # Browser download, tried last: it is a silent no-op outside a real Colab tab, which
    # is the exact failure this cell exists to route around.
    try:
        from google.colab import files
        files.download(SRC)
        print("browser download started; if nothing happens, use the Drive route above")
    except Exception as e:
        print("no download route available:", e)
        print(f"the file is still on the runtime at {SRC}")
'''),
            cell("markdown", "## Optional bonus (only if the above finished fast): WeatherNext 2 archive for cross-model validation\n"),
            cell("code", '''# !python extract_region_stats.py --source fgn --years 2022 --out /content/out
# import shutil; print(shutil.copy("/content/out/fgn_z500_boxstats.parquet", "/content/drive/MyDrive/vishwas"))
'''),
        ],
    }
    out = ROOT / "notebooks/01-extract-region-stats.ipynb"
    out.write_text(json.dumps(nb, indent=1), encoding="utf-8")
    print("wrote", out)


if __name__ == "__main__":
    main()
