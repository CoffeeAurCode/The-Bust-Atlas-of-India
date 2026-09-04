import numpy as np

from pipeline.regions import REGIONS, STATE_TO_REGION, box_weights, normalise_name, region_mean


def test_boxes_well_formed_and_over_india():
    for name, b in REGIONS.items():
        assert b.lat0 < b.lat1, name
        assert b.lon0 < b.lon1, name
        assert 5 <= b.lat0 and b.lat1 <= 40, name
        assert 65 <= b.lon0 and b.lon1 <= 100, name


def test_ten_regions():
    assert len(REGIONS) == 10


def test_every_state_maps_to_a_region():
    for state, region in STATE_TO_REGION.items():
        assert region in REGIONS, (state, region)
        assert normalise_name(state) == state


def test_region_mean_constant_field():
    lat = np.linspace(-87.1875, 87.1875, 32)  # 64x32 equiangular-ish
    lon = np.arange(0, 360, 5.625)
    field = np.full((lat.size, lon.size), 7.5)
    for b in REGIONS.values():
        assert np.isclose(region_mean(field, lat, lon, b), 7.5)


def test_region_mean_preserves_leading_axes():
    lat = np.linspace(-87.1875, 87.1875, 32)
    lon = np.arange(0, 360, 5.625)
    field = np.random.default_rng(0).normal(size=(50, 10, lat.size, lon.size))
    out = region_mean(field, lat, lon, REGIONS["central"])
    assert out.shape == (50, 10)


def test_weights_are_cosine_weighted_and_normalised():
    lat = np.arange(-90, 91, 1.0)
    lon = np.arange(0, 360, 1.0)
    b = REGIONS["gangetic_plain"]
    w = box_weights(lat, lon, b)
    assert np.isclose(w.sum(), 1.0)
    # inside the box, weight decreases with latitude
    i_lo = int(np.where(lat == b.lat0 + 1)[0][0])
    i_hi = int(np.where(lat == b.lat1 - 1)[0][0])
    j = int(np.where(lon == 80)[0][0])
    assert w[i_lo, j] > w[i_hi, j] > 0
    # outside the box, zero
    assert w[int(np.where(lat == 0)[0][0]), j] == 0


def test_coarse_grid_falls_back_to_nearest_point():
    lat = np.array([0.0, 20.0, 40.0])
    lon = np.array([60.0, 90.0, 120.0])
    b = REGIONS["south"]  # 8-13N, no grid point inside
    w = box_weights(lat, lon, b)
    assert w.sum() == 1.0 and (w > 0).sum() == 1
