"""Pick case studies from the test-year predictions and write case_studies.json.

Two flagged busts that happened (highest prob among busts at lead >= 3, different regions),
one confident forecast that verified (lowest prob among non-busts with small error).

    python scripts/pick_case_studies.py --out frontend/public/data
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from pipeline import schemas  # noqa: E402
from pipeline.regions import REGIONS  # noqa: E402


def key(ts) -> str:
    return pd.Timestamp(ts).strftime("%Y-%m-%dT%H")


def nice(d: pd.Timestamp) -> str:
    return f"{d.day} {d:%B %Y}"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--artifacts", default="data/artifacts")
    ap.add_argument("--out", default="frontend/public/data")
    args = ap.parse_args()
    te = pd.read_parquet(ROOT / args.artifacts / "predictions_test.parquet")
    te = te[pd.to_datetime(te.init).dt.hour == 0]  # only exported inits
    out = ROOT / args.out

    cases = []
    busts = te[(te.bust) & (te.lead_days >= 3)].sort_values("p_model", ascending=False)
    used = set()
    for _, r in busts.iterrows():
        if r.region in used:
            continue
        used.add(r.region)
        label = REGIONS[r.region].label
        d = pd.Timestamp(r.init)
        cases.append({
            "id": f"bust-{key(r.init)}-{r.region}",
            "title": f"{label}, {nice(d)}: the Day {int(r.lead_days)} forecast that busted",
            "kind": "bust", "init": key(r.init), "region": r.region, "lead": int(r.lead_days),
            "prob": round(float(r.p_model), 3),
            "narrative": {
                "setup": f"On {nice(d)} at {d:%H}Z the ensemble issued its Day {int(r.lead_days)} outlook for {label}.",
                "flag": f"Vishwas put the bust probability at {r.p_model:.0%}, against a climatological rate of about 5%.",
                "why": "See the drivers panel: the note explains which ensemble signals raised the risk.",
                "outcome": f"The verifying analysis showed an error of {r.error:.0f} m² s⁻², above the {r.bust_threshold:.0f} threshold for this region, lead and season. It busted.",
            },
        })
        if len(cases) == 2:
            break

    ok = te[(~te.bust) & (te.lead_days >= 5) & (te.error < te.error.quantile(0.2))].sort_values("p_model")
    r = ok.iloc[0]
    label = REGIONS[r.region].label
    d = pd.Timestamp(r.init)
    cases.append({
        "id": f"verified-{key(r.init)}-{r.region}",
        "title": f"{label}, {nice(d)}: a Day {int(r.lead_days)} forecast worth trusting",
        "kind": "verified", "init": key(r.init), "region": r.region, "lead": int(r.lead_days),
        "prob": round(float(r.p_model), 3),
        "narrative": {
            "setup": f"On {nice(d)} at {d:%H}Z the ensemble issued its Day {int(r.lead_days)} outlook for {label}.",
            "flag": f"Vishwas put the bust probability at {r.p_model:.0%}: high confidence.",
            "why": "Spread was ordinary for the season, successive runs agreed, and the ensemble formed one coherent scenario.",
            "outcome": f"The verifying analysis showed an error of {r.error:.0f} m² s⁻², well inside the {r.bust_threshold:.0f} threshold. The forecast held.",
        },
    })
    doc = schemas.CaseStudies(cases=cases)
    (out / "case_studies.json").write_text(doc.model_dump_json(), encoding="utf-8")
    print(json.dumps([c["title"] for c in cases], indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
