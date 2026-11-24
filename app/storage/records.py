from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Source:
    id: int | None
    name: str
    kind: str
    uri: str
    recorded_at: str | None = None
    fps: float | None = None
    lat: float | None = None
    lon: float | None = None
    calibration: str | None = None
    created_at: str | None = None


@dataclass
class Run:
    id: int | None
    source_id: int
    started_at: str
    finished_at: str | None = None
    frames: int = 0
    state: str = "running"


@dataclass
class Sighting:
    id: int | None
    run_id: int
    source_id: int
    track_id: int
    status: str
    plate: str | None
    final_plate: str | None
    review: str | None
    first_frame: int
    last_frame: int
    first_seen: str
    last_seen: str
    vehicle_type: str = ""
    color: str | None = None
    alternatives: list[str] = field(default_factory=list)
    share: float = 0.0
    reads: int = 0
    plate_crop: str | None = None
    vehicle_crop: str | None = None


@dataclass
class Vehicle:
    plate: str
    owner_name: str | None = None
    owner_city: str | None = None
    owner_phone: str | None = None
    make_model: str | None = None
    color: str | None = None
    vehicle_type: str | None = None
    notes: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


@dataclass
class WantedPlate:
    id: int | None
    plate: str
    reason: str = ""
    priority: str = "medium"
    active: bool = True
    notes: str | None = None
    added_at: str | None = None


@dataclass
class Review:
    id: int | None
    sighting_id: int
    decision: str
    plate: str | None
    operator: str
    note: str | None = None
    decided_at: str | None = None


@dataclass
class Event:
    id: int | None
    time: str
    level: str
    kind: str
    message: str
    sighting_id: int | None = None
    plate: str | None = None
