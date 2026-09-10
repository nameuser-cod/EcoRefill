"""Material acceptance, optional visual inspection, and required weight limits."""

import math
from time import monotonic, sleep

from weight_sensor import WeightReadingError

from .config import (
    ACCEPT_CONFIDENCE_LIMIT,
    BOTTLE_ACCEPT_CONFIDENCE_LIMIT,
    BOTTLE_ITEMS,
    CAN_ITEMS,
    DETECTION_CONFIDENCE_LIMIT,
    INFERENCE_IMAGE_SIZE,
    MIN_OBJECT_AREA_RATIO,
    POINTS,
    BOTTLE_MAX_WEIGHT_G,
    CAN_MAX_WEIGHT_G,
    WEIGHT_SETTLE_SECONDS,
)
from .diagnostics import log
from .scan_region import scan_region_bounds


class MaterialDetection:
    """Methods composed into MachineRuntime; shared resources live on that instance."""

    def normalize_class_name(self, class_name):
        return (
            str(class_name)
            .lower()
            .strip()
            .replace("-", "_")
            .replace(" ", "_")
        )

    def material_confidence_limit(self, item):
        return (
            max(ACCEPT_CONFIDENCE_LIMIT, BOTTLE_ACCEPT_CONFIDENCE_LIMIT)
            if item in BOTTLE_ITEMS
            else ACCEPT_CONFIDENCE_LIMIT
        )

    def save_detection_preview(self, frame, detection=None):
        """Show the selected prediction, withholding uncertain material labels."""
        import cv2

        preview = frame.copy()
        if detection is not None:
            item = detection["item"]
            confidence = detection["confidence"]
            if confidence < self.material_confidence_limit(item):
                label = "Uncertain material"
                color = (160, 160, 160)
            else:
                label = f"{item} {confidence:.2f}"
                color = (255, 100, 0)
            left, top, right, bottom = [int(value) for value in detection["box"]]
            cv2.rectangle(preview, (left, top), (right, bottom), color, 2)
            cv2.putText(preview, label, (left, max(14, top - 5)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1)
        cv2.imwrite("detection_result.jpg", preview)

    def verify_item(self, frame, settling_started=None):
        """
        Accept ONLY a plastic bottle or aluminum can.

        Safety rules:
        1. Generic labels such as "bottle" and "can" are rejected.
        2. The approved class must meet its material acceptance threshold.
        3. Tiny bounding boxes are ignored to reduce background false positives.
        4. If a non-approved object has the strongest valid prediction, reject it.

        NOTE:
        For this to work properly, the YOLO model itself should contain classes
        such as plastic_bottle/pet_bottle and aluminum_can/aluminium_can.
        If the model only contains generic "bottle" and "can" classes, retraining
        the model is required to distinguish material reliably.
        """
        if settling_started is None:
            settling_started = monotonic()
        left, top, right, bottom = scan_region_bounds(frame)
        scan_frame = frame[top:bottom, left:right].copy()
        inference_started = monotonic()
        results = self.model.predict(
            source=scan_frame,
            conf=DETECTION_CONFIDENCE_LIMIT,
            imgsz=INFERENCE_IMAGE_SIZE,
            verbose=False,
        )
        log(f"Scan timing: inference={monotonic() - inference_started:.3f}s")

        if not results:
            self.save_detection_preview(frame)
            return {
                "accepted": False,
                "category": "reject",
                "item": "unknown",
                "points": 0,
                "confidence": 0,
            }

        frame_height, frame_width = frame.shape[:2]
        # Preserve the existing minimum object size in full-camera pixels.
        frame_area = float(frame_width * frame_height)

        detections = []

        for result in results:
            if result.boxes is None:
                continue

            for box in result.boxes:
                class_id = int(box.cls[0])
                confidence = float(box.conf[0])
                item = self.normalize_class_name(self.model.names[class_id])

                x1, y1, x2, y2 = [float(value) for value in box.xyxy[0].tolist()]
                # Inspection calibration and saved crops use full-frame coordinates.
                x1, x2 = x1 + left, x2 + left
                y1, y2 = y1 + top, y2 + top
                box_width = max(0.0, x2 - x1)
                box_height = max(0.0, y2 - y1)
                box_area_ratio = (
                    (box_width * box_height) / frame_area
                    if frame_area > 0
                    else 0
                )

                log(
                    "YOLO detection:",
                    f"class={item}",
                    f"confidence={confidence:.3f}",
                    f"area={box_area_ratio:.3f}",
                )

                # Ignore tiny detections likely caused by background/noise.
                if box_area_ratio < MIN_OBJECT_AREA_RATIO:
                    continue

                detections.append({
                    "item": item,
                    "confidence": confidence,
                    "area_ratio": box_area_ratio,
                    "box": [x1, y1, x2, y2],
                })

        if not detections:
            self.save_detection_preview(frame)
            return {
                "accepted": False,
                "category": "reject",
                "item": "unknown",
                "points": 0,
                "confidence": 0,
            }

        # Strongest meaningful detection in the frame.
        strongest = max(
            detections,
            key=lambda detection: detection["confidence"],
        )

        best_item = strongest["item"]
        best_confidence = strongest["confidence"]
        self.save_detection_preview(frame, strongest)

        # Reject any class that is not explicitly material-specific.
        if best_item not in BOTTLE_ITEMS and best_item not in CAN_ITEMS:
            log(
                "REJECTED: strongest class is not an approved material:",
                best_item,
            )
            return {
                "accepted": False,
                "category": "reject",
                "item": best_item,
                "points": 0,
                "confidence": best_confidence,
            }

        # Approved class, but prediction is still too uncertain.
        acceptance_limit = self.material_confidence_limit(best_item)
        if best_confidence < acceptance_limit:
            log(
                "REJECTED: approved class confidence too low:",
                f"{best_item} {best_confidence:.3f}",
                f"required={acceptance_limit:.3f}",
            )
            return {
                "accepted": False,
                "category": "reject",
                "item": "unknown",
                "points": 0,
                "confidence": best_confidence,
                "rejection_reason": (
                    "Material prediction is uncertain. Reposition the item and try again."
                ),
            }

        if best_item in BOTTLE_ITEMS:
            log(
                "Material matched: plastic bottle",
                f"confidence={best_confidence:.3f}",
            )
            result = self.visual_inspector.apply({
                "accepted": True,
                "category": "bottle",
                "item": "plastic_bottle",
                "points": POINTS.get(best_item, 1),
                "confidence": best_confidence,
            }, frame, detections)
            return self.apply_weight_check(result, settling_started)

        log(
            "Material matched: aluminum can",
            f"confidence={best_confidence:.3f}",
        )
        result = self.visual_inspector.apply({
            "accepted": True,
            "category": "can",
            "item": "aluminum_can",
            "points": POINTS.get(best_item, 1),
            "confidence": best_confidence,
        }, frame, detections)
        return self.apply_weight_check(result, settling_started)

    def apply_weight_check(self, result, settling_started=None):
        """Mandatory in every visual-inspection mode, before sorting/rewards."""
        report = dict(result.get("inspection") or {})
        result = dict(result, inspection=report)
        if not result["accepted"]:
            report["weight"] = {"status": "not_checked"}
            return result
        limit = BOTTLE_MAX_WEIGHT_G if result["category"] == "bottle" else CAN_MAX_WEIGHT_G
        label = "Bottle" if result["category"] == "bottle" else "Aluminum can"
        try:
            scale = getattr(self, "weight_scale", None)
            if scale is None:
                raise WeightReadingError("unavailable", "Weight sensor is unavailable")
            # Detection runs during the settling interval. Still collect fresh
            # samples only after two seconds from the camera's still frame.
            remaining = WEIGHT_SETTLE_SECONDS if settling_started is None else max(
                0.0, WEIGHT_SETTLE_SECONDS - (monotonic() - settling_started)
            )
            log(f"Scan timing: remaining weight settle={remaining:.3f}s")
            if remaining:
                sleep(remaining)
            weight_started = monotonic()
            reading = scale.read_weight()
            log(f"Scan timing: weight sampling={monotonic() - weight_started:.3f}s")
            grams = reading["grams"]
            if not math.isfinite(grams) or grams <= 0:
                raise WeightReadingError("invalid", "Invalid item weight")
            # Compare full precision. Exactly the limit is allowed; never round
            # a slightly overweight reading down before making the decision.
            overweight = grams > limit
            report["weight"] = dict(reading, status="reject" if overweight else "pass",
                                    limit_g=limit)
            log("Weight inspection:", f"{label}: {grams:.3f} g, limit={limit:g} g")
            if not overweight:
                return result
            reason = f"{label} exceeds the {limit:g} g weight limit. Please remove the item."
        except Exception as error:
            log("Weight check failed:", error)
            status = error.status if isinstance(error, WeightReadingError) else "unavailable"
            reading = error.reading if isinstance(error, WeightReadingError) else {}
            report["weight"] = dict(reading, status=status, limit_g=limit, detail=str(error))
            reason = ("Weight is unstable. Please reposition the item and try again."
                      if status == "unstable" else
                      "Unable to verify the item's weight. Please remove the item and try again.")
        result.update(accepted=False, category="reject", points=0, rejection_reason=reason)
        return result

    def sort_item(self, result):
        if not result["accepted"]:
            return self.send_to_esp32("REJECT")
        if result["category"] == "bottle":
            return self.send_to_esp32("BOTTLE")

        if result["category"] == "can":
            return self.send_to_esp32("CAN")

        return self.send_to_esp32("REJECT")
