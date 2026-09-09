"""Acceptance and routing regressions with simulated model predictions."""

import sys
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, Mock, call, patch

from machine.detection import MaterialDetection
from weight_sensor import WeightReadingError


class MaterialDetectionTests(unittest.TestCase):
    def verify_and_sort(self, label, confidence, grams=20.0, weight_error=None):
        machine = MaterialDetection()
        machine.weight_scale = SimpleNamespace(read_weight=Mock(
            return_value={"grams": grams, "spread_g": 0.2, "samples": 10},
            side_effect=weight_error,
        ))
        box = SimpleNamespace(
            cls=[0], conf=[confidence],
            xyxy=[Mock(tolist=Mock(return_value=[30, 30, 180, 380]))],
        )
        prediction = SimpleNamespace(boxes=[box], plot=Mock())
        machine.model = SimpleNamespace(
            names={0: label}, predict=Mock(return_value=[prediction]),
        )
        machine.visual_inspector = SimpleNamespace(
            apply=Mock(side_effect=lambda result, *_: result),
        )
        machine.send_to_esp32 = Mock(return_value=True)
        frame = MagicMock()
        frame.shape = (480, 640, 3)
        drawing = SimpleNamespace(
            imwrite=Mock(), rectangle=Mock(), putText=Mock(), FONT_HERSHEY_SIMPLEX=0,
        )
        with patch.dict(sys.modules, {"cv2": drawing}), \
             patch("machine.detection.sleep") as settle:
            sequence = Mock()
            sequence.attach_mock(settle, "settle")
            sequence.attach_mock(machine.weight_scale.read_weight, "read_weight")
            result = machine.verify_item(frame)
        if machine.weight_scale.read_weight.called:
            self.assertEqual(sequence.mock_calls, [call.settle(2.0), call.read_weight()])
        else:
            settle.assert_not_called()
        self.assertEqual(drawing.rectangle.call_count, 1)
        preview_label = drawing.putText.call_args.args[1]
        if result["item"] == "unknown":
            self.assertEqual(preview_label, "Uncertain material")
        else:
            self.assertEqual(preview_label, f"{label} {confidence:.2f}")
        machine.sort_item(result)
        return machine, result

    def test_reported_can_misclassifications_do_not_open_bottle_gate(self):
        # Replay the reported predictions, not inference on the screenshot.
        for confidence in (0.53, 0.66, 0.69):
            with self.subTest(confidence=confidence):
                machine, result = self.verify_and_sort("plastic_bottle", confidence)
                self.assertFalse(result["accepted"])
                self.assertEqual(result["points"], 0)
                self.assertEqual(result["item"], "unknown")
                self.assertIn("uncertain", result["rejection_reason"])
                machine.send_to_esp32.assert_called_once_with("REJECT")
                machine.visual_inspector.apply.assert_not_called()

    def test_high_confidence_bottle_still_uses_bottle_gate(self):
        machine, result = self.verify_and_sort("plastic_bottle", 0.95)
        self.assertTrue(result["accepted"])
        machine.send_to_esp32.assert_called_once_with("BOTTLE")

    def test_bottle_threshold_applies_to_all_bottle_aliases(self):
        for label in ("plastic_bottle", "pet_bottle"):
            for confidence, accepted in ((0.749, False), (0.75, True)):
                with self.subTest(label=label, confidence=confidence):
                    machine, result = self.verify_and_sort(label, confidence)
                    self.assertEqual(result["accepted"], accepted)
                    machine.send_to_esp32.assert_called_once_with(
                        "BOTTLE" if accepted else "REJECT",
                    )

    def test_can_threshold_and_routing_are_preserved(self):
        for label in ("aluminum_can", "aluminium_can"):
            for confidence, accepted in ((0.64, False), (0.65, True), (0.66, True)):
                with self.subTest(label=label, confidence=confidence):
                    machine, result = self.verify_and_sort(label, confidence)
                    self.assertEqual(result["accepted"], accepted)
                    machine.send_to_esp32.assert_called_once_with(
                        "CAN" if accepted else "REJECT",
                    )

    def test_weight_limits_and_aliases_before_sorting_and_points(self):
        for label, limit, command in (("plastic_bottle", 150, "BOTTLE"),
                                      ("pet_bottle", 150, "BOTTLE"),
                                      ("aluminum_can", 180, "CAN"),
                                      ("aluminium_can", 180, "CAN")):
            for grams in (limit - 0.1, limit, limit + 0.001, 500):
                with self.subTest(label=label, grams=grams):
                    machine, result = self.verify_and_sort(label, 0.95, grams)
                    allowed = grams <= limit
                    self.assertEqual(result["accepted"], allowed)
                    self.assertEqual(result["points"], int(allowed))
                    machine.send_to_esp32.assert_called_once_with(command if allowed else "REJECT")
                    self.assertEqual(result["inspection"]["weight"]["grams"], grams)
                    self.assertEqual(result["inspection"]["weight"]["limit_g"], limit)
                    if not allowed:
                        self.assertEqual(result["category"], "reject")
                        self.assertIn(f"{limit} g", result["rejection_reason"])

    def test_failed_and_invalid_readings_cannot_award_points(self):
        for label in ("plastic_bottle", "aluminum_can"):
            for error in (TimeoutError("unplugged"), RuntimeError("clock timing"),
                          WeightReadingError("unstable", "moving", {"spread_g": 8})):
                with self.subTest(label=label, error=error), \
                     self.assertLogs("ecorefill.machine", level="ERROR"):
                    machine, result = self.verify_and_sort(label, 0.95, weight_error=error)
                    self.assertFalse(result["accepted"])
                    self.assertEqual(result["points"], 0)
                    machine.send_to_esp32.assert_called_once_with("REJECT")
            for grams in (float("nan"), float("inf"), -1, 0):
                with self.subTest(label=label, grams=grams), \
                     self.assertLogs("ecorefill.machine", level="ERROR"):
                    machine, result = self.verify_and_sort(label, 0.95, grams)
                    self.assertFalse(result["accepted"])
                    machine.send_to_esp32.assert_called_once_with("REJECT")

    def test_missing_sensor_cannot_fall_back_to_material_acceptance(self):
        machine = MaterialDetection()
        with self.assertLogs("ecorefill.machine", level="ERROR"):
            result = machine.apply_weight_check({"accepted": True, "category": "bottle", "points": 1})
        self.assertFalse(result["accepted"])
        self.assertEqual(result["points"], 0)
        self.assertEqual(result["inspection"]["weight"]["status"], "unavailable")

    def test_weight_pass_cannot_override_visual_rejection(self):
        machine = MaterialDetection()
        machine.weight_scale = Mock()
        with patch("machine.detection.sleep") as settle:
            result = machine.apply_weight_check({"accepted": False, "category": "reject",
                                                "points": 0, "rejection_reason": "Visibly dirty"})
        settle.assert_not_called()
        self.assertFalse(result["accepted"])
        self.assertEqual(result["rejection_reason"], "Visibly dirty")
        machine.weight_scale.read_weight.assert_not_called()


if __name__ == "__main__":
    unittest.main()
