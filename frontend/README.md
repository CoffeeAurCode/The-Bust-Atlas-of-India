# frontend/ — The Bust Atlas of India

React 18 + Vite + TypeScript. SVG map via d3-geo over a bundled India subdivisions GeoJSON. No tiles, no runtime network: all data is static JSON in `public/data/`, exported by `../scripts/export_json.py`. Runs offline from `npm run preview`.

Modes: **Atlas** (historical bust climatology by season × lead, needs no model), **Today** (bust probability per region for a chosen init, why-panel, lead curve, jumpiness, source badge), **Evidence** (reliability, PR curve, BSS vs baseline), **Case study** replay.

Honesty rule: the model runs on 10 homogeneous regions; subdivision polygons are painted by parent region and the legend says so.

Before writing code: load the `design-taste-frontend` skill. Bar: an instrument, not a dashboard.

`public/data/` is committed: it is what Vercel serves. Keep it under 16 MB (enforced by `pipeline/tests/test_export.py`). Vercel project root is this folder.
