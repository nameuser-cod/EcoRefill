"""Synthetic geometry verifies classification rules, not real camera accuracy."""

import copy
import unittest

import numpy as np

from machine.visual_inspection import VisualInspector
from tools.calibrate_bottle_size import build_config


class BottleSizeTests(unittest.TestCase):
    def setUp(self):
        self.frame = np.zeros((960, 1280, 3), dtype=np.uint8)
        self.reference = {"frame_size_px": [1280, 960], "detection": {
            "item": "plastic_bottle", "box": [200, 100, 300, 400],
        }}
        self.profiles = [
            {"name": "Small",
             "width_mm": [40, 60], "height_mm": [140, 160]},
            {"name": "Medium",
             "width_mm": [60, 80], "height_mm": [180, 220]},
            {"name": "Large",
             "width_mm": [85, 110], "height_mm": [240, 280]},
        ]
        self.config = build_config(self.reference, 50, 150, self.profiles)

    def scan(self, box, item="plastic_bottle", config=None):
        result = {"accepted": True, "item": item, "category": "bottle", "points": 0.5}
        return VisualInspector(config or self.config).apply(
            result, self.frame, [{"item": item, "box": box}])

    def test_each_calibrated_group_for_both_bottle_labels(self):
        for item in ("plastic_bottle", "pet_bottle"):
            for width, height, group in ((100, 300, "Small"), (140, 400, "Medium"), (200, 520, "Large")):
                with self.subTest(item=item, group=group):
                    result = self.scan([200, 100, 200 + width, 100 + height], item)
                    size = result["inspection"]["size"]
                    self.assertEqual(size["status"], "pass")
                    self.assertEqual(size["size_group"], group)
                    self.assertEqual(result["points"], 0.5)

    def test_unmatched_or_overlapping_profiles_never_claim_size(self):
        for overlap in (False, True):
            config = copy.deepcopy(self.config)
            if overlap:
                config["size"]["profiles"]["plastic_bottle"].append(self.profiles[0])
            box = [200, 100, 300, 400] if overlap else [200, 100, 230, 180]
            result = self.scan(box, config=config)
            self.assertTrue(result["accepted"])
            self.assertIsNone(result["inspection"]["size"]["size_group"])
            config["mode"] = "enforce"
            rejected = self.scan(box, config=config)
            self.assertFalse(rejected["accepted"])
            self.assertEqual(rejected["points"], 0)

    def test_bottle_only_enforcement_allows_cans_but_requires_bottle_profiles(self):
        self.config["mode"] = "enforce"
        for item in ("aluminum_can", "aluminium_can"):
            result = self.scan([200, 100, 300, 400], item)
            self.assertTrue(result["accepted"])
            self.assertEqual(result["inspection"]["size"]["status"], "not_applicable")
        self.config["size"]["profiles"]["plastic_bottle"] = []
        self.assertFalse(self.scan([200, 100, 300, 400])["accepted"])

    def test_partial_view_and_changed_resolution_have_no_group(self):
        for box in ([0, 100, 300, 400], [200, 100, 300, 400]):
            result = self.scan(box)
            self.assertNotIn("size_group", result["inspection"]["size"])
            self.assertIn(result["inspection"]["size"]["status"], {"uncertain", "unavailable"})
            self.config["size"]["frame_size_px"] = [640, 480]

    def test_calibration_rejects_missing_measurements_and_ambiguous_profiles(self):
        for value in (None, 0, -1, True, float("nan"), float("inf")):
            with self.subTest(value=value), self.assertRaises(ValueError):
                build_config(self.reference, value, 150, self.profiles)
        for bad_profiles in ([], self.profiles + [self.profiles[0]],
                             [{**self.profiles[0], "width_mm": [None, None]}],
                             [self.profiles[0], {**self.profiles[0], "name": "Other bottle"}]):
            with self.assertRaises(ValueError):
                build_config(self.reference, 50, 150, bad_profiles)
        with self.assertRaises(ValueError):
            build_config({"detection": self.reference["detection"]}, 50, 150, self.profiles)


if __name__ == "__main__":
    unittest.main()
