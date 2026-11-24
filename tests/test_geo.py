import numpy as np
import pytest

from app.services.geo import GeoMapper, to_latlon, to_meters

IMG = [(0, 0), (100, 0), (100, 100), (0, 100)]
GEO = [(41.0, 29.0), (41.0, 29.001), (40.999, 29.001), (40.999, 29.0)]


def test_to_meters_known_distance():
    x, y = to_meters(41.001, 29.001, 41.0, 29.0)
    assert x == pytest.approx(84.0, abs=0.1)
    assert y == pytest.approx(110.54, abs=0.01)


def test_meters_round_trip():
    lat, lon = to_latlon(*to_meters(41.0123, 28.9876, 41.0, 29.0), 41.0, 29.0)
    assert lat == pytest.approx(41.0123, abs=1e-9)
    assert lon == pytest.approx(28.9876, abs=1e-9)


def test_project_centre_of_square():
    lat, lon = GeoMapper(IMG, GEO).project([(50, 50)])[0]
    assert lat == pytest.approx(40.9995, abs=1e-6)
    assert lon == pytest.approx(29.0005, abs=1e-6)


def test_project_accepts_numpy_and_empty():
    m = GeoMapper(IMG, GEO)
    assert m.project(np.array([[50, 50]])) == m.project([(50, 50)])
    assert m.project([]) == []


def test_perfect_points_have_no_error():
    assert max(GeoMapper(IMG, GEO).errors()) < 0.01


def test_bad_point_has_largest_error():
    geo = GEO + [(40.99955, 29.0005)]
    errors = GeoMapper(IMG + [(50, 50)], geo).errors()
    assert errors.index(max(errors)) == 4


def test_json_round_trip():
    m = GeoMapper(IMG, GEO)
    assert GeoMapper.from_json(m.to_json()).project([(30, 70)]) == m.project([(30, 70)])


@pytest.mark.parametrize("img, geo", [
    (IMG[:3], GEO[:3]),
    (IMG, GEO[:3]),
    ([(0, 0), (1, 1), (2, 2), (3, 3)], GEO),
])
def test_rejects_bad_calibration(img, geo):
    with pytest.raises(ValueError):
        GeoMapper(img, geo)
