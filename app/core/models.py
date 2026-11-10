from __future__ import annotations
from dataclasses import dataclass
from enum import Enum


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

    def padded(self, frac: float) -> "BBox":
        dx, dy = int(self.width * frac), int(self.height * frac)
        return BBox(self.x1 - dx, self.y1 - dy, self.x2 + dx, self.y2 + dy)


@dataclass
class PlateDetection:
    bbox: BBox
    confidence: float


@dataclass
class PlateRead:
    raw: str
    text: str | None
    confidence: float
    char_probs: tuple[float, ...] | None = None


class PlateStatus(str, Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    REVIEW_FOREIGN = "review_foreign"
    REVIEW_UNSURE = "review_unsure"
    REVIEW_CONFLICT = "review_conflict"
    NO_PLATE = "no_plate"


@dataclass
class VehicleTrack:
    track_id: int
    bbox: BBox
    label: str
    confidence: float
    plate: PlateDetection | None = None
    plate_text: str | None = None
    plate_status: PlateStatus | None = None
