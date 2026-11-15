from __future__ import annotations

import cv2
import numpy as np

COLORS = ("white", "silver", "gray", "black", "red", "orange", "yellow", "green", "blue", "brown", "purple")


def name_of(hsv: np.ndarray) -> str:
    h, s, v = float(hsv[0]), float(hsv[1]), float(hsv[2])
    if v < 70 or (v < 100 and s < 130):
        return "black"
    if s < 40:
        if v > 200:
            return "white"
        return "silver" if v > 120 else "gray"
    if s < 80 and v < 120:
        return "gray"
    if h < 8 or h >= 165:
        return "red" if v > 90 else "brown"
    if h < 20:
        return "orange" if v > 150 else "brown"
    if h < 34:
        return "yellow"
    if h < 85:
        return "green"
    if h < 130:
        return "blue"
    return "purple"


class ColorClassifier:
    def __init__(self, k: int = 3, max_pixels: int = 6000):
        self.k = k
        self.max_pixels = max_pixels

    def body_region(self, bgr: np.ndarray) -> np.ndarray:
        h, w = bgr.shape[:2]
        return bgr[int(h * 0.50):int(h * 0.90), int(w * 0.12):int(w * 0.88)]

    def classify(self, bgr: np.ndarray | None) -> str | None:
        if bgr is None or bgr.size == 0 or min(bgr.shape[:2]) < 20:
            return None
        hsv = cv2.cvtColor(self.body_region(bgr), cv2.COLOR_BGR2HSV).reshape(-1, 3).astype(np.float32)
        bright = hsv[hsv[:, 2] > 70]
        pixels = bright if len(bright) > 0.40 * len(hsv) else hsv     # mostly dark: it really is a dark car
        if len(pixels) > self.max_pixels:
            idx = np.random.default_rng(0).choice(len(pixels), self.max_pixels, replace=False)
            pixels = pixels[idx]
        k = min(self.k, len(pixels))
        criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 20, 1.0)
        _, labels, centers = cv2.kmeans(pixels, k, None, criteria, 3, cv2.KMEANS_PP_CENTERS)
        counts = np.bincount(labels.ravel(), minlength=k)
        return name_of(centers[int(np.argmax(counts))])
