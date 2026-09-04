# Vishwas — forecast bust detection (SIH26079, Team Gryffindor)

A model-agnostic confidence layer for medium-range ensemble forecasts. Reads any ensemble at issue time and predicts, per Indian region and lead time (Day 1–10), the probability that the forecast will *bust*, with a plain-language meteorological explanation.

Problem statement: SIH26079, Ministry of Earth Sciences / NCMRWF. Decision support for forecasters; not a replacement for IMD's official bulletin.

## Layout

```
vishwas/
├── pipeline/     regions, labels, baseline, features, model, explain, eval  (pure Python over Parquet)
├── app/          Streamlit dashboard: map, lead slider, why panel, eval, case studies
├── backend/      thin FastAPI over the same artifacts
├── scripts/      extract_region_stats (Colab) · export_artifacts · fetch_openmeteo_wn2
├── notebooks/    Colab notebooks, numbered
├── frontend/     reserved; empty on the fast path
└── data/         gitignored: raw/ cache/ artifacts/
```

## Setup

```
uv venv --python 3.12
.venv\Scripts\activate            # PowerShell;  source .venv/bin/activate on bash
uv pip install -r requirements.txt
streamlit run app/streamlit_app.py
```

`requirements.txt` does not exist yet. First person to create it updates this README.

## Data

Training and validation archives come from the public WeatherBench 2 bucket (`gs://weatherbench2/`), no auth:

- `datasets/ifs_ens/2018-2022-64x32_equiangular_conservative.zarr` — ECMWF IFS ENS, 50 members (training)
- `datasets/fgn/2022-64x32_equiangular_conservative.zarr` — Google WeatherNext 2, 64 members (cross-model validation)
- `datasets/era5/1959-2022-6h-64x32_equiangular_conservative.zarr` and `datasets/era5-hourly-climatology/1990-2019_6h_64x32_equiangular_conservative.zarr` — truth and climatology

Live demo pulls Google WeatherNext 2 from Open-Meteo. The heavy extraction runs once in Colab and produces a small Parquet of per-region ensemble statistics; everything else runs on a laptop, offline.

## The bust definition

For region R, variable V and lead L, a forecast is a bust if its error exceeds the 95th percentile of the error distribution for that same region, variable, lead and season, computed on training years only.

## Data contract

`data/cache/<source>_<var>_boxstats.parquet`, one row per `init × lead × box`, columns: `source, init, lead_days, box, var, ens_mean, ens_std, q10, q25, q50, q75, q90, cluster_gap, truth, climo`. The model never sees anything else, which is what makes it ensemble-agnostic.
