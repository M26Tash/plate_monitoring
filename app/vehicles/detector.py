from collections import Counter, defaultdict

from ultralytics import YOLO

from app.core import config
from app.core.models import BBox, VehicleTrack


class VehicleDetector:
    CLASSES = {2: "car", 3: "motorcycle", 5: "bus", 7: "truck"}

    def __init__(self, weights=config.VEHICLE_WEIGHTS, conf=config.VEHICLE_CONF,
                 tracker=config.TRACKER):
        self.model = YOLO(str(weights))
        self.conf = conf
        self.tracker = tracker
        self._label_votes: dict[int, Counter] = defaultdict(Counter)

    def _stable_label(self, track_id: int, label: str, conf: float) -> str:
        votes = self._label_votes[track_id]
        votes[label] += conf
        return votes.most_common(1)[0][0]

    def track(self, frame) -> list[VehicleTrack]:
        result = self.model.track(frame, persist=True, classes=list(self.CLASSES),
                                  conf=self.conf, tracker=self.tracker,
                                  agnostic_nms=True, verbose=False)[0]
        boxes = result.boxes
        if boxes is None or boxes.id is None:
            return []
        tracks = []
        for xyxy, tid, cls, conf in zip(boxes.xyxy.int().tolist(),
                                        boxes.id.int().tolist(),
                                        boxes.cls.int().tolist(),
                                        boxes.conf.tolist()):
            label = self._stable_label(tid, self.CLASSES[cls], conf)
            tracks.append(VehicleTrack(tid, BBox(*xyxy), label, conf))
        return tracks
