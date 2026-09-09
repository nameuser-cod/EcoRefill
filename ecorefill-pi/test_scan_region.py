"""Check scan isolation, inspection coordinates, and unchanged clean photos."""

from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import numpy as np

from machine.camera import CameraSupport
from machine.detection import MaterialDetection
from machine.scan_region import scan_region_bounds


class ScanRegionTests(unittest.TestCase):
    def setUp(self):
        self.frame = np.zeros((480, 640, 3), dtype=np.uint8)
        self.bounds = scan_region_bounds(self.frame)

    def test_bounds_scale_with_camera_resolution(self):
        self.assertEqual(self.bounds, (211, 19, 416, 461))
        self.assertEqual(scan_region_bounds(np.zeros((960, 1280, 3))),
                         (422, 38, 832, 922))
        with patch("machine.scan_region.DETECTION_REGION", None):
            self.assertEqual(scan_region_bounds(self.frame), (0, 0, 640, 480))
        for region in ((0.8, 0, 0.2, 1), (-0.1, 0, 1, 1), (0, 0, float("nan"), 1)):
            with self.subTest(region=region), \
                 patch("machine.scan_region.DETECTION_REGION", region):
                with self.assertRaises(ValueError):
                    scan_region_bounds(self.frame)

    def test_motion_outside_box_is_ignored_but_inside_triggers(self):
        camera = CameraSupport()
        baseline = camera.prepare_motion_frame(self.frame)
        self.frame[:, :200] = 255
        self.frame[:, 430:] = 255
        outside_motion, _, _ = camera.frame_has_motion(baseline, self.frame)
        self.assertFalse(outside_motion)
        self.frame[100:300, 250:350] = 255
        inside_motion, _, _ = camera.frame_has_motion(baseline, self.frame)
        self.assertTrue(inside_motion)

    def test_higher_resolution_preserves_motion_sensitivity_and_region(self):
        camera = CameraSupport()
        baseline = camera.prepare_motion_frame(self.frame)
        # The same physical scene at twice the width and height must retain
        # both the scan boundary and the original pixel-area threshold.
        for area in ((10, 10, 180, 300), (250, 100, 350, 300), (280, 180, 290, 190)):
            with self.subTest(area=area):
                frame = self.frame.copy()
                left, top, right, bottom = area
                frame[top:bottom, left:right] = 255
                large = np.repeat(np.repeat(frame, 2, axis=0), 2, axis=1)
                motion, gray, changed_area = camera.frame_has_motion(baseline, frame)
                large_motion, large_gray, large_area = camera.frame_has_motion(baseline, large)
                self.assertEqual(large_motion, motion)
                self.assertEqual(large_area, changed_area)
                np.testing.assert_array_equal(large_gray, gray)

    def test_inference_receives_only_scan_pixels_and_inspection_gets_full_coordinates(self):
        left, top, right, bottom = self.bounds
        self.frame[:, :] = 200  # Background must not reach the model.
        self.frame[top:bottom, left:right] = 50
        original = self.frame.copy()
        box = SimpleNamespace(cls=[0], conf=[0.95], xyxy=np.array([[20, 30, 150, 350]]))
        prediction = SimpleNamespace(
            boxes=[box], plot=lambda: np.full((bottom-top, right-left, 3), 100, np.uint8),
        )
        machine = MaterialDetection()
        machine.weight_scale = SimpleNamespace(read_weight=lambda: {"grams": 20.0})
        machine.model = SimpleNamespace(names={0: "aluminum_can"},
                                        predict=Mock(return_value=[prediction]))
        machine.visual_inspector = SimpleNamespace(apply=Mock(side_effect=lambda result, *_: result))
        with patch("cv2.imwrite", return_value=True) as write:
            result = machine.verify_item(self.frame)
        source = machine.model.predict.call_args.kwargs["source"]
        self.assertEqual(source.shape, (442, 205, 3))
        self.assertTrue(np.all(source == 50))
        self.assertTrue(np.array_equal(self.frame, original))
        self.assertTrue(result["accepted"])
        _, inspected_frame, detections = machine.visual_inspector.apply.call_args.args
        self.assertIs(inspected_frame, self.frame)
        self.assertEqual(detections[0]["box"], [231, 49, 361, 369])
        self.assertAlmostEqual(detections[0]["area_ratio"], 130*320/(640*480))
        preview = write.call_args.args[1]
        self.assertEqual(preview.shape, self.frame.shape)
        self.assertTrue(np.array_equal(preview[300, 50], original[300, 50]))
        self.assertEqual(preview[top, left].tolist(), [50, 50, 50])
        self.assertEqual(preview[49, 231].tolist(), [255, 100, 0])
        self.assertFalse(np.any(np.all(preview == [0, 255, 255], axis=2)))

    def test_empty_scan_rejects_and_saves_clean_view_without_scan_box(self):
        machine = MaterialDetection()
        machine.weight_scale = SimpleNamespace(read_weight=lambda: {"grams": 20.0})
        machine.model = SimpleNamespace(predict=Mock(return_value=[]))
        machine.send_to_esp32 = Mock()
        with patch("cv2.imwrite", return_value=True) as write:
            result = machine.verify_item(self.frame)
        self.assertFalse(result["accepted"])
        machine.sort_item(result)
        machine.send_to_esp32.assert_called_once_with("REJECT")
        self.assertEqual(write.call_args.args[0], "detection_result.jpg")
        self.assertTrue(np.array_equal(write.call_args.args[1], self.frame))


if __name__ == "__main__":
    unittest.main()
