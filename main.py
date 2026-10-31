"""Запуск:
    python main.py --source assets/video.mp4
    python main.py --source assets/video.mp4 --verbose     (печатать, что читает OCR)
Выход: клавиша q.
"""
import argparse
from pathlib import Path

import cv2

from app.core import config
from app.pipeline import Pipeline
from app.video.source import VideoSource
from app.vehicles.detector import VehicleDetector
from app.visualization import draw


def build_pipeline(plate_weights: Path, verbose: bool = False) -> Pipeline:
    vehicle_detector = VehicleDetector()
    if not plate_weights.exists():
        print(f"[!] No licence plate weigths ({plate_weights}) — working only with cars.")
        return Pipeline(vehicle_detector)

    from app.plates.detector import PlateDetector
    from app.plates.reader import PlateReader
    from app.plates.validator import TurkishPlateValidator
    from app.aggregation.voting import PlateVoter

    return Pipeline(vehicle_detector, PlateDetector(plate_weights),
                    reader=PlateReader(), validator=TurkishPlateValidator(),
                    voter=PlateVoter(min_votes=3, min_agree=2), verbose=verbose)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--plate-weights", default=str(config.PLATE_WEIGHTS))
    parser.add_argument("--verbose", action="store_true", help="print OCR readings and voting")
    args = parser.parse_args()

    pipeline = build_pipeline(Path(args.plate_weights), args.verbose)

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
