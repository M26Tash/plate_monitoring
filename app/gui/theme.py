from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

BG = "#07090b"
PANEL = "#0d1216"
PANEL_HI = "#121a20"
BORDER = "#1c272e"
GRID = "#0e1519"
TEXT = "#c6d2d8"
MUTED = "#5d6f79"
ACCENT = "#f5a524"
DATA = "#2dd4bf"
OK = "#3ddc84"
WARN = "#f5a524"
DANGER = "#ff4d4f"

MONO = ["Cascadia Mono", "Consolas", "Courier New"]

STYLE = f"""
* {{ font-family: "Cascadia Mono", "Consolas", monospace; }}
QMainWindow, QDialog {{ background: {BG}; }}
QCheckBox {{ color: {TEXT}; spacing: 8px; }}
QCheckBox::indicator {{ width: 14px; height: 14px; border: 1px solid {MUTED}; }}
QCheckBox::indicator:checked {{ background: {ACCENT}; border-color: {ACCENT}; }}
QPushButton:disabled, QPushButton#Primary:disabled {{ color: {MUTED}; border-color: {BORDER}; background: {PANEL}; }}
QWidget {{ background: transparent; color: {TEXT}; }}
QDialog {{ background: {BG}; }}
QToolTip {{ background: {PANEL}; color: {TEXT}; border: 1px solid {ACCENT}; padding: 4px; }}

#Banner {{ background: {ACCENT}; color: {BG}; font-size: 10px; font-weight: 700;
           letter-spacing: 2px; padding: 2px; }}
#TopBar {{ background: {PANEL}; border-bottom: 1px solid {BORDER}; }}
#Logo {{ color: {ACCENT}; font-size: 17px; font-weight: 700; letter-spacing: 3px; }}
#LogoSub {{ color: {MUTED}; font-size: 10px; letter-spacing: 1px; }}
#Chip {{ color: {MUTED}; border: 1px solid {BORDER}; padding: 3px 8px; font-size: 11px; }}
#ChipLive {{ color: {OK}; border: 1px solid {OK}; padding: 3px 8px; font-size: 11px; }}
#Clock {{ color: {DATA}; font-size: 13px; font-weight: 600; padding-left: 6px; }}

#SidebarPanel {{ background: {PANEL}; border-right: 1px solid {BORDER}; }}
#SectionLabel {{ color: {MUTED}; font-size: 10px; letter-spacing: 2px; padding: 16px 16px 6px 16px; }}
#Sidebar {{ border: none; outline: 0; padding: 0; font-size: 12px; }}
#Sidebar::item {{ padding: 10px 14px; color: {MUTED}; border-left: 2px solid transparent; }}
#Sidebar::item:hover {{ background: {PANEL_HI}; color: {TEXT}; }}
#Sidebar::item:selected {{ background: {PANEL_HI}; color: {ACCENT}; border-left: 2px solid {ACCENT}; }}
#Operator {{ color: {MUTED}; font-size: 10px; padding: 12px 16px; border-top: 1px solid {BORDER}; }}

#Crumb {{ color: {MUTED}; font-size: 11px; letter-spacing: 1px; }}
#PageTitle {{ color: {TEXT}; font-size: 24px; font-weight: 700; letter-spacing: 2px; }}
#PageSubtitle {{ color: {MUTED}; font-size: 12px; }}
#Rule {{ background: {BORDER}; max-height: 1px; min-height: 1px; }}

#PanelTitle {{ color: {ACCENT}; font-size: 11px; font-weight: 700; letter-spacing: 2px; }}
#PanelMeta {{ color: {MUTED}; font-size: 10px; }}
#KeyLabel {{ color: {MUTED}; font-size: 12px; }}
#Value {{ color: {TEXT}; font-size: 12px; }}
#ValueData {{ color: {DATA}; font-size: 12px; }}
#ValueWarn {{ color: {WARN}; font-size: 12px; }}

QStatusBar {{ background: {PANEL}; color: {MUTED}; border-top: 1px solid {BORDER}; font-size: 11px; }}
QStatusBar::item {{ border: none; }}

QPushButton {{ background: {PANEL}; border: 1px solid {BORDER}; padding: 6px 14px;
               letter-spacing: 1px; }}
QPushButton:hover {{ border-color: {ACCENT}; color: {ACCENT}; }}
QPushButton#Primary {{ border-color: {ACCENT}; color: {ACCENT}; }}
QPushButton#Primary:hover {{ background: {ACCENT}; color: {BG}; }}
QLineEdit, QComboBox, QSpinBox {{ background: {PANEL}; border: 1px solid {BORDER}; padding: 5px 8px;
                                  selection-background-color: {ACCENT}; selection-color: {BG}; }}
QLineEdit:focus, QComboBox:focus {{ border-color: {ACCENT}; }}
QTableView, QListView, QTreeView {{ background: {PANEL}; border: 1px solid {BORDER};
                                    gridline-color: {BORDER}; alternate-background-color: {PANEL_HI};
                                    selection-background-color: {PANEL_HI}; selection-color: {ACCENT}; }}
QHeaderView::section {{ background: {PANEL_HI}; color: {MUTED}; border: none;
                        border-bottom: 1px solid {BORDER}; padding: 6px; font-size: 11px; }}
QScrollBar:vertical {{ background: transparent; width: 8px; }}
QScrollBar::handle:vertical {{ background: {BORDER}; min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: {MUTED}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
QScrollBar:horizontal {{ background: transparent; height: 8px; }}
QScrollBar::handle:horizontal {{ background: {BORDER}; min-width: 30px; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}

QDateTimeEdit, QDoubleSpinBox {{ background: {PANEL}; border: 1px solid {BORDER}; padding: 5px 8px; }}
QComboBox QAbstractItemView {{ background: {PANEL}; border: 1px solid {ACCENT};
                               selection-background-color: {PANEL_HI}; selection-color: {ACCENT}; }}
QProgressBar {{ background: {PANEL}; border: 1px solid {BORDER}; height: 6px; max-height: 6px;
                text-align: center; color: transparent; }}
QProgressBar::chunk {{ background: {ACCENT}; }}

#Readout {{ color: {DATA}; font-size: 12px; }}
#FeedList {{ background: {PANEL}; border: none; }}
#FeedList::item {{ border-bottom: 1px solid {BORDER}; }}
#FeedList::item:selected {{ background: {PANEL_HI}; }}
#FeedPlate {{ font-size: 16px; font-weight: 700; letter-spacing: 2px; }}
#FeedMeta {{ color: {MUTED}; font-size: 10px; }}
#PlateEdit {{ font-size: 20px; font-weight: 700; letter-spacing: 3px; padding: 8px 10px; }}
#FeedTag {{ font-size: 9px; font-weight: 700; letter-spacing: 1px; padding: 1px 5px; }}
QPushButton#Danger {{ border-color: {DANGER}; color: {DANGER}; }}
QPushButton#Danger:hover {{ background: {DANGER}; color: {BG}; }}
"""

STATUS_COLORS = {
    "confirmed": OK,
    "review_conflict": WARN,
    "review_unsure": WARN,
    "review_foreign": DATA,
    "no_plate": MUTED,
}


def mono(size: int = 10, bold: bool = False) -> QFont:
    font = QFont()
    font.setFamilies(MONO)
    font.setPointSize(size)
    font.setBold(bold)
    return font


def apply(app: QApplication) -> None:
    app.setStyle("Fusion")
    app.setFont(mono(10))
    app.setStyleSheet(STYLE)
