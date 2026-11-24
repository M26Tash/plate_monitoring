from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QComboBox, QFormLayout, QHBoxLayout, QLabel, QLayout, QLineEdit, QListWidget,
                               QListWidgetItem, QPushButton, QScrollArea, QVBoxLayout, QWidget)

from app.gui import theme
from app.gui.pages.base import Page
from app.gui.pages.logs import cell, make_table
from app.gui.pages.monitor import STATUS_TAGS
from app.gui.pages.review import CropBox
from app.gui.sighting_dialog import SightingDialog
from app.gui.widgets import Panel
from app.services.color import COLORS
from app.services.registry import RegistryService
from app.storage import Vehicle

COLUMNS = ("PLATE", "OWNER (MOCK)", "PROVINCE", "MAKE / MODEL", "COLOUR", "TYPE", "SIGHTINGS", "LAST SEEN")


class RegistryPage(Page):
    code, title = "05", "Registry"
    subtitle = "Vehicle profiles: owners are generated mock data, colour and type come from the sightings"

    def build(self) -> None:
        self.service = RegistryService(self.ctx.storage)
        self.items: list[Vehicle] = []
        self.current: Vehicle | None = None

        top = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("search plate, owner or model")
        self.search.textChanged.connect(lambda *_: self.reload())
        top.addWidget(self.search, 1)
        mock = QLabel("MOCK OWNER DATA · NOT REAL PEOPLE", objectName="FeedTag")
        mock.setStyleSheet(f"color: {theme.WARN}; border: 1px solid {theme.WARN};")
        top.addWidget(mock)
        self.content.addLayout(top)

        body = QHBoxLayout()
        body.setSpacing(14)
        table_panel = Panel("Vehicles")
        self.counter = QLabel(objectName="Readout")
        table_panel.body.addWidget(self.counter)
        self.table = make_table(COLUMNS, 1)
        self.table.setSortingEnabled(False)
        self.table.setWordWrap(False)
        self.table.horizontalHeader().setMinimumSectionSize(60)
        self.table.itemSelectionChanged.connect(self._select)
        table_panel.body.addWidget(self.table, 1)
        body.addWidget(table_panel, 3)
        body.addWidget(self._detail_panel(), 2)
        self.content.addLayout(body, 1)
        self.ctx.bus.data_changed.connect(lambda: self.isVisible() and self.reload(keep=True))

    def _detail_panel(self) -> Panel:
        panel = Panel("Profile")
        panel.setMinimumWidth(420)
        inner = QWidget()
        lay = QVBoxLayout(inner)
        lay.setContentsMargins(0, 0, 12, 0)
        lay.setSizeConstraint(QLayout.SetMinimumSize)
        lay.setSpacing(10)
        self.plate_label = QLabel("—", objectName="AlertPlate")
        lay.addWidget(self.plate_label)
        self.wanted_label = QLabel(objectName="FeedTag")
        self.wanted_label.hide()
        lay.addWidget(self.wanted_label, alignment=Qt.AlignLeft)
        self.photo = CropBox(190, "Vehicle")
        lay.addWidget(self.photo)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignLeft)
        self.f_owner = QLineEdit()
        self.f_city = QLineEdit()
        self.f_phone = QLineEdit()
        self.f_model = QLineEdit()
        self.f_model.setPlaceholderText("e.g. Fiat Egea (typed by the analyst)")
        self.f_color = QComboBox()
        self.f_color.setEditable(True)
        self.f_color.addItems(("",) + COLORS)
        self.f_type = QComboBox()
        self.f_type.setEditable(True)
        self.f_type.addItems(("", "car", "motorcycle", "bus", "truck"))
        self.f_notes = QLineEdit()
        for label, w in (("OWNER (MOCK)", self.f_owner), ("PROVINCE", self.f_city), ("PHONE (MOCK)", self.f_phone),
                         ("MAKE / MODEL", self.f_model), ("COLOUR", self.f_color), ("TYPE", self.f_type),
                         ("NOTES", self.f_notes)):
            form.addRow(label, w)
        lay.addLayout(form)
        buttons = QHBoxLayout()
        self.save_btn = QPushButton("SAVE", objectName="Primary")
        self.save_btn.clicked.connect(self._save)
        self.saved = QLabel(objectName="KeyLabel")
        buttons.addWidget(self.save_btn)
        buttons.addWidget(self.saved, 1)
        lay.addLayout(buttons)

        lay.addSpacing(6)
        lay.addWidget(QLabel("SIGHTINGS OF THIS PLATE  (double-click to open)", objectName="KeyLabel"))
        self.sightings = QListWidget(objectName="FeedList")
        self.sightings.setMinimumHeight(160)
        self.sightings.itemDoubleClicked.connect(self._open_sighting)
        lay.addWidget(self.sightings)
        lay.addStretch(1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setWidget(inner)
        panel.body.addWidget(scroll, 1)
        return panel

    def on_show(self) -> None:
        colored = self.service.backfill_colors(self.ctx.crops)
        created = self.service.sync_all()
        if created or colored:
            self.ctx.bus.data_changed.emit()
        self.reload(keep=True)

    def reload(self, keep: bool = False) -> None:
        keep_plate = self.current.plate if keep and self.current else None
        stats = self.ctx.storage.sightings.plate_stats()
        wanted = {w.plate for w in self.ctx.storage.wanted.all(active_only=True)}
        self.items = self.ctx.storage.vehicles.search(self.search.text())
        t = self.table
        t.blockSignals(True)
        t.setRowCount(len(self.items))
        for r, v in enumerate(self.items):
            seen, last = stats.get(v.plate, (0, None))
            values = [cell(v.plate, theme.DANGER if v.plate in wanted else theme.TEXT, bold=True),
                      cell(v.owner_name or "—"), cell(v.owner_city or "—"), cell(v.make_model or "—"),
                      cell((v.color or "—").upper()), cell((v.vehicle_type or "—").upper()),
                      cell(seen), cell((last or "—")[5:16] if last else "—")]
            for c, item in enumerate(values):
                t.setItem(r, c, item)
        t.blockSignals(False)
        self.counter.setText(f"> {len(self.items)} VEHICLES  ·  {sum(1 for v in self.items if v.plate in wanted)} ON WATCHLIST")
        row = next((i for i, v in enumerate(self.items) if v.plate == keep_plate), 0 if self.items else -1)
        if row >= 0:
            t.selectRow(row)
        self._select()

    def _select(self) -> None:
        rows = self.table.selectionModel().selectedRows() if self.table.selectionModel() else []
        self.current = self.items[rows[0].row()] if rows else None
        v = self.current
        self.saved.clear()
        for w in (self.f_owner, self.f_city, self.f_phone, self.f_model, self.f_color, self.f_type,
                  self.f_notes, self.save_btn):
            w.setEnabled(v is not None)
        self.sightings.clear()
        if v is None:
            self.plate_label.setText("—")
            self.photo.set_image(None, "NO VEHICLE")
            self.wanted_label.hide()
            return
        self.plate_label.setText(v.plate)
        w = self.ctx.storage.wanted.by_plate(v.plate)
        if w and w.active:
            self.wanted_label.setText(f"WANTED · {w.priority.upper()} · {w.reason or 'no reason'}")
            self.wanted_label.setStyleSheet(f"color: white; background: {theme.DANGER};")
            self.wanted_label.show()
        else:
            self.wanted_label.hide()
        self.f_owner.setText(v.owner_name or "")
        self.f_city.setText(v.owner_city or "")
        self.f_phone.setText(v.owner_phone or "")
        self.f_model.setText(v.make_model or "")
        self.f_color.setCurrentText(v.color or "")
        self.f_type.setCurrentText(v.vehicle_type or "")
        self.f_notes.setText(v.notes or "")
        history = self.ctx.storage.sightings.by_plate(v.plate)
        self.photo.set_image(self.ctx.crops.load(history[-1].vehicle_crop) if history else None)
        names = {s.id: s.name for s in self.ctx.storage.sources.all()}
        for s in reversed(history):
            item = QListWidgetItem(f"{s.first_seen[:19]}  ·  {names.get(s.source_id, '?')}  ·  "
                                   f"{STATUS_TAGS.get(s.status, s.status)}  ·  {(s.color or '—').upper()}")
            item.setData(Qt.UserRole, s.id)
            item.setForeground(QColor(theme.STATUS_COLORS.get(s.status, theme.TEXT)))
            self.sightings.addItem(item)

    def _save(self) -> None:
        v = self.current
        if v is None:
            return
        v.owner_name = self.f_owner.text().strip() or None
        v.owner_city = self.f_city.text().strip() or None
        v.owner_phone = self.f_phone.text().strip() or None
        v.make_model = self.f_model.text().strip() or None
        v.color = self.f_color.currentText().strip().lower() or None
        v.vehicle_type = self.f_type.currentText().strip().lower() or None
        v.notes = self.f_notes.text().strip() or None
        self.ctx.storage.vehicles.save(v)
        self.ctx.storage.events.log("registry", f"profile of {v.plate} edited by {self.ctx.operator}", plate=v.plate)
        self.reload(keep=True)
        self.saved.setText("✓ saved")

    def _open_sighting(self, item: QListWidgetItem) -> None:
        s = self.ctx.storage.sightings.get(item.data(Qt.UserRole))
        if s:
            SightingDialog(self.ctx, s, self.window()).exec()
