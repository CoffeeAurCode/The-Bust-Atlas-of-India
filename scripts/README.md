# scripts/

One-shot CLIs. Each has a docstring saying what it writes.

- `extract_region_stats.py` — runs in Colab. WB2 Zarr → `data/cache/<source>_<var>_boxstats.parquet`
- `make_synthetic_boxstats.py` — fake Parquet with the real schema, for building the pipeline before extraction finishes
- `export_json.py` — `data/artifacts/*` → `frontend/public/data/*.json`
- `fetch_openmeteo_wn2.py` — live WN2 pull → `frontend/public/data/live.json` (next sprint)
