"""Optional camera checks. No hardware, network, or load-cell dependencies."""

import json
import math
from pathlib import Path
import uuid


def square_crop(frame, box):
    """Keep the whole container when a classifier center-crops its input."""
    import cv2

    height, width = frame.shape[:2]
    x1, y1, x2, y2 = box
    x1, y1 = max(0, math.floor(x1)), max(0, math.floor(y1))
    x2, y2 = min(width, math.ceil(x2)), min(height, math.ceil(y2))
    crop = frame[y1:y2, x1:x2]
    if crop.size == 0:
        raise ValueError("Empty container crop")
    h, w = crop.shape[:2]
    side = max(h, w)
    top, left = (side - h) // 2, (side - w) // 2
    return cv2.copyMakeBorder(
        crop, top, side - h - top, left, side - w - left,
        cv2.BORDER_CONSTANT, value=(114, 114, 114),
    )


class VisualInspector:
    def __init__(self, config=None, base_dir=".", classifier=None):
        self.config = config or {}
        self.base_dir = Path(base_dir)
        self.mode = self.config.get("mode", "off")
        if self.mode not in {"off", "observe", "enforce"}:
            raise ValueError("Inspection mode must be off, observe, or enforce")
        self.classifier = classifier
        self.model_error = None
        for check in ("size", "cleanliness"):
            if not isinstance(self.config.get(check, {}).get("enabled", False), bool):
                raise ValueError(f"{check}.enabled must be a JSON boolean")
        if self.mode != "off" and self.config.get("cleanliness", {}).get("enabled"):
            try:
                if self.classifier is None:
                    path = self.base_dir / self.config["cleanliness"]["model_path"]
                    if not path.is_file():
                        raise ValueError("Cleanliness checkpoint is missing")
                    from ultralytics import YOLO

                    self.classifier = YOLO(str(path))
                if self.classifier.task != "classify" or set(self.classifier.names.values()) != {
                    "visually_acceptable", "visibly_dirty",
                }:
                    raise ValueError("Expected the two-class cleanliness classifier")
            except Exception as error:
                self.model_error = str(error)

    @classmethod
    def from_file(cls, path):
        if not path:
            return cls()
        path = Path(path).resolve()
        with path.open(encoding="utf-8") as source:
            return cls(json.load(source), path.parent)

    def _size(self, frame, detection):
        settings = self.config["size"]
        if list(settings["frame_size_px"]) != [frame.shape[1], frame.shape[0]]:
            raise ValueError("Camera resolution differs from size calibration")
        x1, y1, x2, y2 = detection["box"]
        rx1, ry1, rx2, ry2 = settings["inspection_region_px"]
        if not (0 <= rx1 < rx2 <= frame.shape[1] and 0 <= ry1 < ry2 <= frame.shape[0]):
            raise ValueError("Invalid inspection region")
        if not (rx1 <= x1 < x2 <= rx2 and ry1 <= y1 < y2 <= ry2):
            return {"status": "uncertain", "reason": "Place the whole item in the inspection area."}
        sx, sy = float(settings["mm_per_pixel_x"]), float(settings["mm_per_pixel_y"])
        if not all(math.isfinite(value) and value > 0 for value in (sx, sy)):
            raise ValueError("Positive calibrated millimetres per pixel are required")
        width, height = (x2 - x1) * sx, (y2 - y1) * sy
        # Dimensions are in the camera's horizontal/vertical axes, even for
        # sideways containers. The physical position must match calibration.
        groups = settings["profiles"].get(detection["item"], [])
        if not groups:
            raise ValueError("No size profiles for this container class")
        matches = []
        for group in groups:
            wmin, wmax = map(float, group["width_mm"])
            hmin, hmax = map(float, group["height_mm"])
            if not all(math.isfinite(v) for v in (wmin, wmax, hmin, hmax)) or not (
                0 < wmin < wmax and 0 < hmin < hmax
            ):
                raise ValueError("Invalid size profile limits")
            if wmin <= width <= wmax and hmin <= height <= hmax:
                matches.append(group["name"])
        return {
            "status": "pass" if len(matches) == 1 else "uncertain" if matches else "reject",
            "width_mm": round(width, 1), "height_mm": round(height, 1),
            "size_group": matches[0] if len(matches) == 1 else None,
            "reason": "Size matched." if len(matches) == 1 else "Container size is unsupported or uncertain.",
        }

    def _cleanliness(self, crop):
        if self.model_error or self.classifier is None:
            raise ValueError(self.model_error or "Cleanliness model is unavailable")
        threshold = float(self.config["cleanliness"]["min_confidence"])
        if not math.isfinite(threshold) or not 0.5 < threshold <= 1:
            raise ValueError("Cleanliness confidence must be greater than 0.5 and at most 1")
        result = self.classifier.predict(source=crop, verbose=False)[0]
        label = result.names[int(result.probs.top1)]
        confidence = float(result.probs.top1conf)
        if not math.isfinite(confidence):
            raise ValueError("Invalid cleanliness confidence")
        status = "uncertain" if confidence < threshold else (
            "pass" if label == "visually_acceptable" else "reject"
        )
        return {"status": status, "label": label, "confidence": confidence,
                "reason": "Visible contamination detected." if status == "reject"
                else "The camera could not confirm an acceptable appearance." if status == "uncertain"
                else "Passed visible-contamination check."}

    def inspect(self, frame, detections):
        report = {"mode": self.mode, "passed": False,
                  "size": {"status": "not_checked"},
                  "cleanliness": {"status": "not_checked"},
                  "weight": {"status": "not_installed"}}
        if self.mode == "off" and not self.config.get("capture_directory"):
            return report
        enabled = [name for name in ("size", "cleanliness")
                   if self.config.get(name, {}).get("enabled")]
        active = self.mode != "off" and bool(enabled)
        if len(detections) != 1:
            report["reason"] = "Insert one container at a time."
            return report
        detection = detections[0]
        try:
            crop = square_crop(frame, detection["box"])
            directory = self.config.get("capture_directory")
            if directory:
                # Never auto-label examples from the model's own predictions.
                import cv2

                try:
                    directory = self.base_dir / directory
                    directory.mkdir(parents=True, exist_ok=True)
                    name = uuid.uuid4().hex
                    if not cv2.imwrite(str(directory / f"{name}.jpg"), crop):
                        raise OSError("Could not save inspection crop")
                    with (directory / f"{name}.json").open("w", encoding="utf-8") as target:
                        json.dump({"detection": detection, "human_label": None}, target)
                except Exception as error:
                    report["capture_error"] = str(error)
            if active:
                x1, y1, x2, y2 = detection["box"]
                if not (0 < x1 < x2 < frame.shape[1] and 0 < y1 < y2 < frame.shape[0]):
                    raise ValueError("Container touches the image edge; reposition it")
                for name in enabled:
                    try:
                        report[name] = self._size(frame, detection) if name == "size" else self._cleanliness(crop)
                    except Exception as error:
                        report[name] = {"status": "unavailable", "detail": str(error)}
                report["passed"] = all(report[name]["status"] == "pass" for name in enabled)
                if not report["passed"]:
                    failed = next(name for name in enabled if report[name]["status"] != "pass")
                    report["reason"] = report[failed].get("reason", "Inspection unavailable. Please remove the item.")
            elif self.mode == "enforce":
                report["reason"] = "Inspection unavailable. Please remove the item."
        except Exception as error:
            report["reason"] = "Unable to inspect the whole container. Please reposition it."
            report["detail"] = str(error)
        return report

    def apply(self, result, frame, detections):
        """Enforce before the caller sorts or awards points; observe only logs."""
        report = self.inspect(frame, detections)
        result = dict(result, inspection=report)
        if self.mode == "enforce" and not report["passed"]:
            result.update(accepted=False, category="reject", points=0,
                          rejection_reason=report.get("reason", "Inspection did not pass."))
        return result
