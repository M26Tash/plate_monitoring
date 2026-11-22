from __future__ import annotations

import re

import cv2
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QDialog, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton, QSizePolicy,
                               QVBoxLayout)

from app.gui import theme
from app.gui.map_view import MapView
from app.gui.pages.logs import cell, make_table
from app.gui.pages.monitor import bgr_to_pixmap
from app.gui.widgets import Panel
from app.services.geo import GeoMapper
from app.services.recorder import resolve_file
from app.storage import Source

COLUMNS = ("#", "PIXEL", "LAT, LON", "ERROR (m)")


def grab_frame(source: Source, at_ms: int = 1000):
    uri = source.uri
    if source.kind == "camera" and uri.isdigit():
        target = int(uri)
    elif source.kind == "file":
        target = str(resolve_file(uri))
    else:
        target = uri
    cap = cv2.VideoCapture(target)
    if source.kind == "file":
        cap.set(cv2.CAP_PROP_POS_MSEC, at_ms)
    ok, frame = cap.read()
    cap.release()
    return frame if ok else None


def error_color(metres: float) -> str:
    return theme.OK if metres < 2 else theme.WARN if metres < 5 else theme.DANGER


class FrameView(QLabel):
    clicked = Signal(float, float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumSize(480, 320)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setCursor(Qt.CrossCursor)
        self.frame = None
        self.points: list[tuple[float, float]] = []

    def set_frame(self, bgr) -> None:
        self.frame = bgr
        self._redraw()

    def set_points(self, points) -> None:
        self.points = list(points)
        self._redraw()

    def _redraw(self) -> None:
        if self.frame is None:
            self.setText("NO FRAME")
            return
        img = self.frame.copy()
        h, w = img.shape[:2]
        shown = min(self.width() / w, self.height() / h) or 1
        r = max(3, round(6 / shown))
        for i, (x, y) in enumerate(self.points, 1):
            c = (int(x), int(y))
            cv2.circle(img, c, r + 2, (0, 0, 0), -1)
            cv2.circle(img, c, r, (36, 165, 245), -1)
            cv2.putText(img, str(i), (c[0] + r + 4, c[1] - r), cv2.FONT_HERSHEY_SIMPLEX,
                        r / 5, (0, 0, 0), max(2, r // 2 + 2), cv2.LINE_AA)
            cv2.putText(img, str(i), (c[0] + r + 4, c[1] - r), cv2.FONT_HERSHEY_SIMPLEX,
                        r / 5, (36, 165, 245), max(1, r // 2), cv2.LINE_AA)
        self.setPixmap(bgr_to_pixmap(img, self.width(), self.height()))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._redraw()

    def mousePressEvent(self, e):
        pm = self.pixmap()
        if self.frame is None or pm is None or pm.isNull() or e.button() != Qt.LeftButton:
            return
        h, w = self.frame.shape[:2]
        scale = pm.width() / w
        off_x = (self.width() - pm.width()) / 2
        off_y = (self.height() - pm.height()) / 2
        x = (e.position().x() - off_x) / scale
        y = (e.position().y() - off_y) / scale
        if 0 <= x < w and 0 <= y < h:
            self.clicked.emit(x, y)


class CalibrationDialog(QDialog):

    def __init__(self, ctx, source: Source, parent=None):
        super().__init__(parent)
        self.ctx, self.source = ctx, source
        self.pixels: list[tuple[float, float]] = []
        self.geo: list[tuple[float, float]] = []
        self.mapper: GeoMapper | None = None
        self.setWindowTitle(f"Calibrate · {source.name}")
        self.resize(1440, 860)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(12)

        views = QHBoxLayout()
        views.setSpacing(12)
        frame_panel = Panel("Camera frame", meta=source.name)
        self.frame_view = FrameView()
        self.frame_view.clicked.connect(self._frame_clicked)
        frame_panel.body.addWidget(self.frame_view, 1)
        map_panel = Panel("Satellite map", meta="scroll to zoom · drag to pan")
        self.map = MapView()
        self.map.clicked.connect(self._map_clicked)
        map_panel.body.addWidget(self.map, 1)
        views.addWidget(frame_panel, 1)
        views.addWidget(map_panel, 1)
        lay.addLayout(views, 3)

        hint_row = QHBoxLayout()
        self.hint = QLabel(objectName="Readout")
        hint_row.addWidget(self.hint, 1)
        self.coord = QLineEdit()
        self.coord.setPlaceholderText("or paste lat, lon  (e.g. 41.012345, 28.987654)")
        self.coord.setMinimumWidth(360)
        self.coord.returnPressed.connect(self._paste_coord)
        self.coord_btn = QPushButton("ADD COORD")
        self.coord_btn.clicked.connect(self._paste_coord)
        hint_row.addWidget(self.coord)
        hint_row.addWidget(self.coord_btn)
        lay.addLayout(hint_row)

        bottom = QHBoxLayout()
        self.table = make_table(COLUMNS, 2)
        self.table.setSortingEnabled(False)
        self.table.setMaximumHeight(200)
        bottom.addWidget(self.table, 1)
        side = QVBoxLayout()
        self.summary = QLabel(objectName="KeyLabel")
        self.summary.setWordWrap(True)
        self.summary.setMinimumWidth(260)
        side.addWidget(self.summary)
        side.addStretch(1)
        buttons = QHBoxLayout()
        self.undo_btn = QPushButton("UNDO")
        self.undo_btn.clicked.connect(self._undo)
        self.clear_btn = QPushButton("CLEAR")
        self.clear_btn.clicked.connect(self._clear)
        self.save_btn = QPushButton("SAVE", objectName="Primary")
        self.save_btn.clicked.connect(self._save)
        cancel = QPushButton("CANCEL")
        cancel.clicked.connect(self.reject)
        for b in (self.undo_btn, self.clear_btn, cancel, self.save_btn):
            buttons.addWidget(b)
        side.addLayout(buttons)
        bottom.addLayout(side)
        lay.addLayout(bottom, 1)

        self.frame_view.set_frame(grab_frame(source))
        if source.calibration:
            try:
                saved = GeoMapper.from_json(source.calibration)
                self.pixels = [tuple(p) for p in saved.image_points]
                self.geo = [tuple(p) for p in saved.geo_points]
                self.map.set_view(saved.lat0, saved.lon0, 18)
            except (ValueError, KeyError):
                pass
        elif source.lat is not None and source.lon is not None:
            self.map.set_view(source.lat, source.lon, 18)
        self._refresh()

    def _frame_clicked(self, x: float, y: float) -> None:
        if len(self.pixels) == len(self.geo):
            self.pixels.append((round(x, 1), round(y, 1)))
            self._refresh()

    def _map_clicked(self, lat: float, lon: float) -> None:
        if len(self.pixels) == len(self.geo) + 1:
            self.geo.append((lat, lon))
            self._refresh()

    def _paste_coord(self) -> None:
        nums = re.findall(r"-?\d+(?:\.\d+)?", self.coord.text().replace(",", " "))
        if len(nums) != 2 or len(self.pixels) != len(self.geo) + 1:
            return
        lat, lon = float(nums[0]), float(nums[1])
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            return
        self.coord.clear()
        self._map_clicked(lat, lon)
        self.map.set_view(lat, lon, 18)

    def _undo(self) -> None:
        if len(self.pixels) > len(self.geo):
            self.pixels.pop()
        elif self.geo:
            self.geo.pop()
        self._refresh()

    def _clear(self) -> None:
        self.pixels.clear()
        self.geo.clear()
        self._refresh()

    def _refresh(self) -> None:
        n = len(self.geo)
        waiting_map = len(self.pixels) > n
        self.frame_view.set_points(self.pixels)
        self.map.clear_markers()
        for i, (lat, lon) in enumerate(self.geo, 1):
            self.map.add_marker(lat, lon, str(i))

        self.mapper, errors = None, []
        if n >= 4:
            try:
                self.mapper = GeoMapper(self.pixels[:n], self.geo[:n])
                errors = self.mapper.errors()
            except ValueError:
                self.mapper = None

        t = self.table
        t.setRowCount(len(self.pixels))
        for i, (x, y) in enumerate(self.pixels):
            geo = f"{self.geo[i][0]:.6f}, {self.geo[i][1]:.6f}" if i < n else "… click the map"
            err = cell(f"{errors[i]:.2f}", error_color(errors[i])) if errors else cell("—", theme.MUTED)
            for c, item in enumerate((cell(i + 1), cell(f"{x:.0f}, {y:.0f}"), cell(geo), err)):
                t.setItem(i, c, item)
        if t.rowCount():
            t.scrollToBottom()

        self.coord.setEnabled(waiting_map)
        self.coord_btn.setEnabled(waiting_map)
        if waiting_map:
            self.hint.setText(f"> POINT {n + 1}: click the SAME spot on the map, or paste its lat, lon")
        elif n < 4:
            self.hint.setText(f"> POINT {n + 1}: click a ground landmark on the frame "
                              f"(lane corner, crosswalk end, kerb, manhole) · {4 - n} more needed")
        elif self.mapper is None:
            self.hint.setText("> points are degenerate (on one line?) · spread them out or UNDO")
        else:
            self.hint.setText(f"> {n} PAIRS FITTED · add more points to improve, or SAVE")

        if errors:
            worst = max(errors)
            mean = sum(errors) / len(errors)
            self.summary.setText(f"MEAN ERROR  {mean:.2f} m\nWORST       {worst:.2f} m  (#{errors.index(worst) + 1})\n\n"
                                 "Under 2 m is good. Remove the worst point if it is far off.")
        else:
            self.summary.setText("Click 4 or more pairs: first on the frame, then the same spot on the map.\n"
                                 "Use points on the road surface, spread near/far and left/right.")
        self.undo_btn.setEnabled(bool(self.pixels))
        self.clear_btn.setEnabled(bool(self.pixels))
        self.save_btn.setEnabled(self.mapper is not None and not waiting_map)

    def _save(self) -> None:
        if self.mapper is None:
            return
        worst = max(self.mapper.errors())
        if worst > 5 and QMessageBox.question(
                self, "Large error", f"The worst point is {worst:.1f} m off. Save anyway?") != QMessageBox.Yes:
            return
        s = self.source
        s.calibration = self.mapper.to_json()
        s.lat, s.lon = self.mapper.lat0, self.mapper.lon0
        self.ctx.storage.sources.update(s)
        self.ctx.storage.events.log("geo", f"source {s.name} calibrated with {len(self.geo)} points "
                                           f"(worst error {worst:.2f} m) by {self.ctx.operator}")
        self.ctx.bus.data_changed.emit()
        self.accept()
