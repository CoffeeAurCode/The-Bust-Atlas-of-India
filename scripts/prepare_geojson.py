"""Rewind a GeoJSON so d3-geo renders it correctly.

RFC 7946 GeoJSON winds exterior rings counter-clockwise; d3-geo (spherical) expects
exterior rings CLOCKWISE and holes counter-clockwise, otherwise every polygon paints
the whole globe minus the shape. This script fixes the winding in place.

    python scripts/prepare_geojson.py frontend/public/data/india.geojson
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def signed_area(ring: list[list[float]]) -> float:
    a = 0.0
    for (x1, y1), (x2, y2) in zip(ring, ring[1:] + ring[:1]):
        a += x1 * y2 - x2 * y1
    return a / 2.0


def rewind_polygon(coords: list) -> list:
    out = []
    for i, ring in enumerate(coords):
        area = signed_area(ring)
        # exterior (i == 0) must be clockwise (negative planar area); holes counter-clockwise
        want_cw = i == 0
        is_cw = area < 0
        out.append(ring[::-1] if want_cw != is_cw else ring)
    return out


def main(path: str) -> None:
    p = Path(path)
    g = json.loads(p.read_text(encoding="utf-8"))
    n = 0
    for f in g["features"]:
        geom = f["geometry"]
        if geom["type"] == "Polygon":
            geom["coordinates"] = rewind_polygon(geom["coordinates"])
            n += 1
        elif geom["type"] == "MultiPolygon":
            geom["coordinates"] = [rewind_polygon(poly) for poly in geom["coordinates"]]
            n += len(geom["coordinates"])
    p.write_text(json.dumps(g, separators=(",", ":")), encoding="utf-8")
    print(f"rewound {n} polygons in {len(g['features'])} features -> {p} ({p.stat().st_size / 1e3:.0f} KB)")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "frontend/public/data/india.geojson")
