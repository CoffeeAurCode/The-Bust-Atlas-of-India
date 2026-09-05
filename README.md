# Vishwas — The Bust Atlas of India

**A confidence layer for medium-range weather forecasts.** It reads any ensemble at issue time and predicts, for each Indian region and each lead day from 1 to 10, the probability that the forecast will *bust* — with a plain-language note saying why.

Live: **https://the-bust-atlas-of-india.vercel.app**

SIH26079, Ministry of Earth Sciences / NCMRWF. Team Gryffindor. Decision support for forecasters, not a replacement for IMD's official bulletin.

The forecast is not our contribution. The confidence layer is. Nothing here works on only one ensemble.

---

## The result in one table

Test year 2022, never seen during training. 73,000 region-lead forecasts, 4,285 of them busts, base rate 5.9%.

| | Brier | BSS vs climatology | PR-AUC | ROC-AUC |
|---|---|---|---|---|
| spread-only baseline | 0.0543 | 0.017 | 0.097 | 0.655 |
| **this system** | **0.0539** | **0.024** | **0.113** | **0.663** |

And the operational number, which matters more than any of the above:

> **Regions flagged unreliable bust 17.3% of the time. Unflagged regions bust 5.6% of the time. A 3.1x lift, on 3.5% of forecasts.**

Trained on ECMWF IFS ENS, then scored **unchanged** on Google WeatherNext 2 (64 members): PR-AUC 0.314 against a 0.253 baseline. Nothing was refitted. That is the ensemble-agnostic claim demonstrated rather than asserted.

---

# How to read the data

Everything in the product is one number asked four ways: **for one region, on one lead day, from one forecast run, how likely is this forecast to bust?**

## 1. What a "bust" is, and why the bar moves

A bust is **not** "the forecast was wrong". It is **relative**:

> A forecast is a bust if its error exceeds the **95th percentile** of the error distribution for that same **region**, **lead day** and **season**, measured on the development years only.

The conditioning is the whole design, and it is the thing most people miss at first. Look at what the bust line (`err_p95`) does as lead time grows — North-West India, winter:

| lead | median error | `err_p95` = the bust line | bust rate |
|---|---|---|---|
| Day 1 | 18.1 | **55.5** | 0.052 |
| Day 3 | 32.1 | **113.9** | 0.052 |
| Day 5 | 64.3 | **193.4** | 0.052 |
| Day 7 | 100.8 | **330.0** | 0.052 |
| Day 10 | 187.6 | **571.5** | 0.052 |

(units are m² s⁻², the units of 500 hPa geopotential)

**The bust line rises 10x from Day 1 to Day 10 — and the bust rate does not move at all.** That is not a coincidence, it is the definition: the threshold is a percentile, so about 5% of forecasts sit above it *by construction*, at every lead.

The same holds across seasons. Day 10, North-West India:

| season | `err_p95` | bust rate |
|---|---|---|
| DJF (winter) | 571.5 | 0.052 |
| MAM (pre-monsoon) | 381.8 | 0.052 |
| JJAS (monsoon) | 272.9 | 0.051 |
| ON (post-monsoon) | 386.7 | 0.053 |

Winter needs an error twice the size of the monsoon's to count as a bust, because winter westerlies are simply more variable than the monsoon. The bar moves; the meaning stays fixed.

**So "bust" always means the same thing: unusually bad for these circumstances.** A 220 unit error at Day 10 in winter is an ordinary forecast. The same error at Day 1 would be a disaster. Because the threshold is conditioned, Day 1 and Day 10 risks are directly comparable — which is what makes a single map with a lead slider honest.

## 2. Lead time

Lead time is how far ahead a forecast reaches. Day 1 is tomorrow, Day 10 is ten days out — **all issued at the same moment, from the same model run.** A Day 10 forecast issued 25 January is the forecast for 4 February.

Skill decays with lead. In this archive, median error grows from 21 to 82 units between Day 1 and Day 10, spread grows from 22 to 115, and the flags follow: at Day 2 only 2 region-forecasts across all of 2022 were flagged unreliable; at Day 10, 314 were.

## 3. Which years each tab shows

This trips people up, so it is worth stating plainly. The three-year archive is split, and **the tabs deliberately show different parts of it**:

| | years | what it is |
|---|---|---|
| **Atlas** | 2020 + 2021 | the **development** years. History: what *has* happened. |
| **Today** | 2022 | the **test** year. Forecasts, on data the model never saw. |
| **Evidence** | 2022 | scores on that same unseen test year. |
| **Cases** | 2022 | three worked examples drawn from the test year. |

Everything the model learned — the bust thresholds, the training statistics, the calibration — comes from 2020 and 2021 only. 2022 was held back entirely. That separation is why the Evidence numbers mean anything.

