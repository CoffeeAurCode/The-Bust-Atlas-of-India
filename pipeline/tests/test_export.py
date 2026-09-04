"""Validates whatever is currently in frontend/public/data against the contract.
Skips if the pipeline has not been run yet."""

import json
from pathlib import Path

import pytest

from pipeline import schemas
from pipeline.regions import REGIONS

DATA = Path(__file__).resolve().parents[2] / "frontend/public/data"


@pytest.fixture(scope="module")
def data_dir():
    if not (DATA / "meta.json").exists():
        pytest.skip("run scripts/run_pipeline.py first")
    return DATA


def test_top_level_files_validate(data_dir):
    for name, model in schemas.ALL.items():
        if name == "case_studies.json" and not (data_dir / name).exists():
            continue
        model.model_validate_json((data_dir / name).read_text(encoding="utf-8"))


def test_atlas_has_400_cells(data_dir):
    atlas = schemas.Atlas.model_validate_json((data_dir / "atlas.json").read_text(encoding="utf-8"))
    assert len(atlas.cells) == 400
    assert len(atlas.national) == 40
    assert all(0 <= c.bust_rate <= 1 for c in atlas.cells)


def test_every_init_has_a_complete_prediction_file(data_dir):
    inits = schemas.Inits.model_validate_json((data_dir / "inits.json").read_text(encoding="utf-8")).inits
    meta = schemas.Meta.model_validate_json((data_dir / "meta.json").read_text(encoding="utf-8"))
    assert len(inits) > 0
    files = {p.stem for p in (data_dir / "predictions").glob("*.json")}
    assert set(inits) == files
    for key in inits[:: max(1, len(inits) // 25)]:  # sample ~25 files
        doc = schemas.Prediction.model_validate_json((data_dir / "predictions" / f"{key}.json").read_text(encoding="utf-8"))
        assert set(doc.regions) == set(REGIONS)
        for r in doc.regions.values():
            assert [x.lead for x in r.leads] == meta.leads
            assert all(0 <= x.prob <= 1 for x in r.leads)
            assert all(len(x.drivers) == 3 for x in r.leads)


def test_case_studies_reference_real_inits(data_dir):
    p = data_dir / "case_studies.json"
    if not p.exists():
        pytest.skip("no case studies yet")
    cs = schemas.CaseStudies.model_validate_json(p.read_text(encoding="utf-8"))
    inits = set(schemas.Inits.model_validate_json((data_dir / "inits.json").read_text(encoding="utf-8")).inits)
    assert {c.init for c in cs.cases} <= inits
    assert {c.kind for c in cs.cases} == {"bust", "verified"}


def test_total_size_under_cap(data_dir):
    total = sum(p.stat().st_size for p in data_dir.rglob("*.json"))
    assert total < 16 * 1024 * 1024, f"{total / 1e6:.1f} MB"
