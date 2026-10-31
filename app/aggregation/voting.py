from collections import defaultdict
from dataclasses import dataclass


@dataclass
class PlateStats:
    count: int = 0
    score: float = 0.0

    @property
    def average_confidence(self) -> float:
        return self.score / self.count if self.count else 0.0


class PlateVoter:
    def __init__(
        self,
        min_votes: int = 3,
        min_avg_conf: float = 0.0,
        min_score_margin: float = 0.0,
        min_agree: int = 2,
    ):
        self.min_votes = min_votes
        self.min_avg_conf = min_avg_conf
        self.min_score_margin = min_score_margin
        self.min_agree = min_agree

        self._stats: dict[int, dict[str, PlateStats]] = defaultdict(
            lambda: defaultdict(PlateStats)
        )

    def add(self, track_id: int, plate: str, conf: float) -> None:
        if not plate:
            return

        stats = self._stats[track_id][plate]
        stats.count += 1
        stats.score += max(0.0, min(1.0, conf))

    def ranking(self, track_id: int) -> list[tuple[str, int, float, float]]:
        candidates = self._stats.get(track_id, {})

        return sorted(
            [
                (plate, stats.count, stats.average_confidence, stats.score)
                for plate, stats in candidates.items()
            ],
            key=lambda item: (item[3], item[1], item[2]),
            reverse=True,
        )

    def consensus(self, track_id: int) -> tuple[str, int, float] | None:
        candidates = self._stats.get(track_id)
        if not candidates:
            return None

        weight_by_len: dict[int, float] = defaultdict(float)
        for plate, stats in candidates.items():
            weight_by_len[len(plate)] += stats.score
        length = max(weight_by_len, key=weight_by_len.get)
        same = {p: s for p, s in candidates.items() if len(p) == length}

        text = ""
        for i in range(length):
            weights: dict[str, float] = defaultdict(float)
            for plate, stats in same.items():
                weights[plate[i]] += stats.score
            text += max(weights, key=weights.get)

        readings = sum(s.count for s in same.values())
        avg_conf = sum(s.score for s in same.values()) / readings
        return text, readings, avg_conf

    def best(self, track_id: int) -> tuple[str, int] | None:
        found = self.consensus(track_id)
        if found is None:
            return None
        plate, readings, avg_conf = found

        if readings < self.min_votes:
            return None
        if avg_conf < self.min_avg_conf:
            return None

        stats = self._stats.get(track_id, {})
        exact = stats[plate].count if plate in stats else 0
        if exact < self.min_agree:
            return None

        if self.min_score_margin > 0 and plate in stats:
            rivals = [s.score for p, s in stats.items() if p != plate]
            if rivals and stats[plate].score - max(rivals) < self.min_score_margin:
                return None

        return plate, readings

    def confirmed(self, track_id: int) -> bool:
        return self.best(track_id) is not None
