"""Источник видео: файл, веб-камера (0, 1...) или URL потока."""
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
                raise FileNotFoundError(f"Видео не найдено: {src}")
            self.source = src

        self.cap = cv2.VideoCapture(self.source)
        if not self.cap.isOpened():
            raise RuntimeError(f"Не удалось открыть источник: {src}")
        self.fps = self.cap.get(cv2.CAP_PROP_FPS) or 30.0

    def frames(self):
        """Выдаёт (номер_кадра, время_в_секундах, кадр)."""
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
