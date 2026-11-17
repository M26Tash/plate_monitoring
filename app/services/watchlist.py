from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from app.storage import Sighting, Storage, WantedPlate, normalize_plate

PRIORITIES = ("low", "medium", "high")


def edit_distance(a: str, b: str) -> int:
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


@dataclass
class Hit:
    kind: str
    wanted: WantedPlate
    sighting: Sighting


class WatchlistService:
    def __init__(self, storage: Storage, max_near: int = 1):
        self.storage = storage
        self.max_near = max_near

    def check(self, s: Sighting, allow_near: bool = True) -> Hit | None:
        wanted = self.storage.wanted.all(active_only=True)
        if not wanted:
            return None
        if s.final_plate:
            for w in wanted:
                if w.plate == s.final_plate:
                    self._alert(w, s)
                    return Hit("exact", w, s)
        reading = s.final_plate or s.plate
        if not allow_near or not reading or (s.review == "pending" and s.final_plate is None):
            return None
        near = [w for w in wanted if 0 < edit_distance(reading, w.plate) <= self.max_near]
        if not near:
            return None
        w = near[0]
        self.storage.sightings.flag_for_review(s.id, [reading] + [x.plate for x in near])
        self.storage.events.log("watchlist", f"{reading} is close to wanted {w.plate}: sent to review",
                                level="warning", sighting_id=s.id, plate=reading)
        return Hit("near", w, self.storage.sightings.get(s.id))

    def _alert(self, w: WantedPlate, s: Sighting) -> None:
        reason = f" ({w.reason})" if w.reason else ""
        self.storage.events.log("alert", f"WANTED {w.plate} seen{reason} · priority {w.priority}",
                                level="alert", sighting_id=s.id, plate=w.plate)

    def recent_alerts(self, limit: int = 100):
        return self.storage.events.recent(limit=limit, kind="alert")

    def add(self, plate: str, reason: str = "", priority: str = "medium", notes: str | None = None) -> WantedPlate:
        plate = normalize_plate(plate)
        if not plate:
            raise ValueError("Plate is required.")
        if priority not in PRIORITIES:
            raise ValueError(f"Priority must be one of {', '.join(PRIORITIES)}.")
        if self.storage.wanted.by_plate(plate):
            raise ValueError(f"{plate} is already on the watchlist.")
        w = self.storage.wanted.add(plate, reason, priority, notes)
        self.storage.events.log("watchlist", f"{plate} added to watchlist ({priority})", plate=plate)
        return w

    def import_csv(self, path: Path | str) -> tuple[int, list[str]]:
        added, problems = 0, []
        with open(path, newline="", encoding="utf-8-sig") as f:
            for n, row in enumerate(csv.DictReader(f), 2):
                row = {k.strip().lower(): (v or "").strip() for k, v in row.items() if k}
                try:
                    self.add(row.get("plate", ""), row.get("reason", ""),
                             row.get("priority", "medium").lower() or "medium", row.get("notes") or None)
                    added += 1
                except ValueError as e:
                    problems.append(f"line {n}: {e}")
        return added, problems
