from __future__ import annotations

from PySide6.QtCore import QTimer, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QApplication, QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from app.gui import theme
from app.gui.pages.monitor import bgr_to_pixmap

SHOW_MS = 12000


class AlertToast(QFrame):

    open_requested = Signal()

    def __init__(self, parent):
        super().__init__(parent)
        self.setFixedWidth(380)
        self.hide()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 12, 12, 14)
        lay.setSpacing(6)

        head = QHBoxLayout()
        self.title = QLabel("▲ WANTED VEHICLE", objectName="AlertTitle")
        head.addWidget(self.title)
        head.addStretch(1)
        close = QPushButton("✕", objectName="AlertClose")
        close.setFixedSize(26, 22)
        close.clicked.connect(self.hide)
        head.addWidget(close)
        lay.addLayout(head)

        row = QHBoxLayout()
        row.setSpacing(12)
        self.crop = QLabel()
        self.crop.setFixedSize(120, 40)
        self.crop.setAlignment(Qt.AlignCenter)
        self.crop.setStyleSheet(f"background: #000; border: 1px solid {theme.DANGER};")
        row.addWidget(self.crop)
        self.plate = QLabel(objectName="AlertPlate")
        row.addWidget(self.plate, 1)
        lay.addLayout(row)
        self.details = QLabel(objectName="AlertText")
        self.details.setWordWrap(True)
        lay.addWidget(self.details)
        open_btn = QPushButton("OPEN WATCHLIST ›", objectName="Danger")
        open_btn.clicked.connect(lambda: (self.hide(), self.open_requested.emit()))
        lay.addWidget(open_btn, alignment=Qt.AlignRight)

        self._timer = QTimer(self, singleShot=True, timeout=self.hide)

    def show_hit(self, hit, crop, source_name: str) -> None:
        w, s = hit.wanted, hit.sighting
        self.plate.setText(w.plate)
        pm = bgr_to_pixmap(crop, 120, 40)
        if pm:
            self.crop.setPixmap(pm)
        else:
            self.crop.clear()
        reason = w.reason or "no reason given"
        self.details.setText(f"{reason}\nPRIORITY {w.priority.upper()}  ·  {s.first_seen[:19]}\n"
                             f"SOURCE {source_name}  ·  {s.vehicle_type.upper()}  ·  track #{s.track_id}")
        self.adjustSize()
        self.reposition()
        self.show()
        self.raise_()
        self._timer.start(SHOW_MS)
        QApplication.beep()

    def reposition(self) -> None:
        parent = self.parentWidget()
        if parent is not None:
            self.move(parent.width() - self.width() - 20, 92)

    def paintEvent(self, event):
        p = QPainter(self)
        r = self.rect().adjusted(0, 0, -1, -1)
        p.fillRect(r, QColor("#1a0b0c"))
        p.setPen(QPen(QColor(theme.DANGER), 1))
        p.drawRect(r)
        p.fillRect(0, 0, 4, self.height(), QColor(theme.DANGER))
