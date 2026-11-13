from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QComboBox, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem,
                               QLayout, QPushButton, QScrollArea, QSizePolicy, QVBoxLayout,
                               QWidget)

from app.gui import theme
from app.gui.inspector import ImageInspector
from app.gui.pages.base import Page
from app.gui.pages.monitor import STATUS_TAGS, FeedRow, bgr_to_pixmap
from app.gui.widgets import KeyValue, Panel
from app.services.review import ReviewError, ReviewService, is_turkish
from app.storage import Sighting

CROP_HEIGHT = 170
FILTERS = [("ALL", None), ("CONFLICT", "review_conflict"), ("UNSURE", "review_unsure"),
           ("FOREIGN", "review_foreign")]
WHY = {
    "review_conflict": "two or more different plates were confirmed for this vehicle",
    "review_unsure": "the readings never agreed enough to confirm a plate",
    "review_foreign": "consistent readings, but not a Turkish plate format",
}


class CropBox(QLabel):

    def __init__(self, height: int, title: str = "Image"):
        super().__init__()
        self._image = None
        self.title = title
        self.setFixedHeight(height)
        self.setMinimumWidth(200)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet(f"background: #000; border: 1px solid {theme.BORDER}; color: {theme.MUTED};")

    def set_image(self, bgr, empty_text: str = "NO IMAGE") -> None:
        self._image = bgr
        if bgr is None:
            self.clear()
            self.setText(empty_text)
            self.setCursor(Qt.ArrowCursor)
            self.setToolTip("")
        else:
            self._render()
            self.setCursor(Qt.PointingHandCursor)
            self.setToolTip("Click to inspect with a magnifier")

    def mousePressEvent(self, event):
        if self._image is not None and event.button() == Qt.LeftButton:
            ImageInspector(self._image, self.title, self.window()).exec()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._image is not None:
            self._render()

    def _render(self) -> None:
        self.setPixmap(bgr_to_pixmap(self._image, self.width() - 2, self.height() - 2))


