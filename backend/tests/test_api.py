"""The API must return exactly what is on disk, and nothing more."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "frontend" / "public" / "data"

pytestmark = pytest.mark.skipif(
    not (DATA / "meta.json").is_file(),
    reason="frontend/public/data not built; run scripts/run_pipeline.py",
)

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def read(relative: str) -> dict:
    return json.loads((DATA / relative).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient

    from backend.main import app

    return TestClient(app)


@pytest.mark.parametrize(
    ("route", "filename"),
    [
        ("/api/meta", "meta.json"),
        ("/api/atlas", "atlas.json"),
        ("/api/inits", "inits.json"),
        ("/api/eval", "eval.json"),
        ("/api/case-studies", "case_studies.json"),
    ],
)
def test_files_served_verbatim(client, route: str, filename: str) -> None:
    r = client.get(route)
    assert r.status_code == 200
    assert r.json() == read(filename)


def test_regions(client) -> None:
    r = client.get("/api/regions")
    assert r.status_code == 200
    assert r.json() == read("meta.json")["regions"]
    assert len(r.json()) == 10


def test_health(client) -> None:
    meta = read("meta.json")
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {
        "ok": True,
        "inits": len(read("inits.json")["inits"]),
        "synthetic": meta["synthetic"],
    }


def test_confidence_matches_disk_and_renders_sentences(client) -> None:
    init = read("inits.json")["inits"][0]
    lead = 5
    on_disk = read(f"predictions/{init}.json")

    r = client.get("/api/confidence", params={"init": init, "lead": lead})
    assert r.status_code == 200
    body = r.json()
    assert body["init"] == on_disk["init"]
    assert body["source"] == on_disk["source"]
    assert body["lead"] == lead
    assert len(body["regions"]) == 10

    for region_id, lp in body["regions"].items():
        expected = next(
            x for x in on_disk["regions"][region_id]["leads"] if x["lead"] == lead
        )
        assert {k: v for k, v in lp.items() if k != "sentences"} == expected
        assert len(lp["sentences"]) == 3
        for s in lp["sentences"]:
            assert s and "{" not in s
            if "Day " in s:
                assert f"Day {lead}" in s or f"Day {lead - 1}" in s

    joined = " ".join(s for lp in body["regions"].values() for s in lp["sentences"])
    assert f"Day {lead}" in joined


def test_confidence_single_region(client) -> None:
    init = read("inits.json")["inits"][0]
    r = client.get("/api/confidence", params={"init": init, "lead": 1, "region": "central"})
    assert r.status_code == 200
    assert list(r.json()["regions"]) == ["central"]


def test_response_validates_against_pipeline_schema(client) -> None:
    from pipeline.schemas import LeadPrediction

    init = read("inits.json")["inits"][0]
    body = client.get("/api/confidence", params={"init": init, "lead": 3}).json()
    for lp in body["regions"].values():
        model = LeadPrediction.model_validate(lp)
        assert model.lead == 3
        assert 0.0 <= model.prob <= 1.0


def test_errors(client) -> None:
    init = read("inits.json")["inits"][0]
    assert client.get("/api/confidence", params={"init": "1999-01-01T00", "lead": 1}).status_code == 404
    assert client.get("/api/confidence", params={"init": init, "lead": 11}).status_code == 422
    assert client.get("/api/confidence", params={"init": init, "lead": 0}).status_code == 422
    assert (
        client.get("/api/confidence", params={"init": init, "lead": 1, "region": "narnia"}).status_code
        == 404
    )


def test_openapi_documents_units(client) -> None:
    spec = client.get("/api/openapi.json").json()
    assert "/api/confidence" in spec["paths"]
    props = spec["components"]["schemas"]["LeadPrediction"]["properties"]
    assert "description" in props["std"]
    assert client.get("/api/docs").status_code == 200
