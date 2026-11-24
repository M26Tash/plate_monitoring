from __future__ import annotations

import csv
from datetime import datetime

from PySide6.QtCore import QDateTime, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QComboBox, QDateTimeEdit, QFileDialog, QHBoxLayout,
                               QHeaderView, QLabel, QLineEdit, QMessageBox, QPushButton, QTableWidget,
                               QTableWidgetItem, QTabWidget, QVBoxLayout, QWidget)

from app.gui import theme
from app.gui.pages.base import Page
from app.gui.pages.monitor import STATUS_TAGS
from app.gui.sighting_dialog import LEVEL_COLORS, SightingDialog
from app.gui.widgets import Panel

LIMIT = 2000
SIGHTING_COLUMNS = ("TIME", "PLATE", "STATUS", "REVIEW", "SOURCE", "TYPE", "COLOUR", "TRACK", "READS", "SHARE")
EVENT_COLUMNS = ("TIME", "LEVEL", "KIND", "PLATE", "MESSAGE")
EVENT_KINDS = ("system", "run", "sighting", "review", "alert", "watchlist", "registry", "geo")


def make_table(columns: tuple[str, ...], stretch: int) -> QTableWidget:
    t = QTableWidget(0, len(columns))
    t.setHorizontalHeaderLabels(columns)
    t.verticalHeader().hide()
    t.setSelectionBehavior(QAbstractItemView.SelectRows)
    t.setSelectionMode(QAbstractItemView.SingleSelection)
    t.setEditTriggers(QAbstractItemView.NoEditTriggers)
    t.setShowGrid(False)
    t.setAlternatingRowColors(True)
    t.setSortingEnabled(True)
    h = t.horizontalHeader()
    h.setSectionResizeMode(QHeaderView.ResizeToContents)
    h.setSectionResizeMode(stretch, QHeaderView.Stretch)
    return t


def cell(text, color: str | None = None, bold: bool = False, data=None) -> QTableWidgetItem:
    item = QTableWidgetItem(str(text))
    if color:
        item.setForeground(QColor(color))
    if bold:
        item.setFont(theme.mono(10, bold=True))
    if data is not None:
        item.setData(Qt.UserRole, data)
    return item


def combo(items: list[tuple[str, object]]) -> QComboBox:
    c = QComboBox()
    for label, value in items:
        c.addItem(label, value)
    return c


