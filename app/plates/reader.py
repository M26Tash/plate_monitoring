import cv2
import numpy as np


class PlateReader:
    ALLOWED = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"

    def __init__(self, use_gpu: bool | None = None):
        import easyocr
        if use_gpu is None:
            import torch
            use_gpu = torch.cuda.is_available()
        self.reader = easyocr.Reader(["en"], gpu=use_gpu)

    @staticmethod
    def _strip_blue(img):
        w = img.shape[1]
        hsv = cv2.cvtColor(img[:, : int(w * 0.2)], cv2.COLOR_BGR2HSV)
        blue = cv2.inRange(hsv, (100, 80, 40), (130, 255, 255))
        cols = np.where(blue.mean(axis=0) / 255 > 0.5)[0]
        return img[:, cols.max() + 1:] if len(cols) else img

    def read(self, plate_img) -> tuple[str, float]:
        img = self._strip_blue(plate_img)
        scale = 160 / img.shape[0]
        img = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        results = self.reader.readtext(gray, allowlist=self.ALLOWED)
        results = [r for r in results if r[2] > 0.2]
        if not results:
            return "", 0.0
        results.sort(key=lambda r: r[0][0][0])
        text = "".join(r[1] for r in results)
        conf = sum(r[2] for r in results) / len(results)
        return text, conf
