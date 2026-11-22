from __future__ import annotations

import base64
import html

import cv2
import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QCheckBox, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QPushButton,
                               QVBoxLayout, QWidget)

from app.gui import theme
from app.gui.map_view import MapView
from app.gui.pages.base import Page
from app.gui.pages.logs import combo
from app.gui.pages.monitor import STATUS_TAGS
from app.gui.sighting_dialog import SightingDialog
from app.gui.widgets import Panel
from app.services.geo import GeoMapper
from app.storage import Sighting, Source

PALETTE = (theme.DATA, "#60a5fa", "#a78bfa", "#f472b6", theme.OK, "#facc15")
MAX_PATHS = 400
MAX_POINTS = 40


def smooth(points: np.ndarray, window: int = 7) -> np.ndarray:
    if len(points) < window:
        return points
    kernel = np.ones(window) / window
    pad = window // 2
    padded = np.pad(points, ((pad, pad), (0, 0)), mode="edge")
    return np.column_stack([np.convolve(padded[:, i], kernel, mode="valid") for i in range(2)])


def thin(points: np.ndarray, limit: int = MAX_POINTS) -> np.ndarray:
    if len(points) <= limit:
        return points
    idx = np.linspace(0, len(points) - 1, limit).round().astype(int)
    return points[idx]


def thumbnail(img, width: int = 220) -> str | None:
    if img is None:
        return None
    h, w = img.shape[:2]
    if w > width:
        img = cv2.resize(img, (width, int(h * width / w)))
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 80])
    return "data:image/jpeg;base64," + base64.b64encode(buf).decode() if ok else None


