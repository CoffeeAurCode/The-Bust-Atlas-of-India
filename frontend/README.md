# frontend/ — The Bust Atlas of India

React 18 + Vite + TypeScript. SVG map via d3-geo over a 93 KB India states GeoJSON. No tiles, no runtime network: all data is static JSON in `public/data/`, exported by `../scripts/run_pipeline.py`. Runs offline from `npm run preview`. Deployed on Vercel with this folder as the project root.

```
npm install
npm run dev          # http://localhost:5173
npm run build && npm run preview
npm run typecheck    # tsc
npm test             # vitest: contract tests against public/data
npm run e2e          # playwright: offline smoke + screenshots
```

## Modes

| Mode | URL | What it shows |
|---|---|---|
| Atlas | `/?mode=atlas&season=JJAS&lead=5` | Historical bust rate or p95 error per region for a season and lead. Click a region for its record. |
| Today | `/?mode=today&init=2022-07-12T00&lead=6&region=central` | Bust probability per region for a chosen issue date; forecaster's note, lead curve, run-to-run change, outcome. |
| Evidence | `/?mode=evidence` | Reliability, precision-recall, scores against the spread-only baseline, method. |
| Cases | `/?mode=cases&case=<id>` | Guided replay of case studies. |

Every view is linkable; state lives in the URL.

## Layout

```
src/
  data/       schema.ts (zod contract), api.ts (loaders), text.ts (sentence templates), scale.ts (risk ramp)
  state/      url.ts (URL <-> state)
  components/ IndiaMap.tsx, controls.tsx, charts.tsx
  modes/      AtlasMode, TodayMode, EvidenceMode, CasesMode
  styles/     tokens.css (light/dark), global.css
public/data/  meta.json atlas.json inits.json eval.json case_studies.json india.geojson predictions/<init>.json
```

## Honesty rules baked in

- The model runs on 10 homogeneous regions (5.6° grid). States are shaded by parent region; region boxes are drawn as dashed hairlines; the legend says so.
- `meta.synthetic = true` shows a "synthetic data" badge everywhere. It goes away when the pipeline runs on the real Parquet.
- The basemap must be run through `../scripts/prepare_geojson.py` (d3-geo needs clockwise exterior rings).