class ReviewPage(Page):
    code, title = "02", "Review"
    subtitle = "Analyst queue: readings the system could not settle"

    def build(self) -> None:
        self.service = ReviewService(self.ctx.storage, self.ctx.operator)
        self.current: Sighting | None = None
        self.queue_items: list[Sighting] = []

        top = QHBoxLayout()
        self.filter = QComboBox()
        for label, status in FILTERS:
            self.filter.addItem(label, status)
        self.filter.currentIndexChanged.connect(lambda *_: self.reload())
        top.addWidget(QLabel("FILTER", objectName="KeyLabel"))
        top.addWidget(self.filter)
        top.addStretch(1)
        self.counter = QLabel(objectName="Readout")
        top.addWidget(self.counter)
        self.content.addLayout(top)

        body = QHBoxLayout()
        body.setSpacing(14)
        queue_panel = Panel("Queue", meta="OLDEST FIRST")
        queue_panel.setMinimumWidth(360)
        self.queue = QListWidget(objectName="FeedList")
        self.queue.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.queue.setVerticalScrollMode(QListWidget.ScrollPerPixel)
        self.queue.currentRowChanged.connect(self._select)
        queue_panel.body.addWidget(self.queue, 1)
        body.addWidget(queue_panel, 1)
        body.addWidget(self._detail_panel(), 2)
        self.content.addLayout(body, 1)
        self.ctx.bus.data_changed.connect(self._external_change)

    def _detail_panel(self) -> Panel:
        panel = Panel("Case", meta="ANALYST DECISION")
        inner = QWidget()
        body = QVBoxLayout(inner)
        body.setContentsMargins(0, 0, 12, 0)
        body.setSizeConstraint(QLayout.SetMinimumSize)
        body.setSpacing(6)

        crops = QHBoxLayout()
        crops.setSpacing(12)
        self.plate_img = CropBox(CROP_HEIGHT, "Plate crop")
        self.vehicle_img = CropBox(CROP_HEIGHT, "Vehicle")
        for title, box in (("PLATE CROP  (click to inspect)", self.plate_img), ("VEHICLE  (click to inspect)", self.vehicle_img)):
            col = QVBoxLayout()
            col.setSpacing(4)
            col.addWidget(QLabel(title, objectName="KeyLabel"))
            col.addWidget(box)
            crops.addLayout(col, 1)
        body.addLayout(crops)
        body.addSpacing(18)

        # row 2: case details, full width
        self.f_status = KeyValue("Status", "—", "ValueWarn")
        self.f_why = KeyValue("Why", "—")
        self.f_read = KeyValue("System read", "—", "ValueData")
        self.f_seen = KeyValue("Seen", "—")
        self.f_track = KeyValue("Track", "—")
        for kv in (self.f_status, self.f_why, self.f_read, self.f_seen, self.f_track):
            body.addWidget(kv)

        body.addSpacing(6)
        body.addWidget(QLabel("CANDIDATE READINGS  (click to use)", objectName="KeyLabel"))
        self.candidates = QHBoxLayout()
        self.candidates.setSpacing(8)
        holder = QWidget()
        holder.setLayout(self.candidates)
        self.candidates.setContentsMargins(0, 0, 0, 0)
        body.addWidget(holder)

        body.addSpacing(6)
        edit_row = QHBoxLayout()
        self.plate_edit = QLineEdit(objectName="PlateEdit")
        self.plate_edit.setPlaceholderText("PLATE")
        self.plate_edit.setMaxLength(12)
        self.plate_edit.textChanged.connect(self._validate)
        self.plate_edit.returnPressed.connect(self._accept)
        edit_row.addWidget(self.plate_edit, 1)
        self.validity = QLabel(objectName="KeyLabel")
        self.validity.setMinimumWidth(190)
        edit_row.addWidget(self.validity)
        body.addLayout(edit_row)
        self.note = QLineEdit()
        self.note.setPlaceholderText("note (optional)")
        body.addWidget(self.note)
        self.error = QLabel(objectName="ValueWarn")
        body.addWidget(self.error)

        buttons = QHBoxLayout()
        self.accept_btn = QPushButton("✓ ACCEPT  [ENTER]", objectName="Primary")
        self.foreign_btn = QPushButton("◇ FOREIGN")
        self.reject_btn = QPushButton("✕ REJECT", objectName="Danger")
        self.skip_btn = QPushButton("SKIP ›")
        self.accept_btn.clicked.connect(self._accept)
        self.foreign_btn.clicked.connect(lambda: self._decide(foreign=True))
        self.reject_btn.clicked.connect(lambda: self._decide(reject=True))
        self.skip_btn.clicked.connect(self._skip)
        for b in (self.accept_btn, self.foreign_btn, self.reject_btn):
            buttons.addWidget(b)
        buttons.addStretch(1)
        buttons.addWidget(self.skip_btn)
        body.addLayout(buttons)
        body.addStretch(1)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setWidget(inner)
        panel.body.addWidget(scroll, 1)
        return panel

    def badge(self) -> str | None:
        n = self.ctx.storage.sightings.pending_reviews()
        return str(n) if n else None

    def on_show(self) -> None:
        self.reload()

    def _external_change(self) -> None:
        if self.isVisible():
            self.reload(keep=True)

    def reload(self, keep: bool = False) -> None:
        keep_id = self.current.id if keep and self.current else None
        status = self.filter.currentData()
        items = [s for s in self.ctx.storage.sightings.review_queue() if status is None or s.status == status]
        self.queue_items = items
        self.queue.blockSignals(True)
        self.queue.clear()
        for s in items:
            item = QListWidgetItem()
            row = FeedRow(s, self.ctx.crops.load(s.plate_crop))
            item.setSizeHint(row.sizeHint())
            self.queue.addItem(item)
            self.queue.setItemWidget(item, row)
        self.queue.blockSignals(False)
        total = self.ctx.storage.sightings.pending_reviews()
        self.counter.setText(f"{len(items)} SHOWN  ·  {total} PENDING")
        index = next((i for i, s in enumerate(items) if s.id == keep_id), 0)
        self.queue.setCurrentRow(index if items else -1)
        self._select(self.queue.currentRow())

    def _select(self, row: int) -> None:
        self.error.clear()
        self.current = self.queue_items[row] if 0 <= row < len(self.queue_items) else None
        s = self.current
        for w in (self.accept_btn, self.foreign_btn, self.reject_btn, self.skip_btn, self.plate_edit, self.note):
            w.setEnabled(s is not None)
        self._clear_candidates()
        if s is None:
            self.plate_img.set_image(None, "QUEUE CLEAR")
            self.vehicle_img.set_image(None, "")
            for kv in (self.f_status, self.f_why, self.f_read, self.f_seen, self.f_track):
                kv.value.setText("—")
            self.plate_edit.clear()
            self.note.clear()
            return
        self._show_crop(self.plate_img, s.plate_crop)
        self._show_crop(self.vehicle_img, s.vehicle_crop)
        src = self.ctx.storage.sources.get(s.source_id)
        self.f_status.value.setText(STATUS_TAGS.get(s.status, s.status.upper()))
        self.f_status.value.setStyleSheet(f"color: {theme.STATUS_COLORS.get(s.status, theme.TEXT)};")
        self.f_why.value.setText(WHY.get(s.status, ""))
        self.f_read.value.setText(f"{s.plate or 'unreadable'} · {s.reads} reads · share {s.share:.2f}")
        self.f_seen.value.setText(f"{s.first_seen[:19]} · {src.name if src else '?'}")
        self.f_track.value.setText(f"#{s.track_id}  ·  {s.vehicle_type.upper()}  ·  run #{s.run_id}")
        for plate in dict.fromkeys([*s.alternatives, *([s.plate] if s.plate else [])]):
            btn = QPushButton(plate)
            btn.clicked.connect(lambda _=False, p=plate: self.plate_edit.setText(p))
            self.candidates.addWidget(btn)
        self.candidates.addStretch(1)
        self.plate_edit.setText(s.plate or "")
        self.note.clear()
        self.plate_edit.setFocus()

    def _clear_candidates(self) -> None:
        while self.candidates.count():
            w = self.candidates.takeAt(0).widget()
            if w:
                w.deleteLater()

    def _show_crop(self, box: CropBox, rel: str | None) -> None:
        box.set_image(self.ctx.crops.load(rel))

    def _validate(self, text: str) -> None:
        if not text.strip():
            self.validity.setText("")
        elif is_turkish(text):
            self.validity.setText("✓ TURKISH FORMAT")
            self.validity.setStyleSheet(f"color: {theme.OK};")
        else:
            self.validity.setText("✗ NOT TURKISH FORMAT")
            self.validity.setStyleSheet(f"color: {theme.WARN};")

    def _accept(self) -> None:
        self._decide()

    def _decide(self, foreign: bool = False, reject: bool = False) -> None:
        if self.current is None:
            return
        try:
            self.service.decide(self.current, self.plate_edit.text(), foreign=foreign, reject=reject,
                                note=self.note.text().strip() or None)
        except ReviewError as e:
            self.error.setText(f"> {e}")
            return
        row = self.queue.currentRow()
        self.current = None
        self.reload()
        if self.queue.count():
            self.queue.setCurrentRow(min(row, self.queue.count() - 1))
        self.ctx.bus.data_changed.emit()

    def _skip(self) -> None:
        if self.queue.count() > 1:
            self.queue.setCurrentRow((self.queue.currentRow() + 1) % self.queue.count())
