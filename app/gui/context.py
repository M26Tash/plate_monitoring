from __future__ import annotations

from dataclasses import dataclass, field

from PySide6.QtCore import QObject, Signal

from app.core import config
from app.storage import CropStore, Storage


class EventBus(QObject):
    source_changed = Signal(str)
    pipeline_state = Signal(str)
    data_changed = Signal()


@dataclass
class AppContext:
    storage: Storage
    crops: CropStore
    operator: str = "ANALYST-01"
    bus: EventBus = field(default_factory=EventBus)

    @classmethod
    def open(cls, db_path=config.DB_PATH, crops_dir=config.CROPS_DIR) -> "AppContext":
        return cls(Storage.open(db_path), CropStore(crops_dir))

    def close(self) -> None:
        self.storage.close()
