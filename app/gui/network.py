from __future__ import annotations

from PySide6.QtCore import QObject, QTimer, QUrl, Signal
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest

CHECK_URLS = (
    "https://unpkg.com/leaflet@1.9.4/dist/leaflet.js",
    "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/0/0/0",
)
INTERVAL_MS = 20000
TIMEOUT_MS = 5000


class NetworkMonitor(QObject):
    changed = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.online: bool | None = None
        self._manager = QNetworkAccessManager(self)
        self._results: dict[str, bool] = {}
        self._timer = QTimer(self, interval=INTERVAL_MS, timeout=self.check)
        self._timer.start()
        QTimer.singleShot(0, self.check)

    def check(self) -> None:
        self._results.clear()
        for url in CHECK_URLS:
            request = QNetworkRequest(QUrl(url))
            request.setTransferTimeout(TIMEOUT_MS)
            reply = self._manager.head(request)
            reply.finished.connect(lambda r=reply, u=url: self._done(u, r))

    def _done(self, url: str, reply: QNetworkReply) -> None:
        status = reply.attribute(QNetworkRequest.HttpStatusCodeAttribute)
        self._results[url] = status is not None
        reply.deleteLater()
        if len(self._results) == len(CHECK_URLS):
            online = all(self._results.values())
            if online != self.online:
                self.online = online
                self.changed.emit(online)


_monitor: NetworkMonitor | None = None


def monitor() -> NetworkMonitor:
    global _monitor
    if _monitor is None:
        _monitor = NetworkMonitor()
    return _monitor