class GeoPage(Page):
    code, title = "06", "Geo"
    subtitle = "Vehicle paths of calibrated sources projected on the satellite map"

    def build(self) -> None:
        self._mappers: dict[int, tuple[str, GeoMapper]] = {}
        self._shown = False
        self.sources: list[Source] = []

        body = QHBoxLayout()
        body.setSpacing(14)
        body.addWidget(self._side_panel())
        map_panel = Panel("Map", meta="Esri World Imagery · click a path for details")
        self.map = MapView()
        self.map.open_requested.connect(self._open_sighting)
        map_panel.body.addWidget(self.map, 1)
        body.addWidget(map_panel, 1)
        self.content.addLayout(body, 1)
        self.ctx.bus.data_changed.connect(lambda: self.isVisible() and self.reload(fit=False))

    def _side_panel(self) -> QWidget:
        side = QWidget()
        side.setFixedWidth(360)
        lay = QVBoxLayout(side)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(14)

        src_panel = Panel("Sources")
        self.source_list = QListWidget(objectName="FeedList")
        self.source_list.setMinimumHeight(150)
        self.source_list.itemSelectionChanged.connect(self._update_buttons)
        self.source_list.itemDoubleClicked.connect(lambda *_: self._calibrate())
        src_panel.body.addWidget(self.source_list)
        row = QHBoxLayout()
        self.calibrate_btn = QPushButton("CALIBRATE", objectName="Primary")
        self.calibrate_btn.clicked.connect(self._calibrate)
        self.reset_btn = QPushButton("RESET")
        self.reset_btn.clicked.connect(self._reset_calibration)
        row.addWidget(self.calibrate_btn, 1)
        row.addWidget(self.reset_btn)
        src_panel.body.addLayout(row)
        lay.addWidget(src_panel)

        f_panel = Panel("Filters")
        self.f_plate = QLineEdit()
        self.f_plate.setPlaceholderText("plate contains…")
        self.f_plate.textChanged.connect(lambda *_: self.reload())
        self.f_source = combo([("ALL SOURCES", None)])
        self.f_source.currentIndexChanged.connect(lambda *_: self.reload())
        self.f_status = combo([("ANY STATUS", None)] + [(v, k) for k, v in STATUS_TAGS.items()])
        self.f_status.currentIndexChanged.connect(lambda *_: self.reload())
        self.f_wanted = QCheckBox("WANTED PLATES ONLY")
        self.f_wanted.toggled.connect(lambda *_: self.reload())
        for w in (self.f_plate, self.f_source, self.f_status, self.f_wanted):
            f_panel.body.addWidget(w)
        fit = QPushButton("FIT MAP TO PATHS")
        fit.clicked.connect(lambda: self.map.fit_all())
        f_panel.body.addWidget(fit)
        self.readout = QLabel(objectName="Readout")
        self.readout.setWordWrap(True)
        f_panel.body.addWidget(self.readout)
        lay.addWidget(f_panel)

        legend = Panel("Legend")
        self.legend = QLabel(objectName="KeyLabel")
        self.legend.setWordWrap(True)
        self.legend.setTextFormat(Qt.RichText)
        legend.body.addWidget(self.legend)
        lay.addWidget(legend)
        lay.addStretch(1)
        return side

    def on_show(self) -> None:
        self.reload(fit=not self._shown)
        self._shown = True

    def _mapper(self, source: Source) -> GeoMapper | None:
        if not source.calibration:
            return None
        cached = self._mappers.get(source.id)
        if cached and cached[0] == source.calibration:
            return cached[1]
        try:
            mapper = GeoMapper.from_json(source.calibration)
        except (ValueError, KeyError):
            return None
        self._mappers[source.id] = (source.calibration, mapper)
        return mapper

    def _color(self, source_id: int) -> str:
        ids = [s.id for s in self.sources]
        return PALETTE[ids.index(source_id) % len(PALETTE)] if source_id in ids else theme.TEXT

    def _reload_sources(self) -> None:
        keep = self._selected_source()
        self.sources = self.ctx.storage.sources.all()
        lst = self.source_list
        lst.blockSignals(True)
        lst.clear()
        for s in self.sources:
            mapper = self._mapper(s)
            state = f"CALIBRATED · {len(mapper.image_points)} pts" if mapper else "NOT CALIBRATED"
            item = QListWidgetItem(f"{'●' if mapper else '○'}  {s.name}\n    {state}")
            item.setData(Qt.UserRole, s.id)
            item.setForeground(QColor(self._color(s.id) if mapper else theme.MUTED))
            lst.addItem(item)
            if keep and s.id == keep.id:
                item.setSelected(True)
        lst.blockSignals(False)

        current = self.f_source.currentData()
        self.f_source.blockSignals(True)
        self.f_source.clear()
        self.f_source.addItem("ALL SOURCES", None)
        for s in self.sources:
            if s.calibration:
                self.f_source.addItem(s.name, s.id)
        i = self.f_source.findData(current)
        self.f_source.setCurrentIndex(max(i, 0))
        self.f_source.blockSignals(False)
        self._update_buttons()

    def _selected_source(self) -> Source | None:
        items = self.source_list.selectedItems() if hasattr(self, "source_list") else []
        if not items:
            return None
        sid = items[0].data(Qt.UserRole)
        return next((s for s in self.sources if s.id == sid), None)

    def _update_buttons(self) -> None:
        s = self._selected_source()
        self.calibrate_btn.setEnabled(s is not None)
        self.calibrate_btn.setText("RECALIBRATE" if s and s.calibration else "CALIBRATE")
        self.reset_btn.setEnabled(bool(s and s.calibration))

    def reload(self, fit: bool = True) -> None:
        self._reload_sources()
        calibrated = {s.id: s for s in self.sources if self._mapper(s)}
        wanted = {w.plate for w in self.ctx.storage.wanted.all(active_only=True)}
        source_id = self.f_source.currentData()

        self.map.clear_markers()
        self.map.clear_paths()
        for s in calibrated.values():
            if source_id is None or s.id == source_id:
                self.map.add_camera(s.lat, s.lon, s.name, self._color(s.id))

        sightings: list[Sighting] = []
        if calibrated:
            found = self.ctx.storage.sightings.search(plate=self.f_plate.text().strip() or None,
                                                      status=self.f_status.currentData(),
                                                      source_id=source_id, limit=2000)
            sightings = [s for s in found if s.source_id in calibrated]
            if self.f_wanted.isChecked():
                sightings = [s for s in sightings if (s.final_plate or s.plate) in wanted]

        items, skipped = [], 0
        for s in sightings[:MAX_PATHS]:
            item = self._path_item(s, calibrated[s.source_id], wanted)
            if item:
                items.append(item)
            else:
                skipped += 1
        self.map.add_paths(items)
        if fit:
            self.map.fit_all()

        hits = sum(1 for i in items if i["wanted"])
        more = f" · showing first {MAX_PATHS}" if len(sightings) > MAX_PATHS else ""
        self.readout.setText(f"> {len(items)} PATHS · {len(calibrated)}/{len(self.sources)} SOURCES CALIBRATED"
                             f"{more}" + (f" · {hits} WANTED" if hits else "")
                             + (f"\n> {skipped} sightings without a usable path" if skipped else ""))
        if not calibrated:
            self.readout.setText("> no calibrated source yet · select a source and press CALIBRATE")
        rows = [f"<span style='color:{self._color(s.id)}'>━━</span>&nbsp; {html.escape(s.name)}"
                for s in calibrated.values()]
        rows += [f"<span style='color:{theme.DANGER}'>━━</span>&nbsp; wanted plate",
                 "○ start &nbsp;·&nbsp; ◉ end (direction of travel)",
                 f"<span style='color:{theme.DATA}'>◌</span>&nbsp; calibrated view centre"]
        self.legend.setText("<br>".join(rows))

    def _path_item(self, s: Sighting, source: Source, wanted: set[str]) -> dict | None:
        raw = self.ctx.storage.sightings.path(s.id)
        if len(raw) < 2:
            return None
        pts = thin(smooth(np.array([(x, y) for _, x, y in raw], dtype=np.float64)))
        latlon = self._mapper(source).project(pts)
        plate = s.final_plate or s.plate
        is_wanted = plate in wanted
        crop = thumbnail(self.ctx.crops.load(s.vehicle_crop))
        rows = [f"<div class='pop-plate'>{html.escape(plate or 'NO PLATE')}</div>",
                f"<span class='pop-key'>STATUS</span> {STATUS_TAGS.get(s.status, s.status)}",
                f"<span class='pop-key'>SOURCE</span> {html.escape(source.name)}",
                f"<span class='pop-key'>SEEN</span> {html.escape((s.first_seen or '')[:19])}",
                f"<span class='pop-key'>VEHICLE</span> {html.escape((s.color or '?') + ' ' + (s.vehicle_type or ''))}"]
        if is_wanted:
            rows.insert(1, f"<b style='color:{theme.DANGER}'>⚠ WANTED</b>")
        if crop:
            rows.append(f"<img class='pop-img' src='{crop}'>")
        return {"id": s.id, "points": [[round(a, 7), round(b, 7)] for a, b in latlon],
                "color": theme.DANGER if is_wanted else self._color(s.source_id),
                "wanted": is_wanted, "popup": "<br>".join(rows)}

    def _calibrate(self) -> None:
        from app.gui.calibration import CalibrationDialog
        s = self._selected_source()
        if s is None:
            return
        if CalibrationDialog(self.ctx, s, self.window()).exec():
            self.reload(fit=True)

    def _reset_calibration(self) -> None:
        from PySide6.QtWidgets import QMessageBox
        s = self._selected_source()
        if not s or not s.calibration:
            return
        if QMessageBox.question(self, "Reset calibration",
                                f"Remove the calibration of {s.name}? Its paths will disappear from the map.") \
                != QMessageBox.Yes:
            return
        s.calibration, s.lat, s.lon = None, None, None
        self.ctx.storage.sources.update(s)
        self.ctx.storage.events.log("geo", f"calibration of {s.name} removed by {self.ctx.operator}", level="warning")
        self.ctx.bus.data_changed.emit()
        self.reload()

    def _open_sighting(self, sighting_id: int) -> None:
        s = self.ctx.storage.sightings.get(sighting_id)
        if s:
            SightingDialog(self.ctx, s, self.window()).exec()