## 4. Today tab — the forecast

**"Archive 2022"** means you are replaying the real ECMWF IFS ENS runs from the test year, one file per day, 365 of them. Pick a date and you see what the system would have said that morning — and, because the year is over, whether it was right. That is the point of using the archive: **you get the outcome.** A live forecast cannot show you that for another ten days.

**"Live (WeatherNext 2)"** is the other source toggle: a real current run of Google WeatherNext 2 (64 members) pulled from Open-Meteo. It proves the pipeline runs on today's data and on a completely different model, but it has no outcome yet.

Reading one region on one day:

```
prob 0.177   baseline_prob 0.126   band "high"   flag true
std 540.8    std_pct_climo 1.0     cluster_gap 0.21
outcome: error 220.3, threshold 571.5, busted false
```

- **`prob`** — the answer. 17.7% chance this forecast busts.
- **`baseline_prob`** — what ensemble spread alone would have said (12.6%). The gap is what the layer adds.
- **`band` / `flag`** — bands are `low` under 5%, `moderate` 5 to 15%, `high` 15 to 30%, `severe` above 30%. At or above 15% the region is flagged unreliable and drawn with hatching.
- **`std`** — raw ensemble spread. **`std_pct_climo`** — where that spread sits in this region/lead/season's own history. 1.0 means the top of the range: today's ensemble disagrees as much as it ever does here.
- **`outcome`** — only in archive mode. Error 220.3 against a threshold of 571.5, so no bust.

**On that last point:** the system said 17.7% and no bust followed. That is not a miss. 17.7% means it should *not* bust most of the time. A single probability can never be graded — only a set of them can, which is what Evidence is for.

**`severe` never appears in practice.** The system tops out near 18%. At ROC 0.663 it has not earned the right to claim 30%, and it does not.

## 5. The forecaster's note

The note is generated from per-feature contributions — what pushed this particular probability up or down. In the example above, `std_pct_climo` contributes 0.84 and everything else is a rounding error.

That is the honest picture system-wide. Single-feature skill on the test year: `std_pct_climo` ROC 0.655, `base_rate` 0.585, and `anom` 0.381 — informative *inverted*, meaning strong anomalies bust **less** often. `cluster_gap` (0.497) and `tail` (0.508) are noise on Z500.

The note is an attribution of the model's own reasoning, not an independent meteorological diagnosis. Say so.

## 6. Atlas tab — the history

Atlas is **climatology, not a forecast.** It answers "where and when do forecasts usually go wrong?" from the 2020-2021 development years. 400 cells: 10 regions x 10 lead days x 4 seasons. A cell:

```
north_west / Day 10 / DJF:  n 362
err_p50 187.6   err_p95 571.5   err_max 884.4
bust_rate 0.0525
spread_p50 265.9   spread_skill 1.417
```

- **`n`** — forecasts in this cell. 362 = two winters of runs at 00Z and 12Z.
- **`err_p50`** — the typical error. **`err_p95`** — **the bust line itself**, the same number Today mode compares against. Atlas shows you where the bar is; Today tells you the chance of clearing it.
- **`err_max`** — the worst single forecast on record here (884.4, over 4x the typical error). The `worst_events` list names the dates.
- **`bust_rate`** — near 0.05 in every cell, by construction. Where it drifts above, that region-lead-season busts more than its own history predicts.
- **`spread_skill`** — spread divided by error. **This is the one worth understanding.** Above 1 means the ensemble is **over-dispersive**: it spreads wider than its own errors justify, so it cries wolf. At 1.42 here, spread alone systematically overstates the risk at long leads — and that gap is exactly what the confidence layer exploits.

## 7. Evidence tab — does it work

- **Brier score** — mean squared error of the probabilities, lower better. Nearly meaningless alone: always predicting 5.9% scores well simply because busts are rare.
- **Brier skill score vs climatology** — improvement over always guessing the base rate.
- **PR-AUC** — the one that matters when positives are rare. Random guessing scores 0.059, the base rate. Baseline 0.097, this system 0.113.
- **ROC-AUC** — 0.663: pick one bust and one non-bust at random, and the system ranks the bust higher 66% of the time.
- **Reliability diagram** — when it says 15%, does it bust 15% of the time? Points on the diagonal are honest probabilities. The top decile predicts 14.6% and observes 15.5%.
- **Precision-recall curve** — the flat line is the no-skill base rate.

**Every number is quoted against the spread-only baseline, never against zero.** Forecasters already have ensemble spread. Beating random guessing would be worthless; beating the spread they already have is the claim. Plain accuracy is never reported — at a 5.9% base rate, "never busts" scores 94%.

## 8. Cases tab

