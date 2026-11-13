from __future__ import annotations

from dataclasses import dataclass

from app.core import config
from app.storage import CropStore, Storage


@dataclass
class AppContext:
    storage: Storage
    crops: CropStore
    operator: str = "ANALYST-01"

    @classmethod
    def open(cls, db_path=config.DB_PATH, crops_dir=config.CROPS_DIR) -> "AppContext":
        return cls(Storage.open(db_path), CropStore(crops_dir))

    def close(self) -> None:
        self.storage.close()
