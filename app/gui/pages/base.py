from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget

from app.gui.widgets import KeyValue, Panel


class Page(QWidget):
    code = "00"
    title = "Page"
    subtitle = ""

    def __init__(self):
        super().__init__()
        outer = QVBoxLayout(self)
        outer.setContentsMargins(32, 22, 32, 22)
        outer.setSpacing(4)
        outer.addWidget(QLabel(f"OCULUS / MOD-{self.code} / {self.title.upper()}", objectName="Crumb"))
        outer.addWidget(QLabel(self.title.upper(), objectName="PageTitle"))
        if self.subtitle:
            outer.addWidget(QLabel(self.subtitle, objectName="PageSubtitle"))
        outer.addSpacing(10)
        rule = QFrame(objectName="Rule")
        rule.setAttribute(Qt.WA_StyledBackground, True)
        outer.addWidget(rule)
        outer.addSpacing(14)
        self.content = QVBoxLayout()
        self.content.setSpacing(14)
        outer.addLayout(self.content, 1)
        self.build()

    def build(self) -> None:
        """Create the page's widgets in self.content"""

    def on_show(self) -> None:
        """Called every time the page becomes visible"""


class PlaceholderPage(Page):

    phase = ""
    plan = ""
    feeds = ""

    def build(self) -> None:
        panel = Panel("Module status", meta=f"MOD-{self.code}")
        panel.body.addWidget(KeyValue("Status", f"PENDING — scheduled for phase {self.phase}", "ValueWarn"))
        panel.body.addWidget(KeyValue("Scope", self.plan))
        if self.feeds:
            panel.body.addWidget(KeyValue("Data feed", self.feeds, "ValueData"))
        self.content.addWidget(panel, alignment=Qt.AlignTop)
        self.content.addStretch(1)
