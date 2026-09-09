"""Material acceptance rules and optional visual inspection."""

from .config import (
    ACCEPT_CONFIDENCE_LIMIT,
    BOTTLE_ACCEPT_CONFIDENCE_LIMIT,
    BOTTLE_ITEMS,
    CAN_ITEMS,
    DETECTION_CONFIDENCE_LIMIT,
    INFERENCE_IMAGE_SIZE,
    MIN_OBJECT_AREA_RATIO,
    POINTS,
)
from .diagnostics import log


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

    def verify_item(self, frame):
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
        import cv2

        results = self.model.predict(
            source=frame,
            conf=DETECTION_CONFIDENCE_LIMIT,
            imgsz=INFERENCE_IMAGE_SIZE,
            verbose=False,
        )

        if not results:
            return {
                "accepted": False,
                "category": "reject",
                "item": "unknown",
                "points": 0,
                "confidence": 0,
            }

        annotated_frame = results[0].plot()
        cv2.imwrite("detection_result.jpg", annotated_frame)

        frame_height, frame_width = frame.shape[:2]
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
        acceptance_limit = (
            max(ACCEPT_CONFIDENCE_LIMIT, BOTTLE_ACCEPT_CONFIDENCE_LIMIT)
            if best_item in BOTTLE_ITEMS
            else ACCEPT_CONFIDENCE_LIMIT
        )
        if best_confidence < acceptance_limit:
            log(
                "REJECTED: approved class confidence too low:",
                f"{best_item} {best_confidence:.3f}",
                f"required={acceptance_limit:.3f}",
            )
            return {
                "accepted": False,
                "category": "reject",
                "item": best_item,
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
            return self.visual_inspector.apply({
                "accepted": True,
                "category": "bottle",
                "item": "plastic_bottle",
                "points": POINTS.get(best_item, 1),
                "confidence": best_confidence,
            }, frame, detections)

        log(
            "Material matched: aluminum can",
            f"confidence={best_confidence:.3f}",
        )
        return self.visual_inspector.apply({
            "accepted": True,
            "category": "can",
            "item": "aluminum_can",
            "points": POINTS.get(best_item, 1),
            "confidence": best_confidence,
        }, frame, detections)

    def sort_item(self, result):
        if result["category"] == "bottle":
            return self.send_to_esp32("BOTTLE")

        if result["category"] == "can":
            return self.send_to_esp32("CAN")

        return self.send_to_esp32("REJECT")
