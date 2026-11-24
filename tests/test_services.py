import pytest

from app.services.registry import RegistryService, province_of
from app.services.review import ReviewError, ReviewService
from app.services.watchlist import WatchlistService


def test_review_accept_and_correct(storage, make_sighting):
    service = ReviewService(storage, "tester")
    a = make_sighting(plate="34ABC123", status="review_unsure", review="pending")
    b = make_sighting(plate="34ABC128", status="review_unsure", review="pending")
    assert service.decide(a, "34ABC123").decision == "accepted"
    assert service.decide(b, "34 abc 123").decision == "corrected"
    assert storage.sightings.get(b.id).final_plate == "34ABC123"


def test_review_rejects_invalid_turkish_plate(storage, make_sighting):
    service = ReviewService(storage, "tester")
    s = make_sighting(plate="XX", status="review_unsure", review="pending")
    with pytest.raises(ReviewError):
        service.decide(s, "B AB 1234")
    with pytest.raises(ReviewError):
        service.decide(s, "")
    assert service.decide(s, "B AB 1234", foreign=True).decision == "foreign"


def test_watchlist_exact_match_raises_alert(storage, make_sighting):
    service = WatchlistService(storage)
    service.add("34ABC123", "stolen", "high")
    hit = service.check(make_sighting(plate="34ABC123", final_plate="34ABC123"))
    assert hit.kind == "exact"
    assert len(service.recent_alerts()) == 1


def test_watchlist_near_match_goes_to_review(storage, make_sighting):
    service = WatchlistService(storage)
    service.add("34ABC123")
    hit = service.check(make_sighting(plate="34ABC124", final_plate="34ABC124"))
    assert hit.kind == "near"
    assert hit.sighting.review == "pending"
    assert service.recent_alerts() == []


def test_watchlist_ignores_unrelated_plates(storage, make_sighting):
    service = WatchlistService(storage)
    service.add("34ABC123")
    assert service.check(make_sighting(plate="06XYZ99", final_plate="06XYZ99")) is None


def test_watchlist_add_validation(storage):
    service = WatchlistService(storage)
    service.add("34ABC123")
    with pytest.raises(ValueError):
        service.add("34 abc 123")
    with pytest.raises(ValueError):
        service.add("")
    with pytest.raises(ValueError):
        service.add("06XYZ99", priority="urgent")


@pytest.mark.parametrize("plate, province", [
    ("34ABC123", "İstanbul"),
    ("06A1234", "Ankara"),
    ("01AB12", "Adana"),
    ("81AB12", "Düzce"),
    ("BAB1234", None),
])
def test_province_of(plate, province):
    assert province_of(plate) == province


def test_mock_owner_is_deterministic_and_fictional(storage):
    service = RegistryService(storage)
    first = service.mock_owner("34ABC123")
    assert service.mock_owner("06XYZ99") != first
    assert service.mock_owner("34ABC123") == first
    assert first[1].startswith("0555 ")


def test_registry_creates_profile_once(storage, make_sighting):
    service = RegistryService(storage)
    make_sighting(plate="34ABC123", final_plate="34ABC123")
    v = service.ensure("34ABC123")
    assert v.owner_city == "İstanbul"
    assert service.ensure("34ABC123").owner_name == v.owner_name
    assert storage.vehicles.count() == 1
