import cv2

from app.plates.validator import TurkishPlateValidator

GREEN, YELLOW, ORANGE = (0, 255, 0), (0, 255, 255), (0, 165, 255)


def draw(frame, tracks):
    for t in tracks:
        b = t.bbox
        cv2.rectangle(frame, (b.x1, b.y1), (b.x2, b.y2), GREEN, 2)
        cv2.putText(frame, f"{t.label} #{t.track_id}", (b.x1, max(20, b.y1 - 8)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, GREEN, 2)
        if t.plate:
            p = t.plate.bbox
            cv2.rectangle(frame, (p.x1, p.y1), (p.x2, p.y2), YELLOW, 2)
        if t.plate_text:
            color = GREEN if t.plate_confirmed else ORANGE
            text = f"{TurkishPlateValidator.pretty(t.plate_text)} ({t.plate_votes})"
            cv2.putText(frame, text, (b.x1, min(frame.shape[0] - 10, b.y2 + 28)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.9, color, 2)
    return frame
