from __future__ import annotations

import threading
import time
import traceback

import cv2
from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QImage

from app.core import config
from app.storage import CropStore, Source, Storage

DISPLAY_WIDTH = 1280


def to_qimage(frame_bgr) -> QImage:
    h, w = frame_bgr.shape[:2]
    if w > DISPLAY_WIDTH:
        frame_bgr = cv2.resize(frame_bgr, (DISPLAY_WIDTH, int(h * DISPLAY_WIDTH / w)), interpolation=cv2.INTER_AREA)
        h, w = frame_bgr.shape[:2]
    rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
    return QImage(rgb.data, w, h, 3 * w, QImage.Format_RGB888).copy()


class PipelineWorker(QThread):

    state_changed = Signal(str)
    frame_ready = Signal(QImage, int, int, float)
    alert = Signal(object)                      # services.watchlist.Hit
    sighting_added = Signal(object)
    failed = Signal(str)

    def __init__(self, storage: Storage, crops: CropStore, source: Source, parent=None):
        super().__init__(parent)
        self.storage = storage
        self.crops = crops
        self.source = source
        self._stop = threading.Event()
        self._resume = threading.Event()
        self._resume.set()

    def pause(self) -> None:
        self._resume.clear()
        self.state_changed.emit("paused")

    def resume(self) -> None:
        self._resume.set()
        self.state_changed.emit("running")

    def stop(self) -> None:
        self._stop.set()
        self._resume.set()

    @property
    def paused(self) -> bool:
        return not self._resume.is_set()

    def run(self) -> None:
        recorder = None
        frames = 0
        try:
            self.state_changed.emit("loading")
            from app.services.recorder import RunRecorder, resolve_file
            from app.services.watchlist import WatchlistService
            from app.video.source import VideoSource
            from app.visualization import draw
            from main import build_pipeline

            pipeline = build_pipeline(config.PLATE_WEIGHTS, padding=config.OCR_PADDING,
                                      read_every=config.OCR_READ_EVERY, verbose=False)
            uri = str(resolve_file(self.source.uri)) if self.source.kind == "file" else self.source.uri
            with VideoSource(uri) as video:
                total = int(video.cap.get(cv2.CAP_PROP_FRAME_COUNT)) if self.source.kind == "file" else 0
                recorder = RunRecorder(self.storage, self.crops, self.source, self.source.fps or video.fps)
                watchlist = WatchlistService(self.storage)
                self.state_changed.emit("running")
                started, speed = time.perf_counter(), 0.0
                for _, _, frame in video.frames():
                    self._resume.wait()
                    if self._stop.is_set():
                        break
                    tracks = pipeline.process(frame)
                    frames += 1
                    for result in pipeline.pop_finished():
                        self._publish(recorder.record(result), watchlist)
                    elapsed = time.perf_counter() - started
                    speed = frames / elapsed if elapsed else 0.0
                    self.frame_ready.emit(to_qimage(draw(frame, tracks)), frames, total, speed)
                for result in pipeline.flush():
                    self._publish(recorder.record(result), watchlist)
            state = "stopped" if self._stop.is_set() else "finished"
            recorder.finish(frames, state)
            self.state_changed.emit(state)
        except Exception as e:
            traceback.print_exc()
            if recorder is not None:
                recorder.finish(frames, "failed")
            self.storage.events.log("system", f"processing failed: {e}", level="warning")
            self.failed.emit(str(e))
            self.state_changed.emit("failed")
        finally:
            self.storage.db.close()

    def _publish(self, sighting, watchlist) -> None:
        hit = watchlist.check(sighting)
        if hit is not None:
            sighting = hit.sighting
            if hit.kind == "exact":
                self.alert.emit(hit)
        self.sighting_added.emit(sighting)
