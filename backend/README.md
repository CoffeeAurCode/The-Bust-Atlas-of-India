# backend/

FastAPI over the committed JSON in `frontend/public/data`, so the deliverable is
both a dashboard and an API (PS outcome 5). Read only, no database, no model at
request time: the pipeline has already written every answer to disk.

## Run it locally

```
cd vishwas
.venv\Scripts\python -m uvicorn backend.main:app --reload --port 8000
```

Then open http://localhost:8000/api/docs for the OpenAPI page, or:

```
curl http://localhost:8000/api/health
curl "http://localhost:8000/api/confidence?init=2022-01-01T00&lead=5&region=central"
```

Tests: `.venv\Scripts\python -m pytest -q backend/tests`.

## Endpoints

| Route | Returns |
|---|---|
| `GET /api/meta` | `meta.json` verbatim: regions, seasons, bands, rule templates |
| `GET /api/atlas` | `atlas.json` verbatim: 400 climatology cells plus the national summary |
| `GET /api/inits` | `inits.json` verbatim: every initialisation time available |
| `GET /api/eval` | `eval.json` verbatim: model vs spread baseline on the test years |
| `GET /api/case-studies` | `case_studies.json` verbatim |
| `GET /api/regions` | the 10 region boxes from `meta.json` |
| `GET /api/health` | `{ok, inits, synthetic}` |
| `GET /api/confidence?init=&lead=&region=` | per region prediction at one lead, with the forecaster's note already rendered from `meta.rules` |

`/api/confidence` returns 404 for an unknown init or region and 422 for a lead
outside `meta.leads`. CORS is open: the data is public and read only.

## Where the code lives

The app is one self-contained file, `frontend/api/index.py`. `backend/main.py`
loads it by path and re-exports `app`, so there is only one copy of the routes.
The data directory is `frontend/public/data` by default; override it with the
env var `BUST_ATLAS_DATA`.

## How it deploys on Vercel

The Vercel project root is `frontend`, so `backend/` and `pipeline/` are not
uploaded. That is why the app is self-contained in `frontend/api/index.py`:

- Vercel maps each `.py` file in `/api` to a route and loads a top-level `app`
  as an ASGI application, so `api/index.py` serves `/api`. Python 3.12 is the
  default runtime, so no `functions.runtime` entry is needed.
- `frontend/requirements.txt` gives the function its dependency (`fastapi`).
  Uvicorn is not needed: Vercel runs the ASGI app itself.
- File based routing only serves `/api` exactly, so `frontend/vercel.json`
  rewrites `/api/(.*)` to `/api/index`. The original path is preserved, which is
  why the routes are declared with their `/api/...` prefixes.
- The SPA rewrite already excludes `/api/`, so the static site is untouched.
- The JSON under `frontend/public/data` is committed and ships with the
  deployment, so the function reads it from disk with no network calls.

Docs: https://vercel.com/docs/functions/runtimes/python and
https://vercel.com/docs/functions/runtimes/python/api-directory
