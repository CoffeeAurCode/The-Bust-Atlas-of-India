"""Vishwas pipeline: labels, Bust Atlas, features, model, explanations, export.

Everything here operates on the box-stats Parquet contract (see README) and never
touches the Zarr archives; that lives in scripts/extract_region_stats.py.
"""
