"""JSON contract between the pipeline and the frontend. Every exported file validates
against one of these models, and frontend/src/data/schema.json is generated from them.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Band = Literal["low", "moderate", "high", "severe"]


class RegionMeta(BaseModel):
    id: str
    label: str
    box: list[float] = Field(description="[lat0, lat1, lon0, lon1]")
    centroid: list[float] = Field(description="[lat, lon]")


class SeasonMeta(BaseModel):
    id: str
    label: str


class Meta(BaseModel):
    product: str
    source: str
    source_label: str
    members: int
    grid: str
    variable: str
    leads: list[int]
    years: dict[str, list[int]]
    regions: list[RegionMeta]
    seasons: list[SeasonMeta]
    bust_definition: str
    bands: dict[str, float] = Field(description="lower prob bound per band")
    flag_threshold: float
    generated_at: str
    git_sha: str
    model: dict
    rules: dict[str, list[str]] = Field(description="feature -> [sentence if raises risk, sentence if lowers]")
    season_words: dict[str, str]
    synthetic: bool = False


class WorstEvent(BaseModel):
    init: str
    error: float


class AtlasCell(BaseModel):
    region: str
    lead: int
    season: str
    n: int
    bust_rate: float
    err_p50: float
    err_p90: float
    err_p95: float
    err_max: float
    spread_p50: float
    spread_p95: float
    spread_skill: float
    worst_events: list[WorstEvent]


class NationalCell(BaseModel):
    lead: int
    season: str
    n: int
    bust_rate: float
    err_p50: float
    err_p95: float


class Atlas(BaseModel):
    cells: list[AtlasCell]
    national: list[NationalCell]


class Inits(BaseModel):
    inits: list[str]


class Driver(BaseModel):
    feature: str
    contribution: float


class Outcome(BaseModel):
    error: float
    threshold: float
    busted: bool


class LeadPrediction(BaseModel):
    lead: int
    prob: float
    baseline_prob: float
    band: Band
    flag: bool
    std: float
    std_pct_climo: float
    cluster_gap: float
    jumpiness: float | None
    drivers: list[Driver]
    outcome: Outcome | None


class RegionPrediction(BaseModel):
    leads: list[LeadPrediction]


class Prediction(BaseModel):
    init: str
    source: str
    regions: dict[str, RegionPrediction]


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
    brier: float
    bss_vs_climatology: float
    bss_vs_spread: float | None = None
    pr_auc: float
    roc_auc: float
    reliability: list[ReliabilityBin]
    pr_curve: list[PRPoint]


class Eval(BaseModel):
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
    cases: list[CaseStudy]


ALL = {
    "meta.json": Meta,
    "atlas.json": Atlas,
    "inits.json": Inits,
    "eval.json": Eval,
    "case_studies.json": CaseStudies,
}
