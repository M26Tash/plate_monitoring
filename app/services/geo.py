from __future__ import annotations

import math

M_PER_DEG_LAT = 110540
M_PER_DEG_LON = 111320


def to_meters(lat, lon, lat0, lon0) -> tuple[float, float]:
    y = (lat - lat0) * M_PER_DEG_LAT
    x = (lon - lon0) * M_PER_DEG_LON * math.cos(math.radians(lat0))
    return x,y


def to_latlon(x, y, lat0, lon0) -> tuple[float, float]:
    lat = (y / M_PER_DEG_LAT) + lat0
    lon = x / (M_PER_DEG_LON * math.cos(math.radians(lat0))) + lon0
    return  lat, lon


class GeoMapper:
    def __init__(self, image_points, geo_points):
        pass

