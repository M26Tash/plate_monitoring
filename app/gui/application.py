import sys

from PySide6.QtWidgets import QApplication

from app.gui import theme
from app.gui.main_window import MainWindow
from app.gui.responsible_use import ensure_accepted


def run(argv: list[str] | None = None) -> int:
    app = QApplication(argv if argv is not None else sys.argv)
    app.setApplicationName("OCULUS")
    theme.apply(app)
    if not ensure_accepted():
        return 1
    window = MainWindow()
    window.show()
    return app.exec()
