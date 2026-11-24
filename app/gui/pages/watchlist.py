from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QComboBox, QDialog, QDialogButtonBox,
                               QFileDialog, QFormLayout, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
                               QListWidget, QListWidgetItem, QMessageBox, QPushButton, QTableWidget,
                               QTableWidgetItem, QVBoxLayout)

from app.gui import theme
from app.gui.pages.base import Page
from app.gui.widgets import Panel
from app.services.review import is_turkish
from app.services.watchlist import PRIORITIES, WatchlistService
from app.storage import WantedPlate, normalize_plate

COLUMNS = ("PLATE", "PRIORITY", "REASON", "STATE", "SIGHTINGS", "LAST SEEN", "ADDED")
PRIORITY_COLORS = {"high": theme.DANGER, "medium": theme.WARN, "low": theme.MUTED}


class WantedDialog(QDialog):
    def __init__(self, parent=None, wanted: WantedPlate | None = None):
        super().__init__(parent)
        self.setWindowTitle("Edit wanted plate" if wanted else "Add wanted plate")
        self.setMinimumWidth(520)
        panel = Panel("Plate of interest")
        form = QFormLayout()
        self.plate = QLineEdit(objectName="PlateEdit")
        self.plate.setPlaceholderText("34ABC123")
        self.plate.textChanged.connect(self._validate)
        self.hint = QLabel(objectName="KeyLabel")
        self.reason = QLineEdit()
        self.reason.setPlaceholderText("why this plate is of interest")
        self.priority = QComboBox()
        self.priority.addItems(PRIORITIES)
        self.priority.setCurrentText("medium")
        self.notes = QLineEdit()
        self.active = QCheckBox("active (raises alerts)")
        self.active.setChecked(True)
        form.addRow("PLATE", self.plate)
        form.addRow("", self.hint)
        form.addRow("REASON", self.reason)
        form.addRow("PRIORITY", self.priority)
        form.addRow("NOTES", self.notes)
        form.addRow("", self.active)
        panel.body.addLayout(form)
        if wanted:
            self.plate.setText(wanted.plate)
            self.reason.setText(wanted.reason)
            self.priority.setCurrentText(wanted.priority)
            self.notes.setText(wanted.notes or "")
            self.active.setChecked(wanted.active)

        buttons = QDialogButtonBox()
        buttons.addButton(QPushButton("SAVE", objectName="Primary"), QDialogButtonBox.AcceptRole)
        buttons.addButton(QPushButton("CANCEL"), QDialogButtonBox.RejectRole)
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 20, 20, 20)
        lay.addWidget(panel)
        lay.addWidget(buttons)

    def _validate(self, text: str) -> None:
        if not text.strip():
            self.hint.setText("")
        elif is_turkish(text):
            self.hint.setText("✓ Turkish format")
            self.hint.setStyleSheet(f"color: {theme.OK};")
        else:
            self.hint.setText("! not a Turkish format — allowed (foreign plate)")
            self.hint.setStyleSheet(f"color: {theme.WARN};")

    def _accept(self) -> None:
        if not normalize_plate(self.plate.text()):
            QMessageBox.warning(self, "Watchlist", "Plate is required.")
            return
        self.accept()

    def values(self) -> dict:
        return dict(plate=normalize_plate(self.plate.text()), reason=self.reason.text().strip(),
                    priority=self.priority.currentText(), notes=self.notes.text().strip() or None,
                    active=self.active.isChecked())


