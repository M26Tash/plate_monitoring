from app.gui.pages.base import Page, PlaceholderPage
from app.gui.pages.monitor import MonitorPage
from app.gui.pages.review import ReviewPage
from app.gui.pages.logs import LogsPage
from app.gui.pages.watchlist import WatchlistPage


class VehiclesPage(PlaceholderPage):
    code, title = "05", "Registry"
    subtitle = "Vehicle profiles (mock owner data)"
    phase = "G6"
    plan = "Owner (mock), model, detected colour and type, and every sighting of the plate."
    feeds = "vehicle crops -> colour, YOLO -> type"


class MapPage(PlaceholderPage):
    code, title = "06", "Geo"
    subtitle = "Vehicle paths of calibrated sources projected on a map"
    phase = "G7"
    plan = "Calibrate each view once, then every vehicle path is drawn on the satellite map."
    feeds = "track paths -> homography -> lat/lon"


def all_pages(ctx) -> list[Page]:
    return [cls(ctx) for cls in (MonitorPage, ReviewPage, WatchlistPage, LogsPage, VehiclesPage, MapPage)]
