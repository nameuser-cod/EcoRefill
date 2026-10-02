"""Camera configuration regressions without Raspberry Pi hardware."""

import base64
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import cv2
import numpy as np

from machine.camera import CameraSupport


class CameraTests(unittest.TestCase):
    def test_selects_widest_sufficient_mode_without_full_resolution_cost(self):
        camera = Mock()
        camera.sensor_modes = [
            {"size": (1920, 1080), "crop_limits": (348, 434, 1920, 1080), "format": "cropped"},
            {"size": (2592, 1944), "crop_limits": (0, 0, 2592, 1944), "format": "full"},
            {"size": (640, 480), "crop_limits": (0, 0, 2592, 1944), "format": "small"},
            {"size": (1296, 972), "crop_limits": (0, 0, 2592, 1944), "format": "binned"},
        ]
        with patch.dict(sys.modules, {"picamera2": SimpleNamespace(Picamera2=lambda: camera)}), \
             patch("machine.camera.time.sleep"), \
             patch("machine.camera.CAMERA_WIDTH", 1280), \
             patch("machine.camera.CAMERA_HEIGHT", 960):
            self.assertIs(CameraSupport().initialize_camera(), camera)
        config = camera.create_preview_configuration.call_args.kwargs
        self.assertEqual(config["main"]["size"], (1280, 960))
        self.assertEqual(config["raw"], {"size": (1296, 972), "format": "binned"})
        camera.start.assert_called_once_with()
        camera.close.assert_not_called()

    def test_configuration_failure_releases_camera_for_recovery(self):
        camera = Mock(sensor_modes=[])
        with patch.dict(sys.modules, {"picamera2": SimpleNamespace(Picamera2=lambda: camera)}):
            with self.assertRaisesRegex(ValueError, "no sensor mode"):
                CameraSupport().initialize_camera()
        camera.close.assert_called_once_with()
        camera.start.assert_not_called()

    def test_history_photo_retains_full_view_at_larger_size(self):
        frame = np.zeros((960, 1280, 3), dtype=np.uint8)
        frame[:, :640] = (255, 0, 0)
        frame[:, 640:] = (0, 0, 255)
        original = frame.copy()
        with patch("machine.camera.RECYCLING_IMAGE_WIDTH", 640), \
             patch("machine.camera.RECYCLING_IMAGE_HEIGHT", 480), \
             patch("machine.camera.RECYCLING_IMAGE_JPEG_QUALITY", 80):
            url = CameraSupport().frame_to_base64_data_url(frame)
        header, payload = url.split(",", 1)
        self.assertEqual(header, "data:image/jpeg;base64")
        decoded = cv2.imdecode(np.frombuffer(base64.b64decode(payload), dtype=np.uint8), cv2.IMREAD_COLOR)
        self.assertEqual(decoded.shape, (480, 640, 3))
        self.assertGreater(int(decoded[240, 10, 0]), 240)
        self.assertGreater(int(decoded[240, 630, 2]), 240)
        np.testing.assert_array_equal(frame, original)


if __name__ == "__main__":
    unittest.main()
