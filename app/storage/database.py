from __future__ import annotations

import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

SCHEMA_VERSION = 1

SCHEMA = """
CREATE TABLE IF NOT EXISTS sources (
    id           INTEGER PRIMARY KEY,
    name         TEXT NOT NULL UNIQUE,
    kind         TEXT NOT NULL CHECK (kind IN ('file', 'camera', 'stream')),
    uri          TEXT NOT NULL,
    recorded_at  TEXT,
    fps          REAL,
    lat          REAL,
    lon          REAL,
    calibration  TEXT,
    created_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS runs (
    id           INTEGER PRIMARY KEY,
    source_id    INTEGER NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    started_at   TEXT NOT NULL,
    finished_at  TEXT,
    frames       INTEGER NOT NULL DEFAULT 0,
    state        TEXT NOT NULL DEFAULT 'running'
                 CHECK (state IN ('running', 'finished', 'stopped', 'failed'))
);

CREATE TABLE IF NOT EXISTS sightings (
    id            INTEGER PRIMARY KEY,
    run_id        INTEGER NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    source_id     INTEGER NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    track_id      INTEGER NOT NULL,
    status        TEXT NOT NULL,
    plate         TEXT,
    final_plate   TEXT,
    review        TEXT CHECK (review IN ('pending', 'done')),
    first_frame   INTEGER NOT NULL,
    last_frame    INTEGER NOT NULL,
    first_seen    TEXT NOT NULL,
    last_seen     TEXT NOT NULL,
    vehicle_type  TEXT NOT NULL DEFAULT '',
    color         TEXT,
    alternatives  TEXT NOT NULL DEFAULT '[]',
    share         REAL NOT NULL DEFAULT 0,
    reads         INTEGER NOT NULL DEFAULT 0,
    plate_crop    TEXT,
    vehicle_crop  TEXT,
    UNIQUE (run_id, track_id)
);
CREATE INDEX IF NOT EXISTS ix_sightings_final_plate ON sightings(final_plate);
CREATE INDEX IF NOT EXISTS ix_sightings_status ON sightings(status);
CREATE INDEX IF NOT EXISTS ix_sightings_review ON sightings(review);
CREATE INDEX IF NOT EXISTS ix_sightings_first_seen ON sightings(first_seen);

CREATE TABLE IF NOT EXISTS track_points (
    sighting_id  INTEGER NOT NULL REFERENCES sightings(id) ON DELETE CASCADE,
    frame        INTEGER NOT NULL,
    x            INTEGER NOT NULL,
    y            INTEGER NOT NULL,
    PRIMARY KEY (sighting_id, frame)
) WITHOUT ROWID;

CREATE TABLE IF NOT EXISTS vehicles (
    plate         TEXT PRIMARY KEY,
    owner_name    TEXT,
    owner_city    TEXT,
    owner_phone   TEXT,
    make_model    TEXT,
    color         TEXT,
    vehicle_type  TEXT,
    notes         TEXT,
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS wanted (
    id        INTEGER PRIMARY KEY,
    plate     TEXT NOT NULL UNIQUE,
    reason    TEXT NOT NULL DEFAULT '',
    priority  TEXT NOT NULL DEFAULT 'medium' CHECK (priority IN ('low', 'medium', 'high')),
    active    INTEGER NOT NULL DEFAULT 1,
    notes     TEXT,
    added_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS reviews (
    id           INTEGER PRIMARY KEY,
    sighting_id  INTEGER NOT NULL REFERENCES sightings(id) ON DELETE CASCADE,
    decision     TEXT NOT NULL CHECK (decision IN ('accepted', 'corrected', 'foreign', 'rejected')),
    plate        TEXT,
    operator     TEXT NOT NULL,
    note         TEXT,
    decided_at   TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_reviews_sighting ON reviews(sighting_id);

CREATE TABLE IF NOT EXISTS events (
    id           INTEGER PRIMARY KEY,
    time         TEXT NOT NULL,
    level        TEXT NOT NULL CHECK (level IN ('info', 'warning', 'alert')),
    kind         TEXT NOT NULL,
    message      TEXT NOT NULL,
    sighting_id  INTEGER REFERENCES sightings(id) ON DELETE SET NULL,
    plate        TEXT
);
CREATE INDEX IF NOT EXISTS ix_events_time ON events(time);
"""


def now() -> str:
    return datetime.now().isoformat(sep=" ", timespec="milliseconds")


class Database:

    def __init__(self, path: Path | str):
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._local = threading.local()
        self._shared = None
        if self.path == ":memory:":
            self._shared = self._open(check_same_thread=False)
        self._migrate()

    def _open(self, check_same_thread: bool = True) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=10, check_same_thread=check_same_thread)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        if self.path != ":memory:":
            conn.execute("PRAGMA journal_mode = WAL")
        return conn

    @property
    def conn(self) -> sqlite3.Connection:
        if self._shared is not None:
            return self._shared
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = self._local.conn = self._open()
        return conn

    @contextmanager
    def transaction(self):
        conn = self.conn
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    def _migrate(self) -> None:
        version = self.conn.execute("PRAGMA user_version").fetchone()[0]
        if version > SCHEMA_VERSION:
            raise RuntimeError(f"{self.path} has schema v{version}, this app knows v{SCHEMA_VERSION}")
        self.conn.executescript(SCHEMA)
        self.conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        self.conn.commit()

    def close(self) -> None:
        conn = self._shared or getattr(self._local, "conn", None)
        if conn is not None:
            conn.close()
            self._local.conn = None
