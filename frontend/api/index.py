"""The Bust Atlas of India, read-only JSON API.

Self-contained on purpose: this single file is what Vercel deploys as a Python
serverless function from the `frontend` project root, where neither `pipeline`
nor `backend` exists. It serves the same committed JSON the dashboard fetches,
from `frontend/public/data` (override with the env var BUST_ATLAS_DATA).

`backend/main.py` loads this file by path and re-exports `app`, so local runs,
tests and the deployment all execute exactly this code.
"""

from __future__ import annotations

import json
import math
import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

# --------------------------------------------------------------------------- data


def data_dir() -> Path:
    """Directory holding meta.json, atlas.json, inits.json, eval.json,
    case_studies.json and predictions/<init>.json."""
    env = os.environ.get("BUST_ATLAS_DATA")
    if env:
        return Path(env)
    return Path(__file__).resolve().parents[1] / "public" / "data"


@lru_cache(maxsize=512)
def load(relative: str) -> Any:
    """Read one JSON file once and keep it in memory. Path is validated."""
    path = (data_dir() / relative).resolve()
    root = data_dir().resolve()
    if root not in path.parents and path != root:
        raise HTTPException(status_code=404, detail="not found")
    if not path.is_file():
        raise HTTPException(status_code=404, detail=f"{relative} not found")
    return json.loads(path.read_text(encoding="utf-8"))


# ------------------------------------------------------------------------- models
# Copies of pipeline/schemas.py, kept here so the file has no repo imports.
# They document the OpenAPI schema; the file endpoints return the JSON verbatim.

Band = Literal["low", "moderate", "high", "severe"]


class RegionMeta(BaseModel):
    id: str = Field(description="Region id, e.g. gangetic_plain")
    label: str = Field(description="Human label")
    box: list[float] = Field(description="[lat0, lat1, lon0, lon1] in degrees")
    centroid: list[float] = Field(description="[lat, lon] in degrees")


class SeasonMeta(BaseModel):
    id: str = Field(description="DJF, MAM, JJAS or ON")
    label: str


class Meta(BaseModel):
    """meta.json: the contract every other file is read against."""

    product: str
    source: str = Field(description="Ensemble id the model was run on")
    source_label: str
    members: int = Field(description="Ensemble members")
    grid: str
    variable: str = Field(description="Forecast variable, e.g. z500")
    leads: list[int] = Field(description="Lead times in days, 1 to 10")
    years: dict[str, list[int]] = Field(description="train / cal / test year lists")
    regions: list[RegionMeta]
    state_to_region: dict[str, str]
    seasons: list[SeasonMeta]
    bust_definition: str
    bands: dict[str, float] = Field(description="Lower probability bound per band, 0 to 1")
    flag_threshold: float = Field(description="Probability at or above which a cell is flagged")
    generated_at: str = Field(description="ISO 8601 UTC")
    git_sha: str
    model: dict
    rules: dict[str, list[str]] = Field(
        description="feature -> [sentence if it raises risk, sentence if it lowers risk]"
    )
    season_words: dict[str, str]
    synthetic: bool = Field(default=False, description="True while running on fake data")


class WorstEvent(BaseModel):
    init: str
    error: float = Field(description="Absolute anomaly error, m2 s-2")


class AtlasCell(BaseModel):
    region: str
    lead: int = Field(description="Lead time, days")
    season: str
    n: int = Field(description="Forecasts in the cell")
    bust_rate: float = Field(description="Fraction of forecasts that busted, 0 to 1")
    err_p50: float = Field(description="Median absolute error, m2 s-2")
    err_p90: float = Field(description="m2 s-2")
    err_p95: float = Field(description="m2 s-2, the bust threshold")
    err_max: float = Field(description="m2 s-2")
    spread_p50: float = Field(description="Median ensemble standard deviation, m2 s-2")
    spread_p95: float = Field(description="m2 s-2")
    spread_skill: float = Field(description="Correlation of spread with error, -1 to 1")
    worst_events: list[WorstEvent]


