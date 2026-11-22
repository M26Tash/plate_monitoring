from __future__ import annotations

import json
import math

import cv2
import numpy as np

M_PER_DEG_LAT = 110540
M_PER_DEG_LON = 111320


def to_meters(lat, lon, lat0, lon0) -> tuple[float, float]:
    y = (lat - lat0) * M_PER_DEG_LAT
    x = (lon - lon0) * M_PER_DEG_LON * math.cos(math.radians(lat0))
    return x, y


def to_latlon(x, y, lat0, lon0) -> tuple[float, float]:
    lat = (y / M_PER_DEG_LAT) + lat0
    lon = x / (M_PER_DEG_LON * math.cos(math.radians(lat0))) + lon0
    return lat, lon


class GeoMapper:
    def __init__(self, image_points, geo_points):
        if len(image_points) != len(geo_points) or len(image_points) < 4:
            raise ValueError("Both lists must have the same length and at least 4 points.")

        self.image_points = image_points
        self.geo_points = geo_points

        self.lat0 = sum(lat for lat, lon in geo_points) / len(geo_points)
        self.lon0 = sum(lon for lat, lon in geo_points) / len(geo_points)

        self.metres = [to_meters(lat, lon, self.lat0, self.lon0) for lat, lon in geo_points]

        H, _ = cv2.findHomography(
            np.float32(image_points),
            np.float32(self.metres),
            0
        )

        if H is None or abs(np.linalg.det(H)) < 1e-9:
            raise ValueError("Could not calculate homography matrix.")

        self.H = H

    def _pixels_to_metres(self, points) -> np.ndarray:
        out = cv2.perspectiveTransform(
            np.float32(points).reshape(-1, 1, 2),
            self.H
        )
        return out.reshape(-1, 2)

    def project(self, points) -> list[tuple[float, float]]:
        if len(points) == 0:
            return []

        results = [
            to_latlon(float(x), float(y), self.lat0, self.lon0)
            for x, y in self._pixels_to_metres(points)
        ]

        return results

    def errors(self) -> list[float]:
        projected = self._pixels_to_metres(self.image_points)

        errors = [
            math.hypot(
                float(x1) - float(x2),
                float(y1) - float(y2)
            )
            for (x1, y1), (x2, y2) in zip(projected, self.metres)
        ]

        return errors

    def to_json(self) -> str:
        return json.dumps({
            "image": self.image_points,
            "geo": self.geo_points
        })

    @classmethod
    def from_json(cls, text: str) -> GeoMapper:
        data = json.loads(text)
        return cls(data["image"], data["geo"])