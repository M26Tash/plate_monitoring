from __future__ import annotations

import json
from dataclasses import asdict, fields
from typing import Iterable, TypeVar

from app.storage.database import Database, now
from app.storage.records import Event, Review, Run, Sighting, Source, Vehicle, WantedPlate

T = TypeVar("T")


def normalize_plate(plate: str | None) -> str | None:
    if plate is None:
        return None
    plate = "".join(c for c in plate.upper() if c.isalnum())
    return plate or None


class Repository:
    table = ""

    def __init__(self, db: Database):
        self.db = db

    def _one(self, cls: type[T], sql: str, params: Iterable = ()) -> T | None:
        row = self.db.conn.execute(sql, tuple(params)).fetchone()
        return self._to(cls, row) if row else None

    def _many(self, cls: type[T], sql: str, params: Iterable = ()) -> list[T]:
        return [self._to(cls, r) for r in self.db.conn.execute(sql, tuple(params)).fetchall()]

    @staticmethod
    def _to(cls: type[T], row) -> T:
        names = {f.name for f in fields(cls)}
        return cls(**{k: row[k] for k in row.keys() if k in names})

    def count(self) -> int:
        return self.db.conn.execute(f"SELECT COUNT(*) FROM {self.table}").fetchone()[0]


class SourceRepository(Repository):
    table = "sources"

    def add(self, name: str, kind: str, uri: str, recorded_at: str | None = None,
            fps: float | None = None) -> Source:
        with self.db.transaction() as c:
            cur = c.execute("INSERT INTO sources (name, kind, uri, recorded_at, fps, created_at) "
                            "VALUES (?, ?, ?, ?, ?, ?)", (name, kind, uri, recorded_at, fps, now()))
        return self.get(cur.lastrowid)

    def get(self, source_id: int) -> Source | None:
        return self._one(Source, "SELECT * FROM sources WHERE id = ?", (source_id,))

    def by_name(self, name: str) -> Source | None:
        return self._one(Source, "SELECT * FROM sources WHERE name = ?", (name,))

    def all(self) -> list[Source]:
        return self._many(Source, "SELECT * FROM sources ORDER BY name")

    def update(self, source: Source) -> None:
        with self.db.transaction() as c:
            c.execute("UPDATE sources SET name = ?, kind = ?, uri = ?, recorded_at = ?, fps = ?, "
                      "lat = ?, lon = ?, calibration = ? WHERE id = ?",
                      (source.name, source.kind, source.uri, source.recorded_at, source.fps,
                       source.lat, source.lon, source.calibration, source.id))

    def delete(self, source_id: int) -> None:
        with self.db.transaction() as c:
            c.execute("DELETE FROM sources WHERE id = ?", (source_id,))


class RunRepository(Repository):
    table = "runs"

    def start(self, source_id: int) -> Run:
        with self.db.transaction() as c:
            cur = c.execute("INSERT INTO runs (source_id, started_at) VALUES (?, ?)", (source_id, now()))
        return self.get(cur.lastrowid)

    def finish(self, run_id: int, frames: int, state: str = "finished") -> None:
        with self.db.transaction() as c:
            c.execute("UPDATE runs SET finished_at = ?, frames = ?, state = ? WHERE id = ?",
                      (now(), frames, state, run_id))

    def get(self, run_id: int) -> Run | None:
        return self._one(Run, "SELECT * FROM runs WHERE id = ?", (run_id,))

    def for_source(self, source_id: int) -> list[Run]:
        return self._many(Run, "SELECT * FROM runs WHERE source_id = ? ORDER BY id DESC", (source_id,))

    def delete(self, run_id: int) -> None:
        with self.db.transaction() as c:
            c.execute("DELETE FROM runs WHERE id = ?", (run_id,))


class SightingRepository(Repository):
    table = "sightings"
    COLUMNS = ("run_id", "source_id", "track_id", "status", "plate", "final_plate", "review",
               "first_frame", "last_frame", "first_seen", "last_seen", "vehicle_type", "color",
               "alternatives", "share", "reads", "plate_crop", "vehicle_crop")

    @staticmethod
    def _to(cls, row):
        s = Repository._to(cls, row)
        s.alternatives = json.loads(s.alternatives or "[]")
        return s

    def add(self, s: Sighting, path: Iterable[tuple[int, int, int]] = ()) -> Sighting:
        values = asdict(s)
        values["alternatives"] = json.dumps(s.alternatives)
        values["plate"], values["final_plate"] = normalize_plate(s.plate), normalize_plate(s.final_plate)
        with self.db.transaction() as c:
            cur = c.execute(f"INSERT INTO sightings ({', '.join(self.COLUMNS)}) "
                            f"VALUES ({', '.join('?' * len(self.COLUMNS))})",
                            [values[k] for k in self.COLUMNS])
            sid = cur.lastrowid
            c.executemany("INSERT INTO track_points (sighting_id, frame, x, y) VALUES (?, ?, ?, ?)",
                          [(sid, f, x, y) for f, x, y in path])
        return self.get(sid)

    def get(self, sighting_id: int) -> Sighting | None:
        return self._one(Sighting, "SELECT * FROM sightings WHERE id = ?", (sighting_id,))

    def search(self, plate: str | None = None, status: str | None = None, source_id: int | None = None,
               since: str | None = None, until: str | None = None,
               limit: int = 500, offset: int = 0) -> list[Sighting]:
        where, params = [], []
        if plate:
            where.append("(final_plate LIKE ? OR plate LIKE ?)")
            params += [f"%{normalize_plate(plate)}%"] * 2
        if status:
            where.append("status = ?")
            params.append(status)
        if source_id is not None:
            where.append("source_id = ?")
            params.append(source_id)
        if since:
            where.append("first_seen >= ?")
            params.append(since)
        if until:
            where.append("first_seen <= ?")
            params.append(until)
        sql = "SELECT * FROM sightings"
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY first_seen DESC, id DESC LIMIT ? OFFSET ?"
        return self._many(Sighting, sql, params + [limit, offset])

    def by_plate(self, plate: str) -> list[Sighting]:
        return self._many(Sighting, "SELECT * FROM sightings WHERE final_plate = ? ORDER BY first_seen",
                          (normalize_plate(plate),))

    def review_queue(self) -> list[Sighting]:
        return self._many(Sighting, "SELECT * FROM sightings WHERE review = 'pending' ORDER BY first_seen")

    def path(self, sighting_id: int) -> list[tuple[int, int, int]]:
        rows = self.db.conn.execute("SELECT frame, x, y FROM track_points WHERE sighting_id = ? "
                                    "ORDER BY frame", (sighting_id,)).fetchall()
        return [tuple(r) for r in rows]

    def set_color(self, sighting_id: int, color: str | None) -> None:
        with self.db.transaction() as c:
            c.execute("UPDATE sightings SET color = ? WHERE id = ?", (color, sighting_id))

    def count_by_status(self) -> dict[str, int]:
        rows = self.db.conn.execute("SELECT status, COUNT(*) FROM sightings GROUP BY status").fetchall()
        return {r[0]: r[1] for r in rows}

    def pending_reviews(self) -> int:
        return self.db.conn.execute("SELECT COUNT(*) FROM sightings WHERE review = 'pending'").fetchone()[0]

    def flag_for_review(self, sighting_id: int, alternatives: list[str]) -> None:
        with self.db.transaction() as c:
            c.execute("UPDATE sightings SET review = 'pending', alternatives = ? WHERE id = ?",
                      (json.dumps(alternatives), sighting_id))

    def plate_stats(self) -> dict[str, tuple[int, str]]:
        rows = self.db.conn.execute("SELECT final_plate, COUNT(*), MAX(last_seen) FROM sightings "
                                    "WHERE final_plate IS NOT NULL GROUP BY final_plate").fetchall()
        return {r[0]: (r[1], r[2]) for r in rows}


class VehicleRepository(Repository):
    table = "vehicles"

    def get(self, plate: str) -> Vehicle | None:
        return self._one(Vehicle, "SELECT * FROM vehicles WHERE plate = ?", (normalize_plate(plate),))

    def save(self, v: Vehicle) -> Vehicle:
        v.plate = normalize_plate(v.plate)
        stamp = now()
        with self.db.transaction() as c:
            c.execute("INSERT INTO vehicles (plate, owner_name, owner_city, owner_phone, make_model, color, "
                      "vehicle_type, notes, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
                      "ON CONFLICT(plate) DO UPDATE SET owner_name = excluded.owner_name, "
                      "owner_city = excluded.owner_city, owner_phone = excluded.owner_phone, "
                      "make_model = excluded.make_model, color = excluded.color, "
                      "vehicle_type = excluded.vehicle_type, notes = excluded.notes, "
                      "updated_at = excluded.updated_at",
                      (v.plate, v.owner_name, v.owner_city, v.owner_phone, v.make_model, v.color,
                       v.vehicle_type, v.notes, stamp, stamp))
        return self.get(v.plate)

    def search(self, text: str = "", limit: int = 500) -> list[Vehicle]:
        like = f"%{text.strip()}%"
        return self._many(Vehicle, "SELECT * FROM vehicles WHERE plate LIKE ? OR owner_name LIKE ? "
                                   "OR make_model LIKE ? ORDER BY plate LIMIT ?",
                          (f"%{normalize_plate(text) or ''}%", like, like, limit))

    def delete(self, plate: str) -> None:
        with self.db.transaction() as c:
            c.execute("DELETE FROM vehicles WHERE plate = ?", (normalize_plate(plate),))


class WantedRepository(Repository):
    table = "wanted"

    def add(self, plate: str, reason: str = "", priority: str = "medium", notes: str | None = None) -> WantedPlate:
        with self.db.transaction() as c:
            cur = c.execute("INSERT INTO wanted (plate, reason, priority, notes, added_at) VALUES (?, ?, ?, ?, ?)",
                            (normalize_plate(plate), reason, priority, notes, now()))
        return self.get(cur.lastrowid)

    def get(self, wanted_id: int) -> WantedPlate | None:
        return self._one(WantedPlate, "SELECT * FROM wanted WHERE id = ?", (wanted_id,))

    def by_plate(self, plate: str) -> WantedPlate | None:
        return self._one(WantedPlate, "SELECT * FROM wanted WHERE plate = ?", (normalize_plate(plate),))

    def all(self, active_only: bool = False) -> list[WantedPlate]:
        sql = "SELECT * FROM wanted" + (" WHERE active = 1" if active_only else "")
        items = self._many(WantedPlate, sql + " ORDER BY added_at DESC")
        for w in items:
            w.active = bool(w.active)
        return items

    def update(self, w: WantedPlate) -> None:
        with self.db.transaction() as c:
            c.execute("UPDATE wanted SET plate = ?, reason = ?, priority = ?, active = ?, notes = ? WHERE id = ?",
                      (normalize_plate(w.plate), w.reason, w.priority, int(w.active), w.notes, w.id))

    def remove(self, wanted_id: int) -> None:
        with self.db.transaction() as c:
            c.execute("DELETE FROM wanted WHERE id = ?", (wanted_id,))


class ReviewRepository(Repository):
    table = "reviews"

    def decide(self, sighting_id: int, decision: str, plate: str | None, operator: str,
               note: str | None = None) -> Review:
        plate = normalize_plate(plate)
        final = None if decision == "rejected" else plate
        with self.db.transaction() as c:
            cur = c.execute("INSERT INTO reviews (sighting_id, decision, plate, operator, note, decided_at) "
                            "VALUES (?, ?, ?, ?, ?, ?)", (sighting_id, decision, plate, operator, note, now()))
            c.execute("UPDATE sightings SET final_plate = ?, review = 'done' WHERE id = ?", (final, sighting_id))
        return self._one(Review, "SELECT * FROM reviews WHERE id = ?", (cur.lastrowid,))

    def for_sighting(self, sighting_id: int) -> list[Review]:
        return self._many(Review, "SELECT * FROM reviews WHERE sighting_id = ? ORDER BY id", (sighting_id,))


class EventRepository(Repository):
    table = "events"

    def log(self, kind: str, message: str, level: str = "info", sighting_id: int | None = None,
            plate: str | None = None) -> Event:
        with self.db.transaction() as c:
            cur = c.execute("INSERT INTO events (time, level, kind, message, sighting_id, plate) "
                            "VALUES (?, ?, ?, ?, ?, ?)",
                            (now(), level, kind, message, sighting_id, normalize_plate(plate)))
        return self._one(Event, "SELECT * FROM events WHERE id = ?", (cur.lastrowid,))

    def recent(self, limit: int = 500, kind: str | None = None, level: str | None = None,
               text: str | None = None) -> list[Event]:
        where, params = [], []
        if kind:
            where.append("kind = ?")
            params.append(kind)
        if level:
            where.append("level = ?")
            params.append(level)
        if text:
            where.append("(message LIKE ? OR plate LIKE ?)")
            params += [f"%{text}%"] * 2
        sql = "SELECT * FROM events" + (" WHERE " + " AND ".join(where) if where else "")
        return self._many(Event, sql + " ORDER BY time DESC, id DESC LIMIT ?", params + [limit])


class Storage:

    def __init__(self, db: Database):
        self.db = db
        self.sources = SourceRepository(db)
        self.runs = RunRepository(db)
        self.sightings = SightingRepository(db)
        self.vehicles = VehicleRepository(db)
        self.wanted = WantedRepository(db)
        self.reviews = ReviewRepository(db)
        self.events = EventRepository(db)

    @classmethod
    def open(cls, path) -> "Storage":
        return cls(Database(path))

    def close(self) -> None:
        self.db.close()
