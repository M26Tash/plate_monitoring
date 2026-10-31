import os

import cv2

from app.core.models import VehicleTrack


class Pipeline:
    def __init__(self, vehicle_detector, plate_detector=None,
                 reader=None, validator=None, voter=None,
                 min_ocr_width: int = 80, min_ocr_conf: float = 0.3, ocr_every: int = 3,
                 plate_padding: float = 0.10,
                 verbose: bool = False, debug_dir: str = "debug_crops", debug_limit: int = 200):
        self.vehicle_detector = vehicle_detector
        self.plate_detector = plate_detector
        self.reader, self.validator, self.voter = reader, validator, voter
        self.min_ocr_width = min_ocr_width
        self.min_ocr_conf = min_ocr_conf
        self.ocr_every = ocr_every
        self.plate_padding = plate_padding
        self.verbose = verbose
        self.debug_dir, self.debug_limit = debug_dir, debug_limit
        self._frame_no = 0
        self._announced: set[int] = set()
        self._warned_small: set[int] = set()
        self._saved = 0
        if verbose:
            os.makedirs(debug_dir, exist_ok=True)

    @property
    def _ocr_enabled(self) -> bool:
        return None not in (self.plate_detector, self.reader, self.validator, self.voter)

    def process(self, frame) -> list[VehicleTrack]:
        self._frame_no += 1
        tracks = self.vehicle_detector.track(frame)
        if self.plate_detector is None:
            return tracks

        for t in tracks:
            t.plate = self.plate_detector.detect_in(frame, t.bbox)
            if self._ocr_enabled:
                self._read_plate(frame, t)
        return tracks

    def _read_plate(self, frame, t: VehicleTrack) -> None:
        plate = t.plate
        if (self.verbose and plate is not None and plate.bbox.width < self.min_ocr_width
                and t.track_id not in self._warned_small):
            self._warned_small.add(t.track_id)
            print(f"#{t.track_id}: plate frame founded but too small "
                  f"({plate.bbox.width}px < {self.min_ocr_width}px) - OCR skipped")

        can_read = (plate is not None
                    and not self.voter.confirmed(t.track_id)
                    and plate.bbox.width >= self.min_ocr_width
                    and self._frame_no % self.ocr_every == 0)
        if can_read:
            h, w = frame.shape[:2]
            box = plate.bbox.padded(self.plate_padding).clamp(w, h)
            crop = frame[box.y1:box.y2, box.x1:box.x2]
            raw, conf = self.reader.read(crop)
            text = self.validator.fix(raw)
            if self.verbose:
                print(f"#{t.track_id} frame {self._frame_no}: width={plate.bbox.width}px "
                      f"OCR={raw!r} conf={conf:.2f} -> {text}")
                if self._saved < self.debug_limit:
                    cv2.imwrite(os.path.join(self.debug_dir,
                                             f"t{t.track_id}_f{self._frame_no}.jpg"), crop)
                    self._saved += 1
            if text and conf >= self.min_ocr_conf:
                self.voter.add(t.track_id, text, conf)
                if self.verbose:
                    self._log_voting(t.track_id)

        best = self.voter.best(t.track_id)
        if best:
            t.plate_text, t.plate_votes = best
            t.plate_confirmed = True
            if t.track_id not in self._announced:
                self._announced.add(t.track_id)
                print(f"CONFIRMED: car #{t.track_id} -> {t.plate_text} "
                      f"({t.plate_votes} readings)")

    def _log_voting(self, track_id: int) -> None:
        ranked = self.voter.ranking(track_id)[:5]
        variants = " | ".join(f"{plate}: {count} readings, avg={avg:.2f}, score={score:.2f}"
                              for plate, count, avg, score in ranked)
        print(f"[VOTING] #{track_id}: {variants}")
