import pytest

from app.plates.reader import find_plate
from app.services.review import is_turkish
from app.services.watchlist import edit_distance
from app.storage import normalize_plate


@pytest.mark.parametrize("raw, expected", [
    ("34 abc 123", "34ABC123"),
    ("06-a-1234", "06A1234"),
    ("", None),
    (None, None),
    (" - ", None),
])
def test_normalize_plate(raw, expected):
    assert normalize_plate(raw) == expected


@pytest.mark.parametrize("text, expected", [
    ("34ABC123", "34ABC123"),
    ("TR 06 A 1234", "06A1234"),
    ("81AB12", "81AB12"),
    ("00ABC123", None),
    ("82ABC123", None),
    ("ABCDEF", None),
])
def test_find_plate(text, expected):
    assert find_plate(text) == expected


@pytest.mark.parametrize("plate, expected", [
    ("34ABC123", True),
    ("34 abc 123", True),
    ("B AB 1234", False),
    ("34ABC123X", False),
    (None, False),
])
def test_is_turkish(plate, expected):
    assert is_turkish(plate) is expected


@pytest.mark.parametrize("a, b, d", [
    ("34ABC123", "34ABC123", 0),
    ("34ABC123", "34ABC124", 1),
    ("34ABC123", "34AB123", 1),
    ("34ABC123", "06XYZ999", 8),
    ("", "ABC", 3),
])
def test_edit_distance(a, b, d):
    assert edit_distance(a, b) == d
    assert edit_distance(b, a) == d
