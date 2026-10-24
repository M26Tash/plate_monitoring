from app.core.models import VehicleTrack


class Pipeline:
    def __init__(self, vehicle_detector, plate_detector=None):
        self.vehicle_detector = vehicle_detector
        self.plate_detector = plate_detector

    def process(self, frame) -> list[VehicleTrack]:
        tracks = self.vehicle_detector.track(frame)
        if self.plate_detector is not None:
            for t in tracks:
                t.plate = self.plate_detector.detect_in(frame, t.bbox)
        return tracks