class NationalCell(BaseModel):
    lead: int
    season: str
    n: int
    bust_rate: float
    err_p50: float
    err_p95: float


class Atlas(BaseModel):
    """atlas.json: the climatology, 10 regions x 10 leads x 4 seasons."""

    cells: list[AtlasCell]
    national: list[NationalCell]


class Inits(BaseModel):
    """inits.json: every initialisation time with a predictions file."""

    inits: list[str] = Field(description="YYYY-MM-DDTHH, 00Z only")


class ReliabilityBin(BaseModel):
    bin: int
    lo: float
    hi: float
    n: int
    mean_forecast: float | None
    observed_freq: float | None


class PRPoint(BaseModel):
    threshold: float
    precision: float | None
    recall: float | None


class Scores(BaseModel):
    brier: float = Field(description="Brier score, lower is better")
    bss_vs_climatology: float = Field(description="Brier skill score vs base rate")
    bss_vs_spread: float | None = Field(default=None, description="Brier skill score vs baseline")
    pr_auc: float = Field(description="Area under the precision recall curve")
    roc_auc: float
    reliability: list[ReliabilityBin]
    pr_curve: list[PRPoint]


class Eval(BaseModel):
    """eval.json: model vs spread baseline on the held out test years."""

    n: int
    positives: int
    base_rate: float
    model: Scores
    baseline: Scores
    by_lead: list[dict]
    by_region: list[dict]
    test_years: list[int]


class Narrative(BaseModel):
    setup: str
    flag: str
    why: str
    outcome: str


class CaseStudy(BaseModel):
    id: str
    title: str
    kind: Literal["bust", "verified"]
    init: str
    region: str
    lead: int
    prob: float
    narrative: Narrative


class CaseStudies(BaseModel):
    """case_studies.json: the guided replays."""

    cases: list[CaseStudy]


class Driver(BaseModel):
    feature: str = Field(description="Feature name, see meta.rules")
    contribution: float = Field(description="Signed contribution to the log odds")


class Outcome(BaseModel):
    error: float = Field(description="Verified absolute anomaly error, m2 s-2")
    threshold: float = Field(description="Bust threshold for this region, lead and season")
    busted: bool


class LeadPrediction(BaseModel):
    """One region at one lead time, plus the rendered forecaster's note."""

    lead: int = Field(description="Lead time, days, 1 to 10")
    prob: float = Field(description="Model bust probability, 0 to 1")
    baseline_prob: float = Field(description="Spread baseline probability, 0 to 1")
    band: Band = Field(description="low, moderate, high or severe")
    flag: bool = Field(description="True at or above meta.flag_threshold")
    std: float = Field(description="Ensemble standard deviation, m2 s-2")
    std_pct_climo: float = Field(description="Percentile of spread in the training climatology")
    cluster_gap: float = Field(description="Largest member gap in the central 80%, std units")
    jumpiness: float | None = Field(description="Change vs the previous run, m2 s-2")
    drivers: list[Driver]
    outcome: Outcome | None = Field(description="Null until the forecast has verified")
    sentences: list[str] = Field(description="The drivers rendered as plain English")


class Confidence(BaseModel):
    """Response of /api/confidence."""

    init: str = Field(description="Initialisation time, YYYY-MM-DDTHH")
    source: str = Field(description="Ensemble the prediction came from")
    lead: int = Field(description="Lead time, days")
    regions: dict[str, LeadPrediction] = Field(description="region id -> prediction")


class Health(BaseModel):
    ok: bool
    inits: int = Field(description="Number of initialisation times served")
    synthetic: bool = Field(description="True while running on fake data")


# ------------------------------------------------------------------------ sentences


def season_of(init: str) -> str:
    """Season code of the init month, matching pipeline/seasons.py."""
    month = int(init[5:7])
    if month == 12 or month <= 2:
        return "DJF"
    if month <= 5:
        return "MAM"
    if month <= 9:
        return "JJAS"
    return "ON"


