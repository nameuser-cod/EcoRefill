"""Acceptance and routing regressions with simulated model predictions."""

import sys
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, Mock, call, patch

from machine.detection import MaterialDetection
from machine.weight_sensor import WeightReadingError


class MaterialDetectionTests(unittest.TestCase):
    def setUp(self):
        enabled = patch("machine.detection.WEIGHT_SENSOR_ENABLED", True)
        enabled.start()
        self.addCleanup(enabled.stop)

    def test_disabled_weight_skips_sensor_and_settling_but_preserves_material_checks(self):
        with patch("machine.detection.WEIGHT_SENSOR_ENABLED", False):
            for label, confidence, accepted, command in (
                ("plastic_bottle", 0.95, True, "BOTTLE"),
                ("aluminum_can", 0.95, True, "CAN"),
                ("plastic_bottle", 0.66, False, "REJECT"),
            ):
                with self.subTest(label=label, confidence=confidence):
                    machine, result = self.verify_and_sort(
                        label, confidence, weight_error=RuntimeError("Disconnected sensor"))
                    self.assertEqual(result["accepted"], accepted)
                    self.assertEqual(result["points"], 0.5 if accepted else 0)
                    machine.weight_scale.read_weight.assert_not_called()
                    machine.send_command.assert_called_once_with(command)
                    if accepted:
                        self.assertEqual(result["inspection"]["weight"], {"status": "disabled"})

    def test_disabled_weight_does_not_override_visual_rejection_or_fake_a_measurement(self):
        machine = MaterialDetection()
        result = {"accepted": False, "category": "reject", "points": 0,
                  "rejection_reason": "Visual check failed", "inspection": {"cleanliness": "reject"}}
        with patch("machine.detection.WEIGHT_SENSOR_ENABLED", False), \
             patch("machine.detection.sleep") as settle:
            checked = machine.apply_weight_check(result)
        self.assertFalse(checked["accepted"])
        self.assertEqual(checked["rejection_reason"], "Visual check failed")
        self.assertEqual(checked["inspection"]["cleanliness"], "reject")
        self.assertEqual(checked["inspection"]["weight"], {"status": "disabled"})
        settle.assert_not_called()

    def verify_and_sort(self, label, confidence, grams=0.5, weight_error=None,
                        inference_seconds=0):
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
        clock = [100.0]

        def predict(**kwargs):
            clock[0] += inference_seconds
            return [prediction]

        machine.model = SimpleNamespace(
            names={0: label}, predict=Mock(side_effect=predict),
        )
        machine.visual_inspector = SimpleNamespace(
            apply=Mock(side_effect=lambda result, *_: result),
        )
        machine.send_command = Mock(return_value=True)
        frame = MagicMock()
        frame.shape = (480, 640, 3)
        drawing = SimpleNamespace(
            imwrite=Mock(), rectangle=Mock(), putText=Mock(), FONT_HERSHEY_SIMPLEX=0,
        )
        with patch.dict(sys.modules, {"cv2": drawing}), \
             patch("machine.detection.monotonic", side_effect=lambda: clock[0]), \
             patch("machine.detection.sleep") as settle:
            sequence = Mock()
            sequence.attach_mock(settle, "settle")
            sequence.attach_mock(machine.weight_scale.read_weight, "read_weight")
            result = machine.verify_item(frame)
        if machine.weight_scale.read_weight.called:
            remaining = max(0, 2.0 - inference_seconds)
            expected = ([call.settle(remaining)] if remaining else []) + [call.read_weight()]
            self.assertEqual(sequence.mock_calls, expected)
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

    def test_detection_overlaps_settling_without_shortening_weight_checks(self):
        for duration in (0.5, 1.5, 2.0, 3.0):
            with self.subTest(inference_seconds=duration):
                machine, result = self.verify_and_sort("plastic_bottle", 0.95,
                                                       inference_seconds=duration)
                self.assertTrue(result["accepted"])
                machine.weight_scale.read_weight.assert_called_once_with()

    def test_explicit_still_frame_time_includes_capture_work(self):
        machine = MaterialDetection()
        machine.weight_scale = SimpleNamespace(read_weight=Mock(return_value={"grams": 0.5}))
        with patch("machine.detection.monotonic", return_value=101.5), \
             patch("machine.detection.sleep") as settle:
            result = machine.apply_weight_check(
                {"accepted": True, "category": "bottle", "points": 1}, settling_started=100.0)
        settle.assert_called_once_with(0.5)
        self.assertTrue(result["accepted"])

    def test_reported_can_misclassifications_do_not_open_bottle_gate(self):
        # Replay the reported predictions, not inference on the screenshot.
        for confidence in (0.53, 0.66, 0.69):
            with self.subTest(confidence=confidence):
                machine, result = self.verify_and_sort("plastic_bottle", confidence)
                self.assertFalse(result["accepted"])
                self.assertEqual(result["points"], 0)
                self.assertEqual(result["item"], "unknown")
                self.assertIn("uncertain", result["rejection_reason"])
                machine.send_command.assert_called_once_with("REJECT")
                machine.visual_inspector.apply.assert_not_called()

    def test_high_confidence_bottle_still_uses_bottle_gate(self):
        machine, result = self.verify_and_sort("plastic_bottle", 0.95)
        self.assertTrue(result["accepted"])
        machine.send_command.assert_called_once_with("BOTTLE")

    def test_bottle_threshold_applies_to_all_bottle_aliases(self):
        for label in ("plastic_bottle", "pet_bottle"):
            for confidence, accepted in ((0.749, False), (0.75, True)):
                with self.subTest(label=label, confidence=confidence):
                    machine, result = self.verify_and_sort(label, confidence)
                    self.assertEqual(result["accepted"], accepted)
                    self.assertEqual(result["points"], 0.5 if accepted else 0)
                    machine.send_command.assert_called_once_with(
                        "BOTTLE" if accepted else "REJECT",
                    )

    def test_can_threshold_and_routing_are_preserved(self):
        for label in ("aluminum_can", "aluminium_can"):
            for confidence, accepted in ((0.64, False), (0.65, True), (0.66, True)):
                with self.subTest(label=label, confidence=confidence):
                    machine, result = self.verify_and_sort(label, confidence)
                    self.assertEqual(result["accepted"], accepted)
                    self.assertEqual(result["points"], 0.5 if accepted else 0)
                    machine.send_command.assert_called_once_with(
                        "CAN" if accepted else "REJECT",
                    )

    def test_weight_limits_and_aliases_before_sorting_and_points(self):
        for label, limit, command in (("plastic_bottle", 255, "BOTTLE"),
                                      ("pet_bottle", 255, "BOTTLE"),
                                      ("aluminum_can", 255, "CAN"),
                                      ("aluminium_can", 255, "CAN")):
            for grams in (-100, -3.351, -1, 0, 0.5, 15, 254,
                          limit - 0.001, limit, limit + 0.001, 300):
                with self.subTest(label=label, grams=grams):
                    machine, result = self.verify_and_sort(label, 0.95, grams)
                    allowed = grams < limit
                    self.assertEqual(result["accepted"], allowed)
                    self.assertEqual(result["points"], 0.5 if allowed else 0)
                    machine.send_command.assert_called_once_with(command if allowed else "REJECT")
                    self.assertEqual(result["inspection"]["weight"]["grams"], grams)
                    self.assertEqual(result["inspection"]["weight"]["limit_g"], limit)
                    if not allowed:
                        self.assertEqual(result["category"], "reject")
                        self.assertIn(f"{limit} g", result["rejection_reason"])

    def test_failed_and_invalid_readings_preserve_acceptance_sorting_and_points(self):
        for label, command in (("plastic_bottle", "BOTTLE"), ("aluminum_can", "CAN")):
            for error in (TimeoutError("unplugged"), RuntimeError("clock timing"),
                          WeightReadingError("invalid", "ADC saturated"),
                          WeightReadingError("unstable", "moving", {"grams": 300, "spread_g": 8})):
                with self.subTest(label=label, error=error), \
                     self.assertLogs("ecorefill.machine", level="ERROR"):
                    machine, result = self.verify_and_sort(label, 0.95, weight_error=error)
                    self.assertTrue(result["accepted"])
                    self.assertEqual(result["points"], 0.5)
                    machine.send_command.assert_called_once_with(command)
                    weight = result["inspection"]["weight"]
                    self.assertEqual(weight["status"], "pass")
                    self.assertTrue(weight["bypassed"])
                    self.assertEqual(weight["measurement_status"],
                                     error.status if isinstance(error, WeightReadingError) else "unavailable")
                    self.assertEqual(weight["detail"], str(error))
                    if isinstance(error, WeightReadingError):
                        for key, value in error.reading.items():
                            self.assertEqual(weight[key], value)
            for grams in (float("nan"), float("inf"), float("-inf")):
                with self.subTest(label=label, grams=grams), \
                     self.assertLogs("ecorefill.machine", level="ERROR"):
                    machine, result = self.verify_and_sort(label, 0.95, grams)
                    self.assertTrue(result["accepted"])
                    self.assertEqual(result["points"], 0.5)
                    machine.send_command.assert_called_once_with(command)
                    self.assertTrue(result["inspection"]["weight"]["bypassed"])
                    self.assertEqual(result["inspection"]["weight"]["measurement_status"], "invalid")

    def test_missing_sensor_preserves_material_acceptance(self):
        machine = MaterialDetection()
        with self.assertLogs("ecorefill.machine", level="ERROR"):
            result = machine.apply_weight_check({"accepted": True, "category": "bottle", "points": 1})
        self.assertTrue(result["accepted"])
        self.assertEqual(result["points"], 1)
        self.assertEqual(result["inspection"]["weight"]["status"], "pass")
        self.assertTrue(result["inspection"]["weight"]["bypassed"])
        self.assertEqual(result["inspection"]["weight"]["measurement_status"], "unavailable")

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
