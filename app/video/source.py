from __future__ import annotations
from pathlib import Path
import cv2


class VideoSource:
    def __init__(self, source: str | int):
        src = str(source)
        if src.isdigit():
            self.source: str | int = int(src)
        else:
            is_url = src.startswith(("http://", "https://", "rtsp://"))
            if not is_url and not Path(src).exists():
                raise FileNotFoundError(f"Couldn't find video: {src}")
            self.source = src

        self.cap = cv2.VideoCapture(self.source)
        if not self.cap.isOpened():
            raise RuntimeError(f"Couldn't find the source: {src}")
        self.fps = self.cap.get(cv2.CAP_PROP_FPS) or 30.0

    def frames(self):
        index = 0
        while True:
            ok, frame = self.cap.read()
            if not ok:
                break
            yield index, index / self.fps, frame
            index += 1

    def release(self):
        self.cap.release()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.release()
