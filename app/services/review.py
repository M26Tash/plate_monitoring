from __future__ import annotations

from app.plates.reader import find_plate
from app.storage import Review, Sighting, Storage, normalize_plate

DECISIONS = ("accepted", "corrected", "foreign", "rejected")


class ReviewError(ValueError):
    pass


def is_turkish(plate: str | None) -> bool:
    plate = normalize_plate(plate)
    return bool(plate) and find_plate(plate) == plate


class ReviewService:

    def __init__(self, storage: Storage, operator: str):
        self.storage = storage
        self.operator = operator

    def decide(self, sighting: Sighting, plate: str | None, foreign: bool = False, reject: bool = False,
               note: str | None = None) -> Review:
        plate = normalize_plate(plate)
        if reject:
            decision, plate = "rejected", None
        elif not plate:
            raise ReviewError("Type the plate, or reject the sighting.")
        elif foreign:
            decision = "foreign"
        elif not is_turkish(plate):
            raise ReviewError(f"{plate} is not a valid Turkish plate. Correct it or mark it foreign.")
        else:
            decision = "accepted" if plate == normalize_plate(sighting.plate) else "corrected"

        review = self.storage.reviews.decide(sighting.id, decision, plate, self.operator, note)
        was = sighting.plate or "unreadable"
        message = {"accepted": f"{plate} accepted",
                   "corrected": f"{was} corrected to {plate}",
                   "foreign": f"{plate} marked foreign",
                   "rejected": f"{was} rejected"}[decision]
        self.storage.events.log("review", f"{message} by {self.operator}", sighting_id=sighting.id,
                                plate=plate or sighting.plate)
        return review