Three worked examples from 2022: two busts the system flagged, and one long-range forecast it said to trust, which held. Four steps each, ending in the verified outcome, with a deep link onto the map.

## 9. The regions

Ten boxes, one of them ocean:

| region | latitude | longitude |
|---|---|---|
| Western Himalaya | 30 to 37 N | 73 to 80 E |
| North-West India | 23 to 30 N | 68 to 77 E |
| Indo-Gangetic Plain | 24 to 30 N | 77 to 88 E |
| North-East India | 22 to 29 N | 88 to 97 E |
| Central India | 18 to 24 N | 74 to 84 E |
| West Coast | 12 to 20 N | 72 to 76 E |
| East Coast | 14 to 22 N | 80 to 88 E |
| Peninsular Interior | 12 to 18 N | 76 to 80 E |
| South Peninsula | 8 to 13 N | 76 to 80 E |
| Bay of Bengal | 10 to 20 N | 85 to 95 E |

The grid is 64x32, about 5.6 degrees, so IMD's 36 meteorological subdivisions would be meaningless on it. The map paints each state in the colour of its parent region and draws the boxes, so the real unit is always visible. Bay of Bengal is included because that is where the cyclones form.

**Variable: Z500 only** — 500 hPa geopotential height, the mid-level steering flow. It is the standard field for synoptic-scale pattern busts. Rainfall, Tmax and cyclone track are upgrades, not claims.

---

## Running it

```
uv venv --python 3.12
uv pip install -r requirements.txt
.venv\Scripts\python -m pytest -q                                   # 73 tests

.venv\Scripts\python scripts\run_pipeline.py --input data\cache\ifs_ens_z500_boxstats.parquet
.venv\Scripts\python scripts\pick_case_studies.py
.venv\Scripts\python scripts\cross_model.py --input data\cache\fgn_z500_boxstats.parquet

cd frontend && npm install
npm run dev                 # localhost:5173
npm run typecheck && npm test && npm run build && npm run e2e
```

The heavy extraction runs once in Colab (`notebooks/01-extract-region-stats.ipynb`, about 5 minutes per year of archive) and produces a small Parquet of per-region ensemble statistics. It writes the result to Google Drive at `MyDrive/vishwas/`, not through the browser: `google.colab.files.download()` is a silent no-op when the notebook is driven from VS Code rather than a real Colab tab. Everything after that runs on a laptop, offline. `npm run preview` serves the whole app with the network unplugged.

## Data

Public WeatherBench 2 bucket (`gs://weatherbench2/`), no auth:

- `datasets/ifs_ens/2018-2022-64x32_equiangular_conservative.zarr` — ECMWF IFS ENS, 50 members. Training.
- `datasets/fgn/2022-64x32_equiangular_conservative.zarr` — Google WeatherNext 2, 64 members. Cross-model validation.
- `datasets/era5/1959-2023_01_10-6h-64x32_equiangular_conservative.zarr` — ERA5 truth.
- `datasets/era5-hourly-climatology/1990-2019_6h_64x32_equiangular_conservative.zarr` — climatology.

Live path pulls Google WeatherNext 2 from Open-Meteo, no key.

## The data contract

`data/cache/<source>_z500_boxstats.parquet`, one row per `init x lead_days x region`:

```
source, init, lead_days, region, var,
ens_mean, ens_std, q10, q25, q50, q75, q90, cluster_gap, truth, climo
```

**The model never sees anything else.** Any ensemble that can produce this table works, which is what makes the layer ensemble-agnostic. `cluster_gap` is the largest gap between adjacent sorted members within the central 80%, in standard deviations — about 0.2 to 0.3 for a Gaussian ensemble, above 1 when the members have split into two camps.

## Layout

```
vishwas/
├── pipeline/     regions, seasons, labels, atlas, features, baseline, model,
│                 calibrate, explain, eval, schemas  (pure Python over the Parquet)
├── scripts/      extract_region_stats (Colab) · run_pipeline · pick_case_studies ·
│                 cross_model · validate_boxstats · prepare_geojson
├── notebooks/    01-extract-region-stats.ipynb (generated)
├── frontend/     Vite + React + TypeScript. The Bust Atlas of India. Vercel root.
├── backend/      thin FastAPI over the same JSON artifacts
└── data/         gitignored: raw/ cache/ artifacts/
```

## Honest limitations

- **Three years of archive is the binding constraint** (2020-2022). More training years is the single highest-value improvement available.
- **Skill is concentrated in one feature.** Ensemble spread percentile does most of the work; several engineered features are noise on Z500.
- **Z500 only.** Not rainfall, not temperature, not cyclone track.
- **ERA5 is the truth source.** IMDAA and IMD Pune gridded observations would be better over India.
- **The `severe` band is unreachable** at current skill, and the thresholds have not been tuned to make it light up.