def driver_sentence(
    meta: dict, feature: str, contribution: float, lead: int, season: str, std_pct: float
) -> str:
    """Fill a meta.rules template. Mirrors frontend/src/data/text.ts."""
    rule = meta["rules"].get(feature)
    if not rule:
        return feature
    tpl = rule[0] if contribution > 0 else rule[1]
    pct = max(1, math.floor((1.0 - std_pct) * 100 + 0.5))
    return (
        tpl.replace("{lead}", str(lead))
        .replace("{lead_prev}", str(max(lead - 1, 1)))
        .replace("{season}", meta["season_words"].get(season, "this season"))
        .replace("{pct}", str(pct))
    )


def forecaster_note(meta: dict, lp: dict, season: str) -> list[str]:
    return [
        driver_sentence(
            meta, d["feature"], d["contribution"], lp["lead"], season, lp["std_pct_climo"]
        )
        for d in lp["drivers"]
    ]


# ----------------------------------------------------------------------------- app

app = FastAPI(
    title="Vishwas, The Bust Atlas of India",
    version="1.0.0",
    description=(
        "Read-only API over the committed forecast bust confidence data. "
        "Every response is the same JSON the dashboard reads, so the "
        "deliverable is both a dashboard and an API."
    ),
    docs_url="/api/docs",
    redoc_url=None,
    openapi_url="/api/openapi.json",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


def verbatim(relative: str) -> JSONResponse:
    return JSONResponse(content=load(relative))


@app.get("/api/meta", responses={200: {"model": Meta}}, summary="Contract and configuration")
def get_meta() -> JSONResponse:
    return verbatim("meta.json")


@app.get("/api/atlas", responses={200: {"model": Atlas}}, summary="Bust climatology")
def get_atlas() -> JSONResponse:
    return verbatim("atlas.json")


@app.get("/api/inits", responses={200: {"model": Inits}}, summary="Available init times")
def get_inits() -> JSONResponse:
    return verbatim("inits.json")


@app.get("/api/eval", responses={200: {"model": Eval}}, summary="Model vs baseline scores")
def get_eval() -> JSONResponse:
    return verbatim("eval.json")


@app.get(
    "/api/case-studies", responses={200: {"model": CaseStudies}}, summary="Guided case replays"
)
def get_case_studies() -> JSONResponse:
    return verbatim("case_studies.json")


@app.get("/api/regions", responses={200: {"model": list[RegionMeta]}}, summary="The 10 regions")
def get_regions() -> JSONResponse:
    return JSONResponse(content=load("meta.json")["regions"])


@app.get("/api/health", response_model=Health, summary="Liveness and data summary")
def get_health() -> Health:
    meta = load("meta.json")
    return Health(ok=True, inits=len(load("inits.json")["inits"]), synthetic=meta["synthetic"])


@app.get(
    "/api/confidence",
    response_model=Confidence,
    summary="Bust probability per region at one lead time",
)
def get_confidence(
    init: str = Query(description="Initialisation time, YYYY-MM-DDTHH, from /api/inits"),
    lead: int = Query(description="Lead time in days, 1 to 10"),
    region: str | None = Query(default=None, description="Region id, omit for all 10"),
) -> Confidence:
    meta = load("meta.json")
    if lead not in meta["leads"]:
        raise HTTPException(status_code=422, detail=f"lead must be one of {meta['leads']}")
    if not init.replace("-", "").replace("T", "").isdigit():
        raise HTTPException(status_code=404, detail=f"unknown init {init}")
    try:
        pred = load(f"predictions/{init}.json")
    except HTTPException:
        raise HTTPException(status_code=404, detail=f"unknown init {init}") from None
    if region is not None and region not in pred["regions"]:
        raise HTTPException(status_code=404, detail=f"unknown region {region}")

    season = season_of(init)
    out: dict[str, LeadPrediction] = {}
    for region_id, rp in pred["regions"].items():
        if region is not None and region_id != region:
            continue
        for lp in rp["leads"]:
            if lp["lead"] == lead:
                out[region_id] = LeadPrediction(
                    **lp, sentences=forecaster_note(meta, lp, season)
                )
                break
    return Confidence(init=pred["init"], source=pred["source"], lead=lead, regions=out)
