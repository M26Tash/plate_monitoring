from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QDialog, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QPushButton,
                               QScrollArea, QVBoxLayout, QWidget)

from app.gui import theme
from app.gui.context import AppContext
from app.gui.pages.monitor import STATUS_TAGS
from app.gui.pages.review import CropBox
from app.gui.widgets import KeyValue, Panel
from app.storage import Sighting

LEVEL_COLORS = {"info": theme.TEXT, "warning": theme.WARN, "alert": theme.DANGER}


class SightingDialog(QDialog):
    def __init__(self, ctx: AppContext, sighting: Sighting, parent=None):
        super().__init__(parent)
        s = sighting
        st = ctx.storage
        self.setWindowTitle(f"OCULUS — sighting #{s.id}")
        self.resize(980, 760)

        inner = QWidget()
        body = QVBoxLayout(inner)
        body.setContentsMargins(0, 0, 12, 0)
        body.setSpacing(14)

        head = QHBoxLayout()
        plate = QLabel(s.final_plate or s.plate or "UNREAD", objectName="AlertPlate")
        color = theme.STATUS_COLORS.get(s.status, theme.TEXT)
        plate.setStyleSheet(f"color: {color};")
        head.addWidget(plate)
        tag = QLabel(STATUS_TAGS.get(s.status, s.status.upper()), objectName="FeedTag")
        tag.setStyleSheet(f"color: {color}; border: 1px solid {color};")
        head.addWidget(tag, alignment=Qt.AlignVCenter)
        wanted = st.wanted.by_plate(s.final_plate) if s.final_plate else None
        if wanted:
            hit = QLabel(f"WANTED · {wanted.priority.upper()}", objectName="FeedTag")
            hit.setStyleSheet(f"color: white; background: {theme.DANGER};")
            head.addWidget(hit, alignment=Qt.AlignVCenter)
        head.addStretch(1)
        body.addLayout(head)

        crops = QHBoxLayout()
        crops.setSpacing(12)
        for title, rel in (("PLATE CROP  (click to inspect)", s.plate_crop), ("VEHICLE  (click to inspect)", s.vehicle_crop)):
            col = QVBoxLayout()
            col.addWidget(QLabel(title, objectName="KeyLabel"))
            box = CropBox(200, title.split("  ")[0].title())
            box.set_image(ctx.crops.load(rel))
            col.addWidget(box)
            crops.addLayout(col, 1)
        body.addLayout(crops)

        src = st.sources.get(s.source_id)
        facts = Panel("Record", meta=f"SIGHTING #{s.id}")
        review_state = {"pending": "PENDING", "done": "DONE", None: "NOT NEEDED"}[s.review]
        rows = [
            ("System read", s.plate or "unreadable", "ValueData"),
            ("Final plate", s.final_plate or "—", "Value"),
            ("Alternatives", ", ".join(s.alternatives) or "—", "Value"),
            ("Review", review_state, "ValueWarn" if s.review == "pending" else "Value"),
            ("Source", f"{src.name} [{src.kind}]" if src else "?", "Value"),
            ("Seen", f"{s.first_seen[:23]}  →  {s.last_seen[11:23]}", "Value"),
            ("Frames", f"{s.first_frame} – {s.last_frame}   ·   run #{s.run_id}   ·   track #{s.track_id}", "Value"),
            ("Vehicle", f"{s.vehicle_type.upper()}" + (f"   ·   colour {s.color}" if s.color else ""), "Value"),
            ("OCR", f"{s.reads} reads   ·   weakest share {s.share:.2f}", "Value"),
            ("Path", f"{len(st.sightings.path(s.id))} points", "Value"),
        ]
        if wanted:
            rows.append(("Watchlist", f"{wanted.reason or 'no reason'}   ·   priority {wanted.priority}", "ValueWarn"))
        for key, value, kind in rows:
            facts.body.addWidget(KeyValue(key, value, kind))
        body.addWidget(facts)

        lists = QHBoxLayout()
        lists.setSpacing(12)
        reviews = Panel("Review history")
        rlist = QListWidget(objectName="FeedList")
        for r in st.reviews.for_sighting(s.id):
            note = f"  ·  “{r.note}”" if r.note else ""
            rlist.addItem(f"{r.decided_at[:19]}  {r.decision.upper()}  {r.plate or '—'}  by {r.operator}{note}")
        if not rlist.count():
            rlist.addItem("no review")
        rlist.setMinimumHeight(140)
        reviews.body.addWidget(rlist)
        events = Panel("Events")
        elist = QListWidget(objectName="FeedList")
        elist.setWordWrap(True)
        for e in st.events.for_sighting(s.id):
            item = QListWidgetItem(f"{e.time[11:19]}  {e.kind.upper()}  {e.message}")
            item.setForeground(QColor(LEVEL_COLORS.get(e.level, theme.TEXT)))
            elist.addItem(item)
        if not elist.count():
            elist.addItem("no events")
        elist.setMinimumHeight(140)
        events.body.addWidget(elist)
        lists.addWidget(reviews, 1)
        lists.addWidget(events, 1)
        body.addLayout(lists)
        body.addStretch(1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setWidget(inner)
        close = QPushButton("CLOSE")
        close.clicked.connect(self.accept)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 16, 20, 16)
        lay.addWidget(scroll, 1)
        lay.addWidget(close, alignment=Qt.AlignRight)
