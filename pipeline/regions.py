"""Homogeneous forecast regions over India.

The model runs on a 64x32 (~5.6 deg) grid, so the region unit is 10 hand-written
lat/lon boxes that roughly follow IMD's homogeneous regions plus the Bay of Bengal
(cyclogenesis). The 36 IMD subdivisions / states are painted by their parent region
on the map; that mapping lives here too so pipeline and frontend agree.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class Box:
    lat0: float
    lat1: float
    lon0: float
    lon1: float
    label: str

    @property
    def centroid(self) -> tuple[float, float]:
        return ((self.lat0 + self.lat1) / 2, (self.lon0 + self.lon1) / 2)


# Order matters: it is the region index used everywhere (region_code).
REGIONS: dict[str, Box] = {
    "western_himalaya": Box(30, 37, 73, 80, "Western Himalaya"),
    "north_west": Box(23, 30, 68, 77, "North-West India"),
    "gangetic_plain": Box(24, 30, 77, 88, "Indo-Gangetic Plain"),
    "north_east": Box(22, 29, 88, 97, "North-East India"),
    "central": Box(18, 24, 74, 84, "Central India"),
    "west_coast": Box(12, 20, 72, 76, "West Coast"),
    "east_coast": Box(14, 22, 80, 88, "East Coast"),
    "peninsular": Box(12, 18, 76, 80, "Peninsular Interior"),
    "south": Box(8, 13, 76, 80, "South Peninsula"),
    "bay_of_bengal": Box(10, 20, 85, 95, "Bay of Bengal"),
}

REGION_CODES: dict[str, int] = {name: i for i, name in enumerate(REGIONS)}

# Indian states / UTs -> parent region. Used to paint the map. Keys must match the
# `name` property of frontend/public/data/india.geojson after normalisation
# (lowercase, spaces/&/hyphens -> underscore).
STATE_TO_REGION: dict[str, str] = {
    "jammu_and_kashmir": "western_himalaya",
    "ladakh": "western_himalaya",
    "himachal_pradesh": "western_himalaya",
    "uttarakhand": "western_himalaya",
    "uttaranchal": "western_himalaya",
    "punjab": "north_west",
    "haryana": "north_west",
    "chandigarh": "north_west",
    "delhi": "north_west",
    "nct_of_delhi": "north_west",
    "rajasthan": "north_west",
    "gujarat": "north_west",
    "dadra_and_nagar_haveli_and_daman_and_diu": "west_coast",
    "dadra_and_nagar_haveli": "west_coast",
    "daman_and_diu": "west_coast",
    "uttar_pradesh": "gangetic_plain",
    "bihar": "gangetic_plain",
    "jharkhand": "gangetic_plain",
    "west_bengal": "gangetic_plain",
    "sikkim": "north_east",
    "assam": "north_east",
    "arunachal_pradesh": "north_east",
    "meghalaya": "north_east",
    "nagaland": "north_east",
    "manipur": "north_east",
    "mizoram": "north_east",
    "tripura": "north_east",
    "madhya_pradesh": "central",
    "chhattisgarh": "central",
    "maharashtra": "central",
    "goa": "west_coast",
    "karnataka": "peninsular",
    "telangana": "peninsular",
    "andhra_pradesh": "east_coast",
    "odisha": "east_coast",
    "orissa": "east_coast",
    "tamil_nadu": "south",
    "puducherry": "south",
    "kerala": "south",
    "lakshadweep": "west_coast",
    "andaman_and_nicobar_islands": "bay_of_bengal",
    "andaman_and_nicobar": "bay_of_bengal",
}


def normalise_name(name: str) -> str:
    s = name.strip().lower()
    for ch in ("&", "-", " ", "  "):
        s = s.replace(ch, "_")
    s = s.replace("and", "and")
    while "__" in s:
        s = s.replace("__", "_")
    return s.strip("_")


def box_weights(lat: np.ndarray, lon: np.ndarray, box: Box) -> np.ndarray:
    """Area (cos-lat) weights on a (lat, lon) grid, zero outside the box.

    Longitudes may be 0..360 or -180..180; the box is always given in 0..360-compatible
    positive degrees East, which covers India either way.
    """
    lat = np.asarray(lat, dtype=float)
    lon = np.asarray(lon, dtype=float)
    lon360 = np.where(lon < 0, lon + 360, lon)
    in_lat = (lat >= box.lat0) & (lat <= box.lat1)
    in_lon = (lon360 >= box.lon0) & (lon360 <= box.lon1)
    w = np.cos(np.deg2rad(lat))[:, None] * np.ones_like(lon)[None, :]
    mask = in_lat[:, None] & in_lon[None, :]
    w = np.where(mask, w, 0.0)
    if w.sum() == 0:
        # Coarse grid: fall back to the nearest grid point to the centroid.
        clat, clon = box.centroid
        i = int(np.argmin(np.abs(lat - clat)))
        j = int(np.argmin(np.abs(lon360 - clon)))
        w = np.zeros((lat.size, lon.size))
        w[i, j] = 1.0
    return w / w.sum()


def region_mean(field: np.ndarray, lat: np.ndarray, lon: np.ndarray, box: Box) -> np.ndarray:
    """Area-weighted mean over `box` of `field`, whose last two axes are (lat, lon).

    Leading axes (member, lead, ...) are preserved.
    """
    w = box_weights(lat, lon, box)
    return np.tensordot(np.asarray(field), w, axes=([-2, -1], [0, 1]))
