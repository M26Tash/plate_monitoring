from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

VEHICLE_WEIGHTS = "yolov8s.pt"
PLATE_WEIGHTS = ROOT / "models" / "plate_1.pt"

VEHICLE_CONF = 0.2
PLATE_CONF = 0.3

TRACKER = "botsort.yaml"

DISPLAY_MAX_WIDTH = 1280
