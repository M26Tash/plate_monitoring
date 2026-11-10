from app.gui.pages.base import Page, PlaceholderPage


class MonitorPage(PlaceholderPage):
    code, title = "01", "Monitor"
    subtitle = "Live processing of a camera view: detections, plates, decisions"
    phase = "G2"
    plan = "Video with vehicle and plate boxes, play / pause / stop, live feed of decided plates."
    feeds = "pipeline -> track finished events"


class ReviewPage(PlaceholderPage):
    code, title = "02", "Review"
    subtitle = "Analyst queue: readings the system could not settle"
    phase = "G3"
    plan = "Conflict, unsure and foreign readings with crops: accept a reading, correct it or reject it."
    feeds = "sightings where status = review_*"


class WantedPage(PlaceholderPage):
    code, title = "03", "Watchlist"
    subtitle = "Plates of interest that raise an alert on sighting"
    phase = "G4"
    plan = "Add, edit and import plates of interest. A hit raises an alert; a near match goes to review."
    feeds = "every decided plate"


class LogsPage(PlaceholderPage):
    code, title = "04", "Logs"
    subtitle = "Sighting and event record"
    phase = "G5"
    plan = "Search by plate, filter by view, status and time, export to CSV, open a sighting's details."
    feeds = "sightings, reviews, alerts"


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


def all_pages() -> list[Page]:
    return [MonitorPage(), ReviewPage(), WantedPage(), LogsPage(), VehiclesPage(), MapPage()]
