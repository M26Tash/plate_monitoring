from __future__ import annotations

from datetime import datetime
from pathlib import Path

import cv2
from PySide6.QtCore import QDateTime, QRectF, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDateTimeEdit, QDialog, QDialogButtonBox,
                               QFileDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit, QListWidget,
                               QListWidgetItem, QMessageBox, QProgressBar, QPushButton, QSizePolicy,
                               QVBoxLayout, QWidget)

from app.core import config
from app.gui import theme
from app.gui.pages.base import Page
from app.gui.widgets import Panel
from app.gui.worker import PipelineWorker
from app.services.recorder import file_time, replace_previous_runs, resolve_file
from app.storage import Sighting, Source

VIDEO_FILTER = "Video (*.mp4 *.avi *.mov *.mkv);;All files (*)"
FEED_LIMIT = 300
VIDEO_EXTS = {".mp4", ".avi", ".mov", ".mkv"}
STATUS_TAGS = {"confirmed": "CONFIRMED", "review_conflict": "CONFLICT", "review_unsure": "UNSURE",
               "review_foreign": "FOREIGN", "no_plate": "NO PLATE"}


def suggested_videos() -> list[Path]:
    folder = config.ROOT / "assets"
    if not folder.is_dir():
        return []
    return sorted(p for p in folder.iterdir() if p.suffix.lower() in VIDEO_EXTS)


def bgr_to_pixmap(img, max_w: int, max_h: int) -> QPixmap | None:
    if img is None:
        return None
    rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    h, w = rgb.shape[:2]
    pm = QPixmap.fromImage(QImage(rgb.data, w, h, 3 * w, QImage.Format_RGB888).copy())
    return pm.scaled(max_w, max_h, Qt.KeepAspectRatio, Qt.SmoothTransformation)


