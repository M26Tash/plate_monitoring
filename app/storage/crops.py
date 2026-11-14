from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np


class CropStore:

    def __init__(self, root: Path | str):
        self.root = Path(root)

    def save(self, image, run_id: int, track_id: int, kind: str) -> str | None:
        if image is None or getattr(image, "size", 0) == 0:
            return None
        rel = Path(f"run{run_id:04d}") / f"t{track_id:05d}_{kind}.jpg"
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(path), image, [cv2.IMWRITE_JPEG_QUALITY, 92])
        return rel.as_posix()

    def load(self, rel: str | None) -> np.ndarray | None:
        if not rel:
            return None
        path = self.root / rel
        return cv2.imread(str(path)) if path.exists() else None

    def delete_run(self, run_id: int) -> None:
        folder = self.root / f"run{run_id:04d}"
        if folder.is_dir():
            for f in folder.iterdir():
                f.unlink()
            folder.rmdir()
