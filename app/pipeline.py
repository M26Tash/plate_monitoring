from collections import defaultdict

from app.aggregation.voting import PlateVoter, Vote
from app.core.models import PlateRead, PlateStatus, VehicleTrack


class Pipeline:
    def __init__(self, vehicle_detector, plate_detector=None, reader=None,
                 read_every: int = 1, min_plate_width: int = 100, padding: float = 0.10,
                 voter: PlateVoter | None = None, verbose: bool = True):
        self.vehicle_detector = vehicle_detector
        self.plate_detector = plate_detector
        self.reader = reader
        self.read_every = read_every
        self.min_plate_width = min_plate_width
        self.padding = padding
        self.voter = voter or PlateVoter()
        self.verbose = verbose
        self.frame_no = 0
        self._seen: set[int] = set()
        self._plate_seen: set[int] = set()
        self._announced: dict[int, str] = {}
        self.reads: dict[int, list[tuple[int, int, PlateRead]]] = defaultdict(list)

    def process(self, frame) -> list[VehicleTrack]:
        self.frame_no += 1
        tracks = self.vehicle_detector.track(frame)
        for t in tracks:
            self._seen.add(t.track_id)
            if self.plate_detector is None:
                continue
            t.plate = self.plate_detector.detect_in(frame, t.bbox)
            if t.plate:
                self._plate_seen.add(t.track_id)
                if self.reader and self.frame_no % self.read_every == 0:
                    self._read(frame, t)
            vote = self.voter.current(t.track_id)
            if vote:
                t.plate_text, t.plate_status = vote.text, vote.status
        return tracks

    def final(self, track_id: int) -> Vote:
        if track_id not in self._plate_seen:
            return Vote(PlateStatus.NO_PLATE, None)
        return self.voter.final(track_id)

    def finals(self) -> dict[int, Vote]:
        return {tid: self.final(tid) for tid in sorted(self._seen)}

    def _read(self, frame, t: VehicleTrack) -> None:
        if t.plate.bbox.width < self.min_plate_width:
            return
        h, w = frame.shape[:2]
        box = t.plate.bbox.padded(self.padding).clamp(w, h)
        found = self.reader.read(frame[box.y1:box.y2, box.x1:box.x2])
        self.reads[t.track_id].append((self.frame_no, t.plate.bbox.width, found))
        self.voter.add(t.track_id, found, t.plate.bbox.width)
        vote = self.voter.current(t.track_id)
        if (self.verbose and vote
                and vote.status in (PlateStatus.CONFIRMED, PlateStatus.REVIEW_CONFLICT)
                and self._announced.get(t.track_id) != vote.text):
            self._announced[t.track_id] = vote.text
            note = (f"CONFLICT -> manual review, confirmed so far: {', '.join(vote.alternatives)}"
                    if vote.alternatives else "confirmed")
            print(f"#{t.track_id}: {vote.text} {note} ({vote.reads} reads, share {vote.share:.2f})")
