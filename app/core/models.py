from __future__ import annotations
from dataclasses import dataclass


@dataclass(frozen=True)
class BBox:
    x1: int
    y1: int
    x2: int
    y2: int

    @property
    def width(self) -> int:
        return self.x2 - self.x1

    @property
    def height(self) -> int:
        return self.y2 - self.y1

    def shifted(self, dx: int, dy: int) -> "BBox":
        return BBox(self.x1 + dx, self.y1 + dy, self.x2 + dx, self.y2 + dy)

    def clamp(self, width: int, height: int) -> "BBox":
        return BBox(max(0, self.x1), max(0, self.y1),
                    min(width, self.x2), min(height, self.y2))


@dataclass
class PlateDetection:
    bbox: BBox
    confidence: float


@dataclass
class VehicleTrack:
    track_id: int
    bbox: BBox
    label: str
    confidence: float
    plate: PlateDetection | None = None
