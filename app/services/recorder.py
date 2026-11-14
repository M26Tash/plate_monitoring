from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from app.core.models import PlateStatus, TrackResult
from app.storage import CropStore, Sighting, Source, Storage

REVIEW_STATUSES = {PlateStatus.REVIEW_CONFLICT, PlateStatus.REVIEW_UNSURE, PlateStatus.REVIEW_FOREIGN}


class RunRecorder:

    def __init__(self, storage: Storage, crops: CropStore, source: Source, fps: float):
        self.storage = storage
        self.crops = crops
        self.source = source
        self.fps = fps or 30.0
        self.run = storage.runs.start(source.id)
        start = source.recorded_at or self.run.started_at
        self.t0 = datetime.fromisoformat(start)
        self.frames = 0
        storage.events.log("run", f"run #{self.run.id} started on source '{source.name}'")

    def time_of(self, frame: int) -> str:
        t = self.t0 + timedelta(seconds=max(frame - 1, 0) / self.fps)
        return t.isoformat(sep=" ", timespec="milliseconds")

    def record(self, r: TrackResult) -> Sighting:
        status = PlateStatus(r.status)
        needs_review = status in REVIEW_STATUSES
        s = Sighting(
            id=None, run_id=self.run.id, source_id=self.source.id, track_id=r.track_id,
            status=status.value, plate=r.plate,
            final_plate=r.plate if status == PlateStatus.CONFIRMED else None,
            review="pending" if needs_review else None,
            first_frame=r.first_frame, last_frame=r.last_frame,
            first_seen=self.time_of(r.first_frame), last_seen=self.time_of(r.last_frame),
            vehicle_type=r.label, alternatives=list(r.alternatives), share=r.share, reads=r.reads,
            plate_crop=self.crops.save(r.plate_crop, self.run.id, r.track_id, "plate"),
            vehicle_crop=self.crops.save(r.vehicle_crop, self.run.id, r.track_id, "vehicle"),
        )
        saved = self.storage.sightings.add(s, r.path)
        if status == PlateStatus.CONFIRMED:
            self.storage.events.log("sighting", f"{saved.final_plate} confirmed ({r.label}, track #{r.track_id})",
                                    sighting_id=saved.id, plate=saved.final_plate)
        elif needs_review:
            self.storage.events.log("review", f"{r.plate or 'unreadable plate'} sent to review: {status.value}",
                                    level="warning", sighting_id=saved.id, plate=r.plate)
        return saved

    def finish(self, frames: int, state: str = "finished") -> None:
        self.frames = frames
        self.storage.runs.finish(self.run.id, frames, state)
        self.storage.events.log("run", f"run #{self.run.id} {state} after {frames} frames",
                                level="info" if state == "finished" else "warning")


def replace_previous_runs(storage: Storage, crops: CropStore, source_id: int) -> int:
    runs = storage.runs.for_source(source_id)
    for run in runs:
        storage.runs.delete(run.id)
        crops.delete_run(run.id)
    if runs:
        storage.events.log("run", f"{len(runs)} earlier run(s) of source #{source_id} replaced", level="warning")
    return len(runs)


def file_time(path) -> str:
    return datetime.fromtimestamp(Path(path).stat().st_mtime).isoformat(sep=" ", timespec="seconds")



def resolve_file(uri: str) -> Path:
    from app.core import config
    p = Path(uri)
    return (p if p.is_absolute() else config.ROOT / p).resolve()
