import argparse
from pathlib import Path

import cv2

from app.core import config
from app.pipeline import Pipeline
from app.video.source import VideoSource
from app.vehicles.detector import VehicleDetector
from app.visualization import draw


def build_pipeline(plate_weights: Path) -> Pipeline:
    vehicle_detector = VehicleDetector()
    plate_detector = None
    return Pipeline(vehicle_detector, plate_detector)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--plate-weights", default=str(config.PLATE_WEIGHTS))
    args = parser.parse_args()

    pipeline = build_pipeline(Path(args.plate_weights))

    with VideoSource(args.source) as video:
        for _, _, frame in video.frames():
            tracks = pipeline.process(frame)
            draw(frame, tracks)

            h, w = frame.shape[:2]
            if w > config.DISPLAY_MAX_WIDTH:
                scale = config.DISPLAY_MAX_WIDTH / w
                frame = cv2.resize(frame, (int(w * scale), int(h * scale)))
            cv2.imshow("Plate system (q - exit)", frame)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