class LogsPage(Page):
    code, title = "04", "Logs"
    subtitle = "Every sighting and event: search, filter, open a record, export to CSV"

    def build(self) -> None:
        self.tabs = QTabWidget()
        self.tabs.addTab(self._sightings_tab(), "SIGHTINGS")
        self.tabs.addTab(self._events_tab(), "EVENTS")
        self.tabs.currentChanged.connect(lambda *_: self.reload())
        self.content.addWidget(self.tabs, 1)
        self.ctx.bus.data_changed.connect(lambda: self.isVisible() and self.reload())

    def _sightings_tab(self) -> QWidget:
        tab = QWidget()
        lay = QVBoxLayout(tab)
        lay.setContentsMargins(0, 12, 0, 0)
        lay.setSpacing(10)

        row = QHBoxLayout()
        self.s_plate = QLineEdit()
        self.s_plate.setPlaceholderText("plate contains…")
        self.s_source = QComboBox()
        self.s_source.setMinimumWidth(170)
        self.s_source.setSizeAdjustPolicy(QComboBox.AdjustToContents)
        self.s_status = combo([("ANY STATUS", None)] + [(v, k) for k, v in STATUS_TAGS.items()])
        self.s_review = combo([("ANY REVIEW", None), ("PENDING", "pending"), ("DONE", "done"), ("NOT NEEDED", "none")])
        self.s_range = QCheckBox("TIME RANGE")
        now = QDateTime.currentDateTime()
        self.s_from = QDateTimeEdit(now.addDays(-30))
        self.s_to = QDateTimeEdit(now.addDays(1))
        for d in (self.s_from, self.s_to):
            d.setDisplayFormat("yyyy-MM-dd HH:mm")
            d.setCalendarPopup(True)
            d.setEnabled(False)
            d.dateTimeChanged.connect(lambda *_: self.reload())
        self.s_range.toggled.connect(lambda on: (self.s_from.setEnabled(on), self.s_to.setEnabled(on), self.reload()))
        self.s_plate.textChanged.connect(lambda *_: self.reload())
        for c in (self.s_source, self.s_status, self.s_review):
            c.currentIndexChanged.connect(lambda *_: self.reload())
        row.addWidget(self.s_plate, 1)
        for w in (self.s_source, self.s_status, self.s_review, self.s_range, self.s_from, QLabel("→"), self.s_to):
            row.addWidget(w)
        lay.addLayout(row)

        panel = Panel("Sightings", meta="DOUBLE-CLICK TO OPEN")
        bar = QHBoxLayout()
        self.s_counter = QLabel(objectName="Readout")
        bar.addWidget(self.s_counter, 1)
        export = QPushButton("EXPORT CSV")
        export.clicked.connect(lambda: self._export(self.s_table, "sightings"))
        bar.addWidget(export)
        panel.body.addLayout(bar)
        self.s_table = make_table(SIGHTING_COLUMNS, 4)
        self.s_table.doubleClicked.connect(lambda idx: self._open_row(self.s_table, idx.row()))
        panel.body.addWidget(self.s_table, 1)
        lay.addWidget(panel, 1)
        return tab

    def _reload_sources(self) -> None:
        current = self.s_source.currentData()
        self.s_source.blockSignals(True)
        self.s_source.clear()
        self.s_source.addItem("ANY SOURCE", None)
        for s in self.ctx.storage.sources.all():
            self.s_source.addItem(s.name, s.id)
        i = self.s_source.findData(current)
        self.s_source.setCurrentIndex(max(i, 0))
        self.s_source.blockSignals(False)

    def _reload_sightings(self) -> None:
        since = until = None
        if self.s_range.isChecked():
            since = self.s_from.dateTime().toString("yyyy-MM-dd HH:mm:00")
            until = self.s_to.dateTime().toString("yyyy-MM-dd HH:mm:59")
        rows = self.ctx.storage.sightings.search(plate=self.s_plate.text().strip() or None,
                                                 status=self.s_status.currentData(),
                                                 source_id=self.s_source.currentData(),
                                                 since=since, until=until, limit=LIMIT)
        review = self.s_review.currentData()
        if review:
            rows = [s for s in rows if (s.review or "none") == review]
        names = {s.id: s.name for s in self.ctx.storage.sources.all()}
        wanted = {w.plate for w in self.ctx.storage.wanted.all(active_only=True)}
        t = self.s_table
        t.setSortingEnabled(False)
        t.setRowCount(len(rows))
        for r, s in enumerate(rows):
            plate = s.final_plate or s.plate or "UNREAD"
            color = theme.STATUS_COLORS.get(s.status, theme.TEXT)
            values = [
                cell(s.first_seen[:19], data=s.id),
                cell(plate, theme.DANGER if s.final_plate in wanted else theme.TEXT, bold=True),
                cell(STATUS_TAGS.get(s.status, s.status), color),
                cell({"pending": "PENDING", "done": "DONE"}.get(s.review, "—"),
                     theme.WARN if s.review == "pending" else theme.MUTED),
                cell(names.get(s.source_id, "?")),
                cell(s.vehicle_type.upper()),
                cell((s.color or "—").upper()),
                cell(s.track_id),
                cell(s.reads),
                cell(f"{s.share:.2f}"),
            ]
            for c, item in enumerate(values):
                t.setItem(r, c, item)
        t.setSortingEnabled(True)
        more = "  (limit reached: narrow the filters)" if len(rows) >= LIMIT else ""
        confirmed = sum(1 for s in rows if s.status == "confirmed")
        self.s_counter.setText(f"> {len(rows)} SIGHTINGS  ·  {confirmed} CONFIRMED  ·  "
                               f"{sum(1 for s in rows if s.review == 'pending')} PENDING REVIEW{more}")

    def _events_tab(self) -> QWidget:
        tab = QWidget()
        lay = QVBoxLayout(tab)
        lay.setContentsMargins(0, 12, 0, 0)
        lay.setSpacing(10)
        row = QHBoxLayout()
        self.e_text = QLineEdit()
        self.e_text.setPlaceholderText("message or plate contains…")
        self.e_kind = combo([("ANY KIND", None)] + [(k.upper(), k) for k in EVENT_KINDS])
        self.e_level = combo([("ANY LEVEL", None), ("INFO", "info"), ("WARNING", "warning"), ("ALERT", "alert")])
        self.e_text.textChanged.connect(lambda *_: self.reload())
        for c in (self.e_kind, self.e_level):
            c.currentIndexChanged.connect(lambda *_: self.reload())
        row.addWidget(self.e_text, 1)
        row.addWidget(self.e_kind)
        row.addWidget(self.e_level)
        lay.addLayout(row)

        panel = Panel("Events", meta="DOUBLE-CLICK OPENS THE SIGHTING")
        bar = QHBoxLayout()
        self.e_counter = QLabel(objectName="Readout")
        bar.addWidget(self.e_counter, 1)
        export = QPushButton("EXPORT CSV")
        export.clicked.connect(lambda: self._export(self.e_table, "events"))
        bar.addWidget(export)
        panel.body.addLayout(bar)
        self.e_table = make_table(EVENT_COLUMNS, 4)
        self.e_table.doubleClicked.connect(lambda idx: self._open_row(self.e_table, idx.row()))
        panel.body.addWidget(self.e_table, 1)
        lay.addWidget(panel, 1)
        return tab

    def _reload_events(self) -> None:
        events = self.ctx.storage.events.recent(limit=LIMIT, kind=self.e_kind.currentData(),
                                                level=self.e_level.currentData(),
                                                text=self.e_text.text().strip() or None)
        t = self.e_table
        t.setSortingEnabled(False)
        t.setRowCount(len(events))
        for r, e in enumerate(events):
            color = LEVEL_COLORS.get(e.level, theme.TEXT)
            values = [cell(e.time[:19], data=e.sighting_id), cell(e.level.upper(), color), cell(e.kind.upper()),
                      cell(e.plate or "—", bold=bool(e.plate)), cell(e.message, color)]
            for c, item in enumerate(values):
                t.setItem(r, c, item)
        t.setSortingEnabled(True)
        alerts = sum(1 for e in events if e.level == "alert")
        self.e_counter.setText(f"> {len(events)} EVENTS  ·  {alerts} ALERTS")

    def on_show(self) -> None:
        self._reload_sources()
        self.reload()

    def reload(self) -> None:
        if self.tabs.currentIndex() == 0:
            self._reload_sightings()
        else:
            self._reload_events()

    def _open_row(self, table: QTableWidget, row: int) -> None:
        item = table.item(row, 0)
        sid = item.data(Qt.UserRole) if item else None
        sighting = self.ctx.storage.sightings.get(sid) if sid else None
        if sighting:
            SightingDialog(self.ctx, sighting, self.window()).exec()

    def _export(self, table: QTableWidget, name: str) -> None:
        default = f"oculus_{name}_{datetime.now():%Y%m%d_%H%M}.csv"
        path, _ = QFileDialog.getSaveFileName(self, "Export CSV", default, "CSV (*.csv)")
        if not path:
            return
        headers = [table.horizontalHeaderItem(c).text() for c in range(table.columnCount())]
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(headers)
            for r in range(table.rowCount()):
                w.writerow([table.item(r, c).text() if table.item(r, c) else "" for c in range(table.columnCount())])
        self.ctx.storage.events.log("system", f"{table.rowCount()} {name} exported to CSV")
        QMessageBox.information(self, "Export", f"{table.rowCount()} rows saved to\n{path}")
