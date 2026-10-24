from ultralytics import YOLO

from app.core import config
from app.core.models import BBox, PlateDetection


class PlateDetector:
    def __init__(self, weights=config.PLATE_WEIGHTS, conf=0.5, imgsz=640,
                 min_ratio=2.0, max_ratio=6.5,
                 max_width_frac=0.6, min_center_y_frac=0.4):
        self.model = YOLO(str(weights))
        self.conf = conf
        self.imgsz = imgsz
        self.min_ratio = min_ratio
        self.max_ratio = max_ratio
        self.max_width_frac = max_width_frac
        self.min_center_y_frac = min_center_y_frac

    def _plausible(self, box: BBox, crop_w: int, crop_h: int) -> bool:
        if box.height <= 0 or box.width <= 0:
            return False
        ratio = box.width / box.height
        if not self.min_ratio <= ratio <= self.max_ratio:
            return False
        if box.width > self.max_width_frac * crop_w:
            return False
        center_y = (box.y1 + box.y2) / 2
        return center_y >= self.min_center_y_frac * crop_h

    def detect_in(self, frame, region: BBox) -> PlateDetection | None:
        h, w = frame.shape[:2]
        r = region.clamp(w, h)
        if r.width < 20 or r.height < 20:
            return None

        crop = frame[r.y1:r.y2, r.x1:r.x2]
        result = self.model.predict(crop, conf=self.conf, imgsz=self.imgsz, verbose=False)[0]
        boxes = result.boxes
        if boxes is None or len(boxes) == 0:
            return None

        candidates = []
        for i in range(len(boxes)):
            x1, y1, x2, y2 = boxes.xyxy[i].int().tolist()
            box = BBox(x1, y1, x2, y2)
            if self._plausible(box, r.width, r.height):
                candidates.append((float(boxes.conf[i]), box))
        if not candidates:
            return None

        conf, best = max(candidates, key=lambda c: c[0])
        return PlateDetection(best.shifted(r.x1, r.y1), conf)