class VideoView(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.image: QImage | None = None
        self.overlay = "NO SIGNAL"
        self.setMinimumSize(480, 270)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def show_image(self, image: QImage) -> None:
        self.image, self.overlay = image, ""
        self.update()

    def clear(self, text: str = "NO SIGNAL") -> None:
        self.image, self.overlay = None, text
        self.update()

    def set_overlay(self, text: str) -> None:
        self.overlay = text
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        r = self.rect()
        p.fillRect(r, QColor("#000000"))
        if self.image is not None:
            img = self.image.size().scaled(r.size(), Qt.KeepAspectRatioByExpanding)
            target = QRectF((r.width() - img.width()) / 2, (r.height() - img.height()) / 2,
                            img.width(), img.height())
            p.setClipRect(r)
            p.drawImage(target, self.image)
            p.setClipping(False)
        if self.overlay:
            p.setPen(QColor(theme.ACCENT if self.image is None else theme.WARN))
            p.setFont(theme.mono(14, bold=True))
            p.drawText(r, Qt.AlignCenter, self.overlay)
        p.setPen(QPen(QColor(theme.ACCENT), 2))
        b, rr = 14, r.adjusted(1, 1, -2, -2)
        for x, y, dx, dy in ((rr.left(), rr.top(), 1, 1), (rr.right(), rr.top(), -1, 1),
                             (rr.left(), rr.bottom(), 1, -1), (rr.right(), rr.bottom(), -1, -1)):
            p.drawLine(x, y, x + dx * b, y)
            p.drawLine(x, y, x, y + dy * b)


class FeedRow(QWidget):

    def __init__(self, s: Sighting, crop, parent=None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(10)
        thumb = QLabel()
        thumb.setFixedSize(108, 36)
        thumb.setAlignment(Qt.AlignCenter)
        thumb.setStyleSheet(f"background: #000; border: 1px solid {theme.BORDER};")
        pm = bgr_to_pixmap(crop, 108, 36)
        if pm:
            thumb.setPixmap(pm)
        else:
            thumb.setText("—")
        lay.addWidget(thumb, alignment=Qt.AlignTop)

        color = theme.STATUS_COLORS.get(s.status, theme.TEXT)
        text = QVBoxLayout()
        text.setSpacing(3)
        plate = s.final_plate or s.plate or "UNREAD"
        if s.review == "pending":
            plate += " ?"
        label = QLabel(plate, objectName="FeedPlate")
        label.setStyleSheet(f"color: {color};")
        text.addWidget(label)
        meta = QHBoxLayout()
        meta.setSpacing(8)
        tag = QLabel(STATUS_TAGS.get(s.status, s.status.upper()), objectName="FeedTag")
        tag.setStyleSheet(f"color: {color}; border: 1px solid {color};")
        meta.addWidget(tag)
        meta.addWidget(QLabel(s.first_seen[11:19], objectName="FeedMeta"))
        meta.addStretch(1)
        text.addLayout(meta)
        text.addWidget(QLabel(f"#{s.track_id} · {s.vehicle_type.upper()}", objectName="FeedMeta"))
        lay.addLayout(text, 1)


class SourceDialog(QDialog):

    def __init__(self, parent=None, path: str | None = None):
        super().__init__(parent)
        self.setWindowTitle("Add source")
        self.setMinimumWidth(560)
        panel = Panel("New source")
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignLeft)
        self.kind = QComboBox()
        self.kind.addItems(["file", "camera", "stream"])
        self.uri = QLineEdit()
        browse = QPushButton("BROWSE")
        browse.clicked.connect(self._browse)
        uri_row = QHBoxLayout()
        uri_row.addWidget(self.uri, 1)
        uri_row.addWidget(browse)
        self.name = QLineEdit()
        self.recorded = QDateTimeEdit(QDateTime.currentDateTime())
        self.recorded.setDisplayFormat("yyyy-MM-dd HH:mm:ss")
        self.recorded.setCalendarPopup(True)
        self.live = QCheckBox("live source (times = processing time)")
        self.live.toggled.connect(lambda on: self.recorded.setEnabled(not on))
        self.kind.currentTextChanged.connect(self._kind_changed)
        form.addRow("KIND", self.kind)
        form.addRow("URI", uri_row)
        form.addRow("NAME", self.name)
        form.addRow("RECORDED AT", self.recorded)
        form.addRow("", self.live)
        panel.body.addLayout(form)

        buttons = QDialogButtonBox()
        buttons.addButton(QPushButton("ADD", objectName="Primary"), QDialogButtonBox.AcceptRole)
        buttons.addButton(QPushButton("CANCEL"), QDialogButtonBox.RejectRole)
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 20, 20, 20)
        lay.addWidget(panel)
        lay.addWidget(buttons)
        if path:
            self._set_file(path)

    def _kind_changed(self, kind: str) -> None:
        self.live.setChecked(kind != "file")
        self.uri.setPlaceholderText({"file": "path to a video file", "camera": "camera index, e.g. 0",
                                     "stream": "rtsp://… or http://…"}[kind])

    def _browse(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Choose a video", "", VIDEO_FILTER)
        if path:
            self.kind.setCurrentText("file")
            self._set_file(path)

    def _set_file(self, path: str) -> None:
        self.uri.setText(path)
        if not self.name.text():
            self.name.setText(Path(path).stem)
        self.recorded.setDateTime(QDateTime.fromString(file_time(path), "yyyy-MM-dd HH:mm:ss"))

    def _accept(self) -> None:
        if not self.uri.text().strip() or not self.name.text().strip():
            QMessageBox.warning(self, "Add source", "URI and name are required.")
            return
        if self.kind.currentText() == "file" and not Path(self.uri.text().strip()).exists():
            QMessageBox.warning(self, "Add source", "That file does not exist.")
            return
        self.accept()

    def values(self) -> dict:
        recorded = None if self.live.isChecked() else self.recorded.dateTime().toString("yyyy-MM-dd HH:mm:ss")
        return dict(name=self.name.text().strip(), kind=self.kind.currentText(),
                    uri=self.uri.text().strip(), recorded_at=recorded)


class MonitorPage(Page):
    code, title = "01", "Monitor"
    subtitle = "Process a source: detections, plates and decisions as they happen"

    def build(self) -> None:
        self.worker: PipelineWorker | None = None
        self.counts = {"vehicles": 0, "confirmed": 0, "review": 0}

        controls = Panel("Source", meta="FILE · CAMERA · STREAM")
        row = QHBoxLayout()
        self.sources = QComboBox()
        self.sources.setMinimumWidth(260)
        self.sources.currentIndexChanged.connect(self._source_selected)
        self.add_btn = QPushButton("+ ADD")
        self.add_btn.clicked.connect(self._add_source)
        self.start_btn = QPushButton("▶ START", objectName="Primary")
        self.start_btn.clicked.connect(self._start)
        self.pause_btn = QPushButton("❚❚ PAUSE")
        self.pause_btn.clicked.connect(self._toggle_pause)
        self.stop_btn = QPushButton("■ STOP", objectName="Danger")
        self.stop_btn.clicked.connect(self._stop)
        for w in (self.sources, self.add_btn):
            row.addWidget(w)
        row.addStretch(1)
        for w in (self.start_btn, self.pause_btn, self.stop_btn):
            row.addWidget(w)
        controls.body.addLayout(row)
        self.progress = QProgressBar()
        self.progress.setRange(0, 1)
        controls.body.addWidget(self.progress)
        self.readout = QLabel(objectName="Readout")
        controls.body.addWidget(self.readout)
        self.content.addWidget(controls)

        body = QHBoxLayout()
        body.setSpacing(14)
        video_panel = Panel("Feed", meta="DETECTION OVERLAY")
        self.video = VideoView()
        video_panel.body.addWidget(self.video, 1)
        body.addWidget(video_panel, 3)
        feed_panel = Panel("Decisions", meta="LATEST FIRST")
        feed_panel.setMinimumWidth(340)
        self.feed = QListWidget(objectName="FeedList")
        self.feed.setVerticalScrollMode(QListWidget.ScrollPerPixel)
        self.feed.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        feed_panel.body.addWidget(self.feed, 1)
        body.addWidget(feed_panel, 1)
        self.content.addLayout(body, 1)

        self._reload_sources()
        self._set_state("idle")

    def _reload_sources(self, select_id: int | None = None) -> None:
        self.sources.blockSignals(True)
        self.sources.clear()
        registered = self.ctx.storage.sources.all()
        for s in registered:
            self.sources.addItem(f"{s.name}  [{s.kind}]", s.id)
        known = {resolve_file(s.uri) for s in registered if s.kind == "file"}
        suggestions = [p for p in suggested_videos() if p.resolve() not in known]
        if suggestions and registered:
            self.sources.insertSeparator(self.sources.count())
        for p in suggestions:
            self.sources.addItem(f"{p.name}  [assets · new]", str(p))
        self.sources.blockSignals(False)
        if select_id is not None:
            self.sources.setCurrentIndex(self.sources.findData(select_id))
        self._source_selected()

    def current_source(self) -> Source | None:
        sid = self.sources.currentData()
        return self.ctx.storage.sources.get(sid) if isinstance(sid, int) else None

    def _suggested_path(self) -> Path | None:
        data = self.sources.currentData()
        return Path(data) if isinstance(data, str) else None

    def _source_selected(self, *_):
        s, suggested = self.current_source(), self._suggested_path()
        self.ctx.bus.source_changed.emit(s.name if s else suggested.name if suggested else "")
        self.start_btn.setEnabled((s is not None or suggested is not None) and self.worker is None)
        if self.worker is None:
            self.readout.setText(self._describe(s) if s or not suggested else
                                 f"> SUGGESTED  {suggested.relative_to(config.ROOT).as_posix()}   ·   "
                                 f"RECORDED {file_time(suggested)} (file date)   ·   START registers it")

    def _register_suggestion(self, path: Path) -> Source:
        name, n = path.stem, 2
        while self.ctx.storage.sources.by_name(name):
            name, n = f"{path.stem}-{n}", n + 1
        uri = path.relative_to(config.ROOT).as_posix() if path.is_relative_to(config.ROOT) else str(path)
        src = self.ctx.storage.sources.add(name, "file", uri, file_time(path))
        self.ctx.storage.events.log("system", f"source '{src.name}' added from assets/")
        self._reload_sources(src.id)
        return src

    def _describe(self, s: Source | None) -> str:
        if s is None:
            return "> no source — add a video file to begin"
        runs = self.ctx.storage.runs.for_source(s.id)
        when = s.recorded_at or "live (processing time)"
        return f"> {s.kind.upper()}  {s.uri}   ·   RECORDED {when}   ·   {len(runs)} PREVIOUS RUN(S)"

    def _add_source(self) -> None:
        dlg = SourceDialog(self)
        if dlg.exec() != QDialog.Accepted:
            return
        v = dlg.values()
        if self.ctx.storage.sources.by_name(v["name"]):
            QMessageBox.warning(self, "Add source", f"A source named '{v['name']}' already exists.")
            return
        src = self.ctx.storage.sources.add(**v)
        self.ctx.storage.events.log("system", f"source '{src.name}' added ({src.kind})")
        self._reload_sources(src.id)

    def _start(self) -> None:
        if self.worker is not None:
            return
        suggested = self._suggested_path()
        src = self._register_suggestion(suggested) if suggested else self.current_source()
        if src is None:
            return
        if self.ctx.storage.runs.for_source(src.id):
            answer = QMessageBox.question(
                self, "Previous results",
                f"'{src.name}' was processed before.\n\nReplace the previous results "
                f"(sightings, reviews and crops of earlier runs)?\n\nNo = keep them and add a new run.",
                QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel, QMessageBox.No)
            if answer == QMessageBox.Cancel:
                return
            if answer == QMessageBox.Yes:
                replace_previous_runs(self.ctx.storage, self.ctx.crops, src.id)
        self.feed.clear()
        self.counts = dict.fromkeys(self.counts, 0)
        self.video.clear("LOADING MODELS…")
        self.worker = PipelineWorker(self.ctx.storage, self.ctx.crops, src, self)
        self.worker.state_changed.connect(self._set_state)
        self.worker.frame_ready.connect(self._on_frame)
        self.worker.sighting_added.connect(self._on_sighting)
        self.worker.failed.connect(lambda msg: QMessageBox.critical(self, "Processing failed", msg))
        self.worker.finished.connect(self._worker_done)
        self.worker.start()

    def _toggle_pause(self) -> None:
        if self.worker is None:
            return
        if self.worker.paused:
            self.worker.resume()
        else:
            self.worker.pause()

    def _stop(self) -> None:
        if self.worker is not None:
            self.worker.stop()
            self.video.set_overlay("STOPPING…")

    def _worker_done(self) -> None:
        self.worker.deleteLater()
        self.worker = None
        self._source_selected()
        self.ctx.bus.data_changed.emit()

    def _set_state(self, state: str) -> None:
        running = state in ("loading", "running", "paused")
        self.sources.setEnabled(not running)
        self.add_btn.setEnabled(not running)
        self.start_btn.setEnabled(not running and (self.current_source() or self._suggested_path()) is not None)
        self.pause_btn.setEnabled(state in ("running", "paused"))
        self.pause_btn.setText("▶ RESUME" if state == "paused" else "❚❚ PAUSE")
        self.stop_btn.setEnabled(running)
        if state == "paused":
            self.video.set_overlay("PAUSED")
        elif state == "running":
            self.video.set_overlay("")
        elif state in ("finished", "stopped", "failed"):
            self.video.set_overlay(f"RUN {state.upper()}")
            self.readout.setText(self._summary(state))
        self.ctx.bus.pipeline_state.emit(state)

    def _on_frame(self, image: QImage, frame: int, total: int, fps: float) -> None:
        self.video.show_image(image)
        if self.worker is not None and self.worker.paused:
            self.video.set_overlay("PAUSED")
        if total:
            self.progress.setRange(0, total)
            self.progress.setValue(frame)
        else:
            self.progress.setRange(0, 0)
        of = f"/{total}" if total else ""
        self.readout.setText(f"> FRAME {frame}{of}   ·   {fps:.1f} FPS   ·   " + self._counts_text())

    def _on_sighting(self, s: Sighting) -> None:
        self.counts["vehicles"] += 1
        if s.status == "confirmed":
            self.counts["confirmed"] += 1
        if s.review == "pending":
            self.counts["review"] += 1
        if s.status == "no_plate":
            return
        item = QListWidgetItem()
        row = FeedRow(s, self.ctx.crops.load(s.plate_crop))
        item.setSizeHint(row.sizeHint())
        self.feed.insertItem(0, item)
        self.feed.setItemWidget(item, row)
        while self.feed.count() > FEED_LIMIT:
            self.feed.takeItem(self.feed.count() - 1)
        self.ctx.bus.data_changed.emit()

    def _counts_text(self) -> str:
        c = self.counts
        return f"VEHICLES {c['vehicles']}   ·   CONFIRMED {c['confirmed']}   ·   TO REVIEW {c['review']}"

    def _summary(self, state: str) -> str:
        return f"> RUN {state.upper()}   ·   " + self._counts_text()

    def shutdown(self) -> None:
        if self.worker is not None:
            self.worker.stop()
            self.worker.wait(10000)
