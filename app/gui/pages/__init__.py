from app.gui.pages.base import Page, PlaceholderPage
from app.gui.pages.monitor import MonitorPage
from app.gui.pages.review import ReviewPage
from app.gui.pages.logs import LogsPage
from app.gui.pages.registry import RegistryPage
from app.gui.pages.watchlist import WatchlistPage
from app.gui.pages.geo import GeoPage


def all_pages(ctx) -> list[Page]:
    return [cls(ctx) for cls in (MonitorPage, ReviewPage, WatchlistPage, LogsPage, RegistryPage, GeoPage)]
