import numpy as np
import pytest

from app.services.color import ColorClassifier, name_of


@pytest.mark.parametrize("hsv, expected", [
    ((0, 0, 240), "white"),
    ((0, 0, 160), "silver"),
    ((0, 0, 110), "gray"),
    ((0, 0, 30), "black"),
    ((0, 200, 200), "red"),
    ((110, 200, 200), "blue"),
    ((60, 200, 200), "green"),
    ((28, 200, 200), "yellow"),
])
def test_name_of(hsv, expected):
    assert name_of(np.array(hsv, dtype=np.float32)) == expected


@pytest.mark.parametrize("bgr, expected", [
    ((240, 240, 240), "white"),
    ((200, 40, 20), "blue"),
    ((20, 20, 200), "red"),
])
def test_classify_solid_vehicle(bgr, expected):
    img = np.full((120, 160, 3), bgr, dtype=np.uint8)
    assert ColorClassifier().classify(img) == expected


def test_classify_rejects_tiny_or_missing_crops():
    c = ColorClassifier()
    assert c.classify(None) is None
    assert c.classify(np.zeros((10, 10, 3), dtype=np.uint8)) is None
