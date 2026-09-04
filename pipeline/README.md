# pipeline/

Pure-Python package operating on the box-stats Parquet. No Zarr access here; that lives in `scripts/extract_region_stats.py`.

Planned modules (create as needed):

- `regions.py`   — 10 India lat/lon boxes + area-weighted box mean
- `labels.py`    — p95 per box × lead × season on 2018–2021; `bust` column
- `baseline.py`  — spread-threshold classifier + eval
- `features.py`  — Tier 0/1/2 features; docstring lists the leakage guarantee for each
- `model.py`     — LightGBM + isotonic; train 2018–2020, calibrate 2021, test 2022
- `explain.py`   — SHAP top-k → meteorological sentences via a rule table
- `eval.py`      — Brier, BSS, PR-AUC, ROC-AUC, reliability bins; cross-model runner

Temporal split is fixed: train 2018–2020, calibrate 2021, test 2022 (matches the FGN 2022 archive).
