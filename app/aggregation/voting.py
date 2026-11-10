from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from app.core.models import PlateRead, PlateStatus
from app.plates.reader import find_plate


@dataclass
class Vote:
    status: PlateStatus
    text: str | None
    reads: int = 0
    share: float = 0.0
    alternatives: tuple[str, ...] = ()


@dataclass
class _Read:
    text: str
    probs: tuple[float, ...]
    weight: float
    confidence: float
    turkish: bool


def _shape(s: str) -> str:
    return "".join("9" if c.isdigit() else "A" for c in s)


def _consensus(reads: list[_Read]) -> tuple[str, float, float]:
    text, weakest = [], 1.0
    for i in range(len(reads[0].text)):
        scores = defaultdict(float)
        for r in reads:
            scores[r.text[i]] += r.weight * r.probs[i]
        char, top = max(scores.items(), key=lambda kv: kv[1])
        total = sum(scores.values())
        text.append(char)
        weakest = min(weakest, top / total if total else 0.0)
    return "".join(text), weakest, sum(r.weight * r.confidence for r in reads)


def _best_group(reads: list[_Read], key) -> tuple[list[_Read], float]:
    groups = defaultdict(list)
    for r in reads:
        groups[key(r.text)].append(r)
    weight = lambda rs: sum(r.weight * r.confidence for r in rs)
    best = max(groups.values(), key=weight)
    total = weight(reads)
    return best, weight(best) / total if total else 0.0


class PlateVoter:
    def __init__(self, min_reads: int = 3, min_weight: float = 2.0, min_char_share: float = 0.55,
                 min_shape_share: float = 0.6, foreign_min_conf: float = 0.9,
                 ref_width: int = 200, min_foreign_len: int = 4):
        self.min_reads = min_reads
        self.min_weight = min_weight
        self.min_char_share = min_char_share
        self.min_shape_share = min_shape_share
        self.foreign_min_conf = foreign_min_conf
        self.ref_width = ref_width
        self.min_foreign_len = min_foreign_len
        self._reads: dict[int, list[_Read]] = defaultdict(list)
        self._confirmed: dict[int, Vote] = {}
        self._current: dict[int, Vote] = {}
        self._history: dict[int, list[str]] = defaultdict(list)

    def add(self, track_id: int, read: PlateRead, plate_width: int) -> None:
        turkish = read.text is not None
        text = read.text if turkish else "".join(c for c in read.raw.upper() if c.isalnum())
        if not turkish and len(text) < self.min_foreign_len:
            return
        probs = read.char_probs if read.char_probs and len(read.char_probs) == len(text) \
            else (read.confidence,) * len(text)
        weight = min(1.0, plate_width / self.ref_width)
        self._reads[track_id].append(_Read(text, probs, weight, read.confidence, turkish))
        self._update(track_id)

    def current(self, track_id: int) -> Vote | None:
        return self._conflict(track_id) or self._confirmed.get(track_id) or self._current.get(track_id)

    def final(self, track_id: int) -> Vote:
        conflict = self._conflict(track_id)
        if conflict:
            return conflict
        guess = self._current.get(track_id)
        if guess and guess.status == PlateStatus.CONFIRMED:
            return guess
        foreign = self._foreign(track_id)
        if foreign:
            return foreign
        return Vote(PlateStatus.REVIEW_UNSURE, guess.text if guess else None,
                    guess.reads if guess else 0, guess.share if guess else 0.0)

    def _update(self, track_id: int) -> None:
        reads = self._reads[track_id]
        turkish = [r for r in reads if r.turkish]
        source = turkish or reads
        group, shape_share = _best_group(source, _shape if turkish else len)
        text, share, weight = _consensus(group)
        confirmable = (turkish and len(group) >= self.min_reads and weight >= self.min_weight
                       and shape_share >= self.min_shape_share and share >= self.min_char_share
                       and find_plate(text) == text)
        status = PlateStatus.CONFIRMED if confirmable else PlateStatus.PENDING
        self._current[track_id] = Vote(status, text, len(group), share)
        if confirmable:
            self._confirmed[track_id] = self._current[track_id]
            if text not in self._history[track_id]:
                self._history[track_id].append(text)

    def _conflict(self, track_id: int) -> Vote | None:
        history = self._history.get(track_id, [])
        if len(history) < 2:
            return None
        last = self._confirmed[track_id]
        return Vote(PlateStatus.REVIEW_CONFLICT, last.text, last.reads, last.share, tuple(history))

    def _foreign(self, track_id: int) -> Vote | None:
        reads = self._reads.get(track_id, [])
        foreign = [r for r in reads if not r.turkish]
        if not foreign:
            return None
        weight = lambda rs: sum(r.weight * r.confidence for r in rs)
        if weight(foreign) <= weight([r for r in reads if r.turkish]):
            return None
        group, _ = _best_group(foreign, len)
        avg_conf = sum(r.confidence for r in group) / len(group)
        if len(group) < self.min_reads or avg_conf < self.foreign_min_conf:
            return None
        text, share, _ = _consensus(group)
        return Vote(PlateStatus.REVIEW_FOREIGN, text, len(group), share)
