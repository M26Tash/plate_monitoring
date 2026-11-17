from __future__ import annotations

import cv2
import numpy as np
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QCheckBox, QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from app.gui import theme

ZOOMS = (2, 3, 4, 6, 8)
LENS = 260


def to_qimage(bgr: np.ndarray) -> QImage:
    rgb = np.ascontiguousarray(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB))
    h, w = rgb.shape[:2]
    return QImage(rgb.data, w, h, 3 * w, QImage.Format_RGB888).copy()


def enhance(bgr: np.ndarray) -> np.ndarray:
    lab = cv2.cvtColor(bgr, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    l = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8)).apply(l)
    out = cv2.cvtColor(cv2.merge((l, a, b)), cv2.COLOR_LAB2BGR)
    blur = cv2.GaussianBlur(out, (0, 0), 1.2)
    return cv2.addWeighted(out, 1.6, blur, -0.6, 0)


class LensView(QWidget):
    def __init__(self, bgr: np.ndarray, parent=None):
        super().__init__(parent)
        self.plain = to_qimage(bgr)
        self.sharp = to_qimage(enhance(bgr))
        self.use_enhanced = False
        self.zoom_index = 1
        self.mouse: QPointF | None = None
        self.setMouseTracking(True)
        self.setCursor(Qt.CrossCursor)
        self.setMinimumSize(640, 420)
        self.on_zoom = None

    @property
    def zoom(self) -> int:
        return ZOOMS[self.zoom_index]

    def image_rect(self) -> QRectF:
        size = self.plain.size().scaled(self.size(), Qt.KeepAspectRatio)
        return QRectF((self.width() - size.width()) / 2, (self.height() - size.height()) / 2,
                      size.width(), size.height())

    def mouseMoveEvent(self, e):
        self.mouse = e.position()
        self.update()

    def leaveEvent(self, e):
        self.mouse = None
        self.update()

    def wheelEvent(self, e):
        step = 1 if e.angleDelta().y() > 0 else -1
        self.zoom_index = max(0, min(len(ZOOMS) - 1, self.zoom_index + step))
        if self.on_zoom:
            self.on_zoom(self.zoom)
        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor("#000"))
        target = self.image_rect()
        p.drawImage(target, self.plain)
        if self.mouse is None or not target.contains(self.mouse):
            return
        scale = self.plain.width() / target.width()
        sx = (self.mouse.x() - target.x()) * scale
        sy = (self.mouse.y() - target.y()) * scale
        src_px = LENS / self.zoom * scale
        source = QRectF(sx - src_px / 2, sy - src_px / 2, src_px, src_px)
        lens = QRectF(self.mouse.x() - LENS / 2, self.mouse.y() - LENS / 2, LENS, LENS)
        clip = QPainterPath()
        clip.addEllipse(lens)
        p.save()
        p.setClipPath(clip)
        p.fillRect(lens, QColor("#000"))
        p.drawImage(lens, self.sharp if self.use_enhanced else self.plain, source)
        p.restore()
        p.setPen(QPen(QColor(theme.ACCENT), 2))
        p.drawEllipse(lens)
        p.setPen(QPen(QColor(theme.ACCENT), 1))
        c = self.mouse
        p.drawLine(QPointF(c.x() - 8, c.y()), QPointF(c.x() + 8, c.y()))
        p.drawLine(QPointF(c.x(), c.y() - 8), QPointF(c.x(), c.y() + 8))
        p.setFont(theme.mono(9, bold=True))
        p.drawText(lens.adjusted(0, 0, 0, -10), Qt.AlignHCenter | Qt.AlignBottom, f"{self.zoom}×")


class ImageInspector(QDialog):
    def __init__(self, bgr: np.ndarray, title: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"OCULUS — {title}")
        self.view = LensView(bgr)
        h, w = bgr.shape[:2]
        info = QLabel(f"{title.upper()}   ·   {w}×{h} px   ·   hover = lens   ·   wheel = zoom   ·   esc = close",
                      objectName="KeyLabel")
        self.zoom_label = QLabel(objectName="Readout")
        self.view.on_zoom = lambda z: self.zoom_label.setText(f"ZOOM {z}×")
        self.zoom_label.setText(f"ZOOM {self.view.zoom}×")
        sharp = QCheckBox("ENHANCE (contrast + sharpen in lens)")
        sharp.toggled.connect(self._toggle_enhance)
        close = QPushButton("CLOSE")
        close.clicked.connect(self.accept)

        bar = QHBoxLayout()
        bar.addWidget(info, 1)
        bar.addWidget(self.zoom_label)
        bar.addSpacing(16)
        bar.addWidget(sharp)
        bar.addSpacing(16)
        bar.addWidget(close)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 14, 16, 16)
        lay.addLayout(bar)
        lay.addWidget(self.view, 1)

        screen = self.screen().availableGeometry() if self.screen() else None
        if screen:
            self.resize(int(screen.width() * 0.8), int(screen.height() * 0.8))

    def _toggle_enhance(self, on: bool) -> None:
        self.view.use_enhanced = on
        self.view.update()
