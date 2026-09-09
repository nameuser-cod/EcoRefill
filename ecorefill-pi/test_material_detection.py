"""Acceptance and routing regressions with simulated model predictions."""

import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from machine.detection import MaterialDetection


class MaterialDetectionTests(unittest.TestCase):
    def verify_and_sort(self, label, confidence):
        machine = MaterialDetection()
        box = SimpleNamespace(
            cls=[0], conf=[confidence],
            xyxy=[Mock(tolist=Mock(return_value=[100, 50, 400, 400]))],
        )
        prediction = SimpleNamespace(boxes=[box], plot=Mock())
        machine.model = SimpleNamespace(
            names={0: label}, predict=Mock(return_value=[prediction]),
        )
        machine.visual_inspector = SimpleNamespace(
            apply=Mock(side_effect=lambda result, *_: result),
        )
        machine.send_to_esp32 = Mock(return_value=True)
        with patch.dict(sys.modules, {"cv2": SimpleNamespace(imwrite=Mock())}):
            result = machine.verify_item(SimpleNamespace(shape=(480, 640, 3)))
        machine.sort_item(result)
        return machine, result

    def test_reported_can_misclassifications_do_not_open_bottle_gate(self):
        # Replay the reported predictions, not inference on the screenshot.
        for confidence in (0.53, 0.66):
            with self.subTest(confidence=confidence):
                machine, result = self.verify_and_sort("plastic_bottle", confidence)
                self.assertFalse(result["accepted"])
                self.assertEqual(result["points"], 0)
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


if __name__ == "__main__":
    unittest.main()