class WatchlistPage(Page):
    code, title = "03", "Watchlist"
    subtitle = "Plates of interest: an exact sighting raises an alert, a 1-character near match goes to review"

    def build(self) -> None:
        self.service = WatchlistService(self.ctx.storage)
        self.items: list[WantedPlate] = []

        top = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("search plate or reason")
        self.search.textChanged.connect(lambda *_: self.reload())
        top.addWidget(self.search, 1)
        self.add_btn = QPushButton("+ ADD", objectName="Primary")
        self.import_btn = QPushButton("IMPORT CSV")
        self.edit_btn = QPushButton("EDIT")
        self.toggle_btn = QPushButton("ACTIVATE / PAUSE")
        self.remove_btn = QPushButton("REMOVE", objectName="Danger")
        self.add_btn.clicked.connect(self._add)
        self.import_btn.clicked.connect(self._import)
        self.edit_btn.clicked.connect(self._edit)
        self.toggle_btn.clicked.connect(self._toggle)
        self.remove_btn.clicked.connect(self._remove)
        for b in (self.add_btn, self.import_btn, self.edit_btn, self.toggle_btn, self.remove_btn):
            top.addWidget(b)
        self.content.addLayout(top)

        body = QHBoxLayout()
        body.setSpacing(14)
        table_panel = Panel("Plates of interest")
        self.counter = QLabel(objectName="Readout")
        table_panel.body.addWidget(self.counter)
        self.table = QTableWidget(0, len(COLUMNS))
        self.table.setHorizontalHeaderLabels(COLUMNS)
        self.table.verticalHeader().hide()
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setShowGrid(False)
        self.table.setAlternatingRowColors(True)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.doubleClicked.connect(lambda *_: self._edit())
        self.table.itemSelectionChanged.connect(self._selection_changed)
        table_panel.body.addWidget(self.table, 1)
        body.addWidget(table_panel, 2)

        alerts_panel = Panel("Recent alerts", meta="NEWEST FIRST")
        alerts_panel.setMinimumWidth(340)
        self.alerts = QListWidget(objectName="FeedList")
        self.alerts.setWordWrap(True)
        self.alerts.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        alerts_panel.body.addWidget(self.alerts, 1)
        body.addWidget(alerts_panel, 1)
        self.content.addLayout(body, 1)
        self.ctx.bus.data_changed.connect(lambda: self.isVisible() and self.reload())
        self.ctx.bus.alert.connect(lambda *_: self.isVisible() and self.reload())

    def on_show(self) -> None:
        self.reload()

    def badge(self) -> str | None:
        n = len(self.ctx.storage.wanted.all(active_only=True))
        return str(n) if n else None

    def reload(self) -> None:
        text = self.search.text().strip().upper()
        stats = self.ctx.storage.sightings.plate_stats()
        self.items = [w for w in self.ctx.storage.wanted.all()
                      if not text or text in w.plate or text in w.reason.upper()]
        self.table.setRowCount(len(self.items))
        for r, w in enumerate(self.items):
            seen, last = stats.get(w.plate, (0, None))
            cells = (w.plate, w.priority.upper(), w.reason, "ACTIVE" if w.active else "PAUSED",
                     str(seen), (last or "—")[:19], (w.added_at or "")[:16])
            for c, value in enumerate(cells):
                item = QTableWidgetItem(value)
                if c == 0:
                    item.setFont(theme.mono(11, bold=True))
                if c == 1:
                    item.setForeground(QColor(PRIORITY_COLORS[w.priority]))
                if c == 3:
                    item.setForeground(QColor(theme.OK if w.active else theme.MUTED))
                if c == 4 and seen:
                    item.setForeground(QColor(theme.DANGER))
                self.table.setItem(r, c, item)
        active = sum(1 for w in self.items if w.active)
        self.counter.setText(f"> {len(self.items)} PLATES  ·  {active} ACTIVE")
        self._selection_changed()

        self.alerts.clear()
        for e in self.service.recent_alerts():
            item = QListWidgetItem(f"{e.time[:19]}\n{e.message}")
            item.setForeground(QColor(theme.DANGER))
            self.alerts.addItem(item)
        if not self.alerts.count():
            self.alerts.addItem(QListWidgetItem("no alerts yet"))

    def _selected(self) -> WantedPlate | None:
        rows = self.table.selectionModel().selectedRows() if self.table.selectionModel() else []
        return self.items[rows[0].row()] if rows else None

    def _selection_changed(self) -> None:
        has = self._selected() is not None
        for b in (self.edit_btn, self.toggle_btn, self.remove_btn):
            b.setEnabled(has)

    def _changed(self) -> None:
        self.reload()
        self.ctx.bus.data_changed.emit()

    def _add(self) -> None:
        dlg = WantedDialog(self)
        if dlg.exec() != QDialog.Accepted:
            return
        v = dlg.values()
        try:
            w = self.service.add(v["plate"], v["reason"], v["priority"], v["notes"])
        except ValueError as e:
            QMessageBox.warning(self, "Watchlist", str(e))
            return
        if not v["active"]:
            w.active = False
            self.ctx.storage.wanted.update(w)
        seen = self.ctx.storage.sightings.plate_stats().get(w.plate, (0, None))[0]
        if seen:
            QMessageBox.information(self, "Watchlist", f"{w.plate} was already seen {seen} time(s) before it was "
                                                       f"added. Past sightings don't raise alerts; see the Logs.")
        self._changed()

    def _edit(self) -> None:
        w = self._selected()
        if w is None:
            return
        dlg = WantedDialog(self, w)
        if dlg.exec() != QDialog.Accepted:
            return
        v = dlg.values()
        other = self.ctx.storage.wanted.by_plate(v["plate"])
        if other and other.id != w.id:
            QMessageBox.warning(self, "Watchlist", f"{v['plate']} is already on the watchlist.")
            return
        w.plate, w.reason, w.priority, w.notes, w.active = (v["plate"], v["reason"], v["priority"],
                                                             v["notes"], v["active"])
        self.ctx.storage.wanted.update(w)
        self.ctx.storage.events.log("watchlist", f"{w.plate} updated", plate=w.plate)
        self._changed()

    def _toggle(self) -> None:
        w = self._selected()
        if w is None:
            return
        w.active = not w.active
        self.ctx.storage.wanted.update(w)
        self.ctx.storage.events.log("watchlist", f"{w.plate} {'activated' if w.active else 'paused'}", plate=w.plate)
        self._changed()

    def _remove(self) -> None:
        w = self._selected()
        if w is None:
            return
        if QMessageBox.question(self, "Watchlist", f"Remove {w.plate} from the watchlist?") != QMessageBox.Yes:
            return
        self.ctx.storage.wanted.remove(w.id)
        self.ctx.storage.events.log("watchlist", f"{w.plate} removed from watchlist", plate=w.plate)
        self._changed()

    def _import(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Import watchlist", "", "CSV (*.csv);;All files (*)")
        if not path:
            return
        added, problems = self.service.import_csv(path)
        text = f"{added} plate(s) added."
        if problems:
            text += "\n\nSkipped:\n" + "\n".join(problems[:15]) + ("\n…" if len(problems) > 15 else "")
        QMessageBox.information(self, "Import", text)
        self._changed()
