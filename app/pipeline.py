from collections import defaultdict

from app.aggregation.voting import PlateVoter, Vote
from app.core.models import PlateRead, PlateStatus, TrackResult, VehicleTrack


class _TrackState:

    def __init__(self, track_id: int, frame_no: int):
        self.track_id = track_id
        self.label = ""
        self.first_frame = self.last_frame = frame_no
        self.plate_crop = None
        self.plate_width = 0
        self.vehicle_crop = None
        self.vehicle_area = 0
        self.path: list[tuple[int, int, int]] = []


class Pipeline:

    def __init__(self, vehicle_detector, plate_detector=None, reader=None,
                 read_every: int = 1, min_plate_width: int = 100, padding: float = 0.10,
                 voter: PlateVoter | None = None, lost_after: int = 45, verbose: bool = True):
        self.vehicle_detector = vehicle_detector
        self.plate_detector = plate_detector
        self.reader = reader
        self.read_every = read_every
        self.min_plate_width = min_plate_width
        self.padding = padding
        self.voter = voter or PlateVoter()
        self.lost_after = lost_after
        self.verbose = verbose
        self.frame_no = 0
        self._live: dict[int, _TrackState] = {}
        self._results: dict[int, TrackResult] = {}
        self._finished: list[TrackResult] = []
        self._plate_seen: set[int] = set()
        self._announced: dict[int, str] = {}
        self.reads: dict[int, list[tuple[int, int, PlateRead]]] = defaultdict(list)

    def process(self, frame) -> list[VehicleTrack]:
        self.frame_no += 1
        tracks = self.vehicle_detector.track(frame)
        for t in tracks:
            if t.track_id in self._results:
                continue
            self._observe(frame, t)
            if self.plate_detector is not None:
                t.plate = self.plate_detector.detect_in(frame, t.bbox)
                if t.plate:
                    self._plate_seen.add(t.track_id)
                    self._keep_plate_crop(frame, t)
                    if self.reader and self.frame_no % self.read_every == 0:
                        self._read(frame, t)
            vote = self.voter.current(t.track_id)
            if vote:
                t.plate_text, t.plate_status = vote.text, vote.status
        for tid in [tid for tid, s in self._live.items()
                    if self.frame_no - s.last_frame > self.lost_after]:
            self._finish(tid)
        return tracks

    def pop_finished(self) -> list[TrackResult]:
        done, self._finished = self._finished, []
        return done

    def flush(self) -> list[TrackResult]:
        for tid in list(self._live):
            self._finish(tid)
        return self.pop_finished()

    def final(self, track_id: int) -> Vote:
        if track_id not in self._plate_seen:
            return Vote(PlateStatus.NO_PLATE, None)
        return self.voter.final(track_id)

    def finals(self) -> dict[int, Vote]:
        ids = sorted(set(self._live) | set(self._results))
        return {tid: self.final(tid) for tid in ids}

    def _observe(self, frame, t: VehicleTrack) -> None:
        s = self._live.get(t.track_id)
        if s is None:
            s = self._live[t.track_id] = _TrackState(t.track_id, self.frame_no)
        s.last_frame, s.label = self.frame_no, t.label
        b = t.bbox
        s.path.append((self.frame_no, (b.x1 + b.x2) // 2, b.y2))
        area = b.width * b.height
        if area > s.vehicle_area:
            h, w = frame.shape[:2]
            c = b.clamp(w, h)
            s.vehicle_area, s.vehicle_crop = area, frame[c.y1:c.y2, c.x1:c.x2].copy()

    def _keep_plate_crop(self, frame, t: VehicleTrack) -> None:
        s = self._live[t.track_id]
        if t.plate.bbox.width > s.plate_width:
            h, w = frame.shape[:2]
            c = t.plate.bbox.padded(self.padding).clamp(w, h)
            s.plate_width, s.plate_crop = t.plate.bbox.width, frame[c.y1:c.y2, c.x1:c.x2].copy()

    def _finish(self, track_id: int) -> None:
        s = self._live.pop(track_id)
        vote = self.final(track_id)
        result = TrackResult(track_id, s.label, vote.status, vote.text, s.first_frame, s.last_frame,
                             vote.alternatives, vote.share, vote.reads,
                             s.plate_crop, s.vehicle_crop, s.path)
        self._results[track_id] = result
        self._finished.append(result)

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
