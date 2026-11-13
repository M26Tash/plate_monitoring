from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QMainWindow,
                               QStackedWidget, QVBoxLayout, QWidget)

from app.gui.context import AppContext
from app.gui.pages import all_pages
from app.gui.pages.base import Page
from app.gui.widgets import Chip, GridBackground, UtcClock

APP_NAME = "OCULUS"
SIDEBAR_WIDTH = 220


class MainWindow(QMainWindow):

    def __init__(self, ctx: AppContext):
        super().__init__()
        self.ctx = ctx
        self.setWindowTitle(f"{APP_NAME} — plate intelligence console")
        self.setMinimumSize(1240, 780)
        self.pages: list[Page] = all_pages(ctx)

        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._banner())
        root.addWidget(self._top_bar())
        body = QHBoxLayout()
        body.setSpacing(0)
        body.addWidget(self._sidebar())
        body.addWidget(self._stage(), 1)
        root.addLayout(body, 1)
        self.setCentralWidget(central)

        self._status = QLabel("READY")
        self.statusBar().addWidget(self._status)
        self._db_status = QLabel()
        self.statusBar().addPermanentWidget(self._db_status)
        self._pipeline_status = QLabel()
        self.statusBar().addPermanentWidget(self._pipeline_status)
        self.statusBar().addPermanentWidget(QLabel("v0.1  "))
        self._set_pipeline_state("idle")
        bus = ctx.bus
        bus.source_changed.connect(self.set_source)
        bus.pipeline_state.connect(self._set_pipeline_state)
        bus.data_changed.connect(self.refresh_db_status)
        self.sidebar.setCurrentRow(0)

    def _set_pipeline_state(self, state: str) -> None:
        self._pipeline_status.setText(f"PIPELINE: {state.upper()}   ")

    def closeEvent(self, event):
        for page in self.pages:
            page.shutdown()
        super().closeEvent(event)

    def _banner(self) -> QLabel:
        banner = QLabel("MOCK DATA  //  LOCAL PROCESSING ONLY", objectName="Banner")
        banner.setAlignment(Qt.AlignCenter)
        return banner

    def _top_bar(self) -> QWidget:
        bar = QWidget(objectName="TopBar")
        bar.setAttribute(Qt.WA_StyledBackground, True)
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(16, 10, 16, 10)
        lay.setSpacing(10)
        logo = QVBoxLayout()
        logo.setSpacing(0)
        logo.addWidget(QLabel(f"◢ {APP_NAME}", objectName="Logo"))
        logo.addWidget(QLabel("PLATE INTELLIGENCE CONSOLE", objectName="LogoSub"))
        lay.addLayout(logo)
        lay.addStretch(1)
        self.source_chip = Chip("SRC  NONE")
        for chip in (Chip("● SYS ONLINE", live=True), self.source_chip):
            lay.addWidget(chip)
        lay.addWidget(UtcClock())
        return bar

    def _sidebar(self) -> QWidget:
        self.sidebar = QListWidget(objectName="Sidebar")
        for i, page in enumerate(self.pages):
            item = QListWidgetItem(f"{page.code}  {page.title.upper()}")
            item.setToolTip(f"{page.subtitle}  (Ctrl+{i + 1})")
            self.sidebar.addItem(item)
            QShortcut(QKeySequence(f"Ctrl+{i + 1}"), self, lambda i=i: self.sidebar.setCurrentRow(i))
        self.sidebar.currentRowChanged.connect(self._show_page)

        panel = QWidget(objectName="SidebarPanel")
        panel.setAttribute(Qt.WA_StyledBackground, True)
        panel.setFixedWidth(SIDEBAR_WIDTH)
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(QLabel("MODULES", objectName="SectionLabel"))
        lay.addWidget(self.sidebar, 1)
        lay.addWidget(QLabel(f"OPERATOR  {self.ctx.operator}\nCLEARANCE  LOCAL", objectName="Operator"))
        return panel

    def _stage(self) -> QWidget:
        stage = GridBackground()
        lay = QVBoxLayout(stage)
        lay.setContentsMargins(0, 0, 0, 0)
        self.stack = QStackedWidget()
        for page in self.pages:
            self.stack.addWidget(page)
        lay.addWidget(self.stack)
        return stage

    def set_source(self, name: str | None) -> None:
        self.source_chip.setText(f"SRC  {name or 'NONE'}")

    def _show_page(self, index: int) -> None:
        if index < 0:
            return
        self.stack.setCurrentIndex(index)
        page = self.pages[index]
        self._status.setText(f"MODULE {page.code} {page.title.upper()} — ACTIVE")
        page.on_show()
        self.refresh_db_status()

    def refresh_db_status(self) -> None:
        s = self.ctx.storage
        self._db_status.setText(f"DB: {Path(s.db.path).name}  ·  {s.sightings.count()} SIGHTINGS  ·  "
                                f"{s.sightings.pending_reviews()} TO REVIEW   ")
        for i, page in enumerate(self.pages):
            badge = page.badge()
            self.sidebar.item(i).setText(f"{page.code}  {page.title.upper()}" + (f"   [{badge}]" if badge else ""))
