
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import (QCheckBox, QDialog, QDialogButtonBox, QLabel, QPushButton,
                               QVBoxLayout)

from app.gui.widgets import Panel

POLICY_VERSION = "1"
SETTINGS_KEY = "responsible_use/accepted_version"

SUMMARY = """OCULUS reads licence plates and records where and when vehicles were seen.

PERMITTED   viewing · evaluation of the author's work · private,
            non-commercial personal learning. NOTHING ELSE.

FORBIDDEN   redistribution · commercial use · real camera feeds or streams
            · use in other projects or publications

NEVER       stalking, following or tracking a person · harassment or harm ·
            profiling individuals · covert or mass surveillance ·
            discrimination · selling or publishing movement data

Readings can be wrong: never act against a person on an automatic reading.
Comply with KVKK, GDPR and local law.

Full terms: LICENSE and RESPONSIBLE_USE.md"""


def settings() -> QSettings:
    return QSettings("Oculus", "Oculus")


def is_accepted() -> bool:
    return settings().value(SETTINGS_KEY, "") == POLICY_VERSION


class ResponsibleUseDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("OCULUS — Responsible use")
        self.setModal(True)
        self.setMinimumWidth(640)

        panel = Panel("Responsible use", meta=f"POLICY v{POLICY_VERSION}")
        text = QLabel(SUMMARY, objectName="Value")
        text.setWordWrap(False)
        panel.body.addWidget(text)

        self.agree = QCheckBox("I have read the policy and accept the LICENSE terms")
        buttons = QDialogButtonBox()
        self.accept_btn = QPushButton("ACCEPT", objectName="Primary")
        self.accept_btn.setEnabled(False)
        buttons.addButton(self.accept_btn, QDialogButtonBox.AcceptRole)
        buttons.addButton(QPushButton("EXIT"), QDialogButtonBox.RejectRole)
        self.agree.toggled.connect(self.accept_btn.setEnabled)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 20, 20, 20)
        lay.setSpacing(14)
        lay.addWidget(panel)
        lay.addWidget(self.agree)
        lay.addWidget(buttons)

    def accept(self):
        settings().setValue(SETTINGS_KEY, POLICY_VERSION)
        super().accept()


def ensure_accepted(parent=None) -> bool:
    return is_accepted() or ResponsibleUseDialog(parent).exec() == QDialog.Accepted
