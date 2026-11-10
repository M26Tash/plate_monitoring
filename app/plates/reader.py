from __future__ import annotations

import re

import cv2

from app.core.models import PlateRead

TR_PLATE = re.compile(r"(0[1-9]|[1-7]\d|8[01])[A-PR-VYZ]{1,3}\d{2,4}")
ALLOWED = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"


def find_plate(text: str) -> str | None:
    m = TR_PLATE.search(re.sub(r"[^A-Z0-9]", "", text.upper()))
    return m.group() if m else None

class FastPlateReader:
    def __init__(self, model: str = "cct-s-v2-global-model", recognizer=None):
        if recognizer is None:
            from fast_plate_ocr import LicensePlateRecognizer
            recognizer = LicensePlateRecognizer(model, device="cpu")
        self.name = model
        self.recognizer = recognizer
        self.gray = recognizer.config.num_channels == 1

    def read(self, plate_img) -> PlateRead:
        img = cv2.cvtColor(plate_img, cv2.COLOR_BGR2GRAY if self.gray else cv2.COLOR_BGR2RGB)
        pred = self.recognizer.run(img, return_confidence=True)[0]
        raw = pred.plate.replace(self.recognizer.config.pad_char, "")
        probs = tuple(float(p) for p in (pred.char_probs if pred.char_probs is not None else [])[:len(raw)])
        text = find_plate(raw)
        if text and text != raw:
            start = raw.index(text)
            probs = probs[start:start + len(text)]
        conf = sum(probs) / len(probs) if probs else 0.0
        return PlateRead(raw=raw, text=text, confidence=conf, char_probs=probs or None)

