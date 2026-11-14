from datetime import datetime, timezone

from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from app.gui import theme


class GridBackground(QWidget):

    def __init__(self, step: int = 32, parent=None):
        super().__init__(parent)
        self.step = step
        self.setAttribute(Qt.WA_StyledBackground, False)

    def paintEvent(self, event):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(theme.BG))
        p.setPen(QPen(QColor(theme.GRID), 1))
        for x in range(0, self.width(), self.step):
            p.drawLine(x, 0, x, self.height())
        for y in range(0, self.height(), self.step):
            p.drawLine(0, y, self.width(), y)


class Panel(QFrame):

    BRACKET = 10

    def __init__(self, title: str, meta: str = "", parent=None):
        super().__init__(parent)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(18, 14, 18, 16)
        outer.setSpacing(12)
        head = QHBoxLayout()
        head.addWidget(QLabel(f"[ {title.upper()} ]", objectName="PanelTitle"))
        head.addStretch(1)
        if meta:
            head.addWidget(QLabel(meta, objectName="PanelMeta"))
        outer.addLayout(head)
        self.body = QVBoxLayout()
        self.body.setSpacing(6)
        outer.addLayout(self.body, 1)

    def paintEvent(self, event):
        p = QPainter(self)
        r = self.rect().adjusted(0, 0, -1, -1)
        p.fillRect(r, QColor(theme.PANEL))
        p.setPen(QPen(QColor(theme.BORDER), 1))
        p.drawRect(r)
        p.setPen(QPen(QColor(theme.ACCENT), 2))
        b = self.BRACKET
        for x, y, dx, dy in ((r.left(), r.top(), 1, 1), (r.right(), r.top(), -1, 1),
                             (r.left(), r.bottom(), 1, -1), (r.right(), r.bottom(), -1, -1)):
            p.drawLine(x, y, x + dx * b, y)
            p.drawLine(x, y, x, y + dy * b)


class KeyValue(QWidget):

    def __init__(self, key: str, value: str, kind: str = "Value", width: int = 18, parent=None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)
        lay.addWidget(QLabel(f"> {key.upper()} ".ljust(width, "."), objectName="KeyLabel"))
        self.value = QLabel(value, objectName=kind)
        self.value.setWordWrap(True)
        lay.addWidget(self.value, 1)


class Chip(QLabel):

    def __init__(self, text: str, live: bool = False, parent=None):
        super().__init__(text, parent)
        self.setObjectName("ChipLive" if live else "Chip")


class UtcClock(QLabel):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Clock")
        self._tick()
        self._timer = QTimer(self, interval=1000, timeout=self._tick)
        self._timer.start()

    def _tick(self):
        now = datetime.now(timezone.utc)
        local = datetime.now().strftime("%H:%M:%S")
        self.setText(f"{now:%Y-%m-%d %H:%M:%S}Z  ·  LCL {local}")
