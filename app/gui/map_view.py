from __future__ import annotations

import json

from PySide6.QtCore import QObject, QUrl, Signal, Slot
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineCore import QWebEngineSettings
from PySide6.QtWebEngineWidgets import QWebEngineView

from app.gui import theme

HTML = """<!DOCTYPE html><html><head><meta charset="utf-8">
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script src="qrc:///qtwebchannel/qwebchannel.js"></script>
<style>
html, body, #map { margin: 0; height: 100%; background: %BG%; }
.leaflet-tooltip, .leaflet-popup-content-wrapper, .leaflet-popup-tip {
  background: %PANEL%; color: %TEXT%; border: 1px solid %ACCENT%; border-radius: 0;
  font-family: 'Cascadia Mono', Consolas, monospace; font-size: 12px; box-shadow: none; }
.leaflet-tooltip:before { display: none; }
.leaflet-popup-content { margin: 10px 12px; }
.pop-plate { color: %ACCENT%; font-size: 16px; font-weight: bold; }
.pop-key { color: %MUTED%; }
.pop-img { display: block; max-width: 220px; margin: 6px 0; border: 1px solid %BORDER%; }
.pop-btn { color: %ACCENT%; background: none; border: 1px solid %ACCENT%; padding: 3px 10px;
  font-family: inherit; cursor: pointer; margin-top: 6px; }
.pop-btn:hover { background: %ACCENT%; color: %BG%; }
.leaflet-control-attribution { background: rgba(11,15,20,.8) !important; color: %MUTED%; }
.leaflet-control-attribution a { color: %MUTED%; }
</style></head>
<body><div id="map"></div><script>
var map = L.map('map', {zoomControl: true}).setView([20, 0], 2);
L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
            {maxZoom: 21, maxNativeZoom: 19,
             attribution: 'Tiles &copy; Esri, Maxar, Earthstar Geographics | Leaflet'}).addTo(map);
var markers = L.layerGroup().addTo(map);
var paths = L.layerGroup().addTo(map);
var bridge = null;

function setView(lat, lon, zoom) { map.setView([lat, lon], zoom); }
function clearMarkers() { markers.clearLayers(); }
function clearPaths() { paths.clearLayers(); }

function addMarker(lat, lon, label, color) {
  L.circleMarker([lat, lon], {radius: 7, color: color, weight: 2, fillOpacity: 0.6})
   .bindTooltip(label, {permanent: true, direction: 'right'}).addTo(markers);
}

function addCamera(lat, lon, label, color) {
  L.circleMarker([lat, lon], {radius: 10, color: color, weight: 3, fillOpacity: 0.15, dashArray: '3 3'})
   .bindTooltip(label, {permanent: true, direction: 'top'}).addTo(markers);
}

function addPaths(items) {
  items.forEach(function (p) {
    var weight = p.wanted ? 5 : 3;
    var line = L.polyline(p.points, {color: p.color, weight: weight, opacity: 0.9}).addTo(paths);
    L.circleMarker(p.points[0], {radius: 3, color: p.color, weight: 1, fillOpacity: 1}).addTo(paths);
    var end = L.circleMarker(p.points[p.points.length - 1],
                             {radius: 5, color: p.color, weight: 2, fillColor: '#0b0f14', fillOpacity: 1}).addTo(paths);
    var html = p.popup + '<br><button class="pop-btn" onclick="bridge.opened(' + p.id + ')">OPEN RECORD</button>';
    line.bindPopup(html, {maxWidth: 260});
    end.bindPopup(html, {maxWidth: 260});
    line.on('mouseover', function () { line.setStyle({weight: weight + 3}); });
    line.on('mouseout', function () { line.setStyle({weight: weight}); });
  });
}

function fitAll(pad) {
  var group = L.featureGroup(paths.getLayers().concat(markers.getLayers()));
  if (group.getLayers().length) map.fitBounds(group.getBounds(), {padding: [pad, pad], maxZoom: 18});
}

new QWebChannel(qt.webChannelTransport, function (ch) {
  bridge = ch.objects.bridge;
  map.on('click', function (e) { bridge.clicked(e.latlng.lat, e.latlng.lng); });
  bridge.ready();
});
</script></body></html>"""

for _name in ("BG", "PANEL", "TEXT", "ACCENT", "MUTED", "BORDER"):
    HTML = HTML.replace(f"%{_name}%", getattr(theme, _name))


class _Bridge(QObject):
    map_clicked = Signal(float, float)
    loaded = Signal()
    open_requested = Signal(int)

    @Slot(float, float)
    def clicked(self, lat, lon):
        self.map_clicked.emit(lat, lon)

    @Slot()
    def ready(self):
        self.loaded.emit()

    @Slot(int)
    def opened(self, sighting_id):
        self.open_requested.emit(sighting_id)


class MapView(QWebEngineView):
    clicked = Signal(float, float)
    open_requested = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._ready = False
        self._pending: list[str] = []
        self.settings().setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls, True)
        self._bridge = _Bridge()
        self._bridge.map_clicked.connect(self.clicked)
        self._bridge.open_requested.connect(self.open_requested)
        self._bridge.loaded.connect(self._on_loaded)
        self._channel = QWebChannel()
        self._channel.registerObject("bridge", self._bridge)
        self.page().setWebChannel(self._channel)
        self.page().setBackgroundColor(theme.BG)
        self.setHtml(HTML, QUrl("qrc:///"))

    def _on_loaded(self) -> None:
        self._ready = True
        for js in self._pending:
            self.page().runJavaScript(js)
        self._pending.clear()

    def run(self, js: str) -> None:
        if self._ready:
            self.page().runJavaScript(js)
        else:
            self._pending.append(js)

    def set_view(self, lat: float, lon: float, zoom: int = 18) -> None:
        self.run(f"setView({lat}, {lon}, {zoom})")

    def clear_markers(self) -> None:
        self.run("clearMarkers()")

    def clear_paths(self) -> None:
        self.run("clearPaths()")

    def add_marker(self, lat: float, lon: float, label: str, color: str = theme.ACCENT) -> None:
        self.run(f"addMarker({lat}, {lon}, {json.dumps(label)}, {json.dumps(color)})")

    def add_camera(self, lat: float, lon: float, label: str, color: str = theme.DATA) -> None:
        self.run(f"addCamera({lat}, {lon}, {json.dumps(label)}, {json.dumps(color)})")

    def add_paths(self, items: list[dict]) -> None:
        if items:
            self.run(f"addPaths({json.dumps(items)})")

    def fit_all(self, padding: int = 40) -> None:
        self.run(f"fitAll({padding})")
