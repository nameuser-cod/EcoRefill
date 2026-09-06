import ast
import copy
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

import numpy as np

from visual_inspection import VisualInspector, square_crop


class Classifier:
    task = "classify"
    names = {0: "visually_acceptable", 1: "visibly_dirty"}

    def __init__(self, label=0, confidence=0.99):
        self.label, self.confidence = label, confidence

    def predict(self, **kwargs):
        return [SimpleNamespace(names=self.names, probs=SimpleNamespace(
            top1=self.label, top1conf=self.confidence))]


class InspectionTests(unittest.TestCase):
    def setUp(self):
        self.frame = np.zeros((480, 640, 3), dtype=np.uint8)
        self.detection = {"item": "plastic_bottle", "box": [200, 100, 300, 400],
                          "confidence": 0.99, "area_ratio": 0.1}
        self.accepted = {"accepted": True, "category": "bottle", "points": 1,
                         "item": "plastic_bottle", "confidence": 0.99}
        self.config = {"mode": "enforce", "cleanliness": {
            "enabled": True, "min_confidence": 0.9}}

    def apply(self, classifier=None, config=None, detections=None):
        return VisualInspector(config or self.config, classifier=classifier).apply(
            self.accepted, self.frame, detections if detections is not None else [self.detection])

    def test_dirty_or_uncertain_never_earns_points(self):
        for classifier in (Classifier(1), Classifier(0, 0.7), Classifier(0, float("nan"))):
            result = self.apply(classifier)
            self.assertFalse(result["accepted"])
            self.assertEqual(result["category"], "reject")
            self.assertEqual(result["points"], 0)

    def test_visible_pass_does_not_claim_weight(self):
        result = self.apply(Classifier())
        self.assertTrue(result["accepted"])
        self.assertEqual(result["inspection"]["weight"]["status"], "not_installed")
        self.assertEqual(result["inspection"]["size"]["status"], "not_checked")

    def test_unavailable_model_or_no_checks_rejects(self):
        self.assertFalse(self.apply()["accepted"])
        self.assertFalse(self.apply(config={"mode": "enforce"})["accepted"])
        with tempfile.TemporaryDirectory() as directory:
            self.config["cleanliness"]["model_path"] = str(Path(directory) / "missing.pt")
            self.assertFalse(self.apply()["accepted"])

    def test_wrong_model_and_overlapping_size_profiles_reject(self):
        classifier = Classifier()
        classifier.task = "detect"
        self.assertFalse(self.apply(classifier)["accepted"])
        profile = {"name": "overlap", "width_mm": [40, 60], "height_mm": [140, 160]}
        config = {"mode": "enforce", "size": {
            "enabled": True, "frame_size_px": [640, 480],
            "inspection_region_px": [10, 10, 630, 470],
            "mm_per_pixel_x": 0.5, "mm_per_pixel_y": 0.5,
            "profiles": {"plastic_bottle": [profile, profile]},
        }}
        self.assertFalse(self.apply(config=config)["accepted"])

    def test_observation_records_dirty_without_changing_acceptance(self):
        self.config["mode"] = "observe"
        result = self.apply(Classifier(1))
        self.assertTrue(result["accepted"])
        self.assertEqual(result["inspection"]["cleanliness"]["status"], "reject")

    def test_multiple_or_partial_containers_rejected(self):
        self.assertFalse(self.apply(Classifier(), detections=[self.detection] * 2)["accepted"])
        self.detection["box"][0] = 0
        self.assertFalse(self.apply(Classifier())["accepted"])

    def test_calibrated_size_and_cleanliness_must_both_pass(self):
        self.config["size"] = {
            "enabled": True, "frame_size_px": [640, 480],
            "inspection_region_px": [10, 10, 630, 470],
            "mm_per_pixel_x": 0.5, "mm_per_pixel_y": 0.5,
            "profiles": {"plastic_bottle": [
                {"name": "test_group", "width_mm": [40, 60], "height_mm": [140, 160]}
            ]},
        }
        result = self.apply(Classifier())
        self.assertTrue(result["accepted"])
        self.assertEqual(result["inspection"]["size"]["height_mm"], 150)
        self.assertFalse(self.apply(Classifier(1))["accepted"])
        for field, value in (("frame_size_px", [320, 240]), ("mm_per_pixel_x", None),
                             ("mm_per_pixel_y", float("nan")), ("profiles", {})):
            config = copy.deepcopy(self.config)
            config["size"][field] = value
            self.assertFalse(self.apply(Classifier(), config=config)["accepted"])
        self.detection["box"][3] = 450
        self.assertFalse(self.apply(Classifier())["accepted"])

    def test_capture_is_unlabeled_and_preserves_whole_crop(self):
        self.frame[100:400, 200:300] = 255
        crop = square_crop(self.frame, self.detection["box"])
        self.assertEqual(crop.shape, (300, 300, 3))
        self.assertTrue(np.all(crop[:, 100:200] == 255))
        with tempfile.TemporaryDirectory() as directory:
            result = self.apply(config={"mode": "off", "capture_directory": directory})
            self.assertTrue(result["accepted"])
            import json
            metadata = json.loads(next(Path(directory).glob("*.json")).read_text())
            self.assertIsNone(metadata["human_label"])

    def test_machine_verification_routes_dirty_container_to_reject(self):
        # Exercise the actual acceptance and sorting functions without starting
        # GPIO, Firebase, camera, serial, or the machine's background threads.
        source = Path(__file__).with_name("machine_flow.py").read_text()
        tree = ast.parse(source)
        functions = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                     and node.name in {"verify_item", "sort_item"}]
        box = SimpleNamespace(cls=[0], conf=[0.99], xyxy=np.array([[200, 100, 300, 400]]))
        prediction = SimpleNamespace(boxes=[box], plot=lambda: self.frame)
        commands = []
        namespace = {
            "model": SimpleNamespace(names={0: "plastic_bottle"}, predict=lambda **kw: [prediction]),
            "cv2": SimpleNamespace(imwrite=lambda *args: True),
            "normalize_class_name": lambda value: value,
            "DETECTION_CONFIDENCE_LIMIT": 0.2, "INFERENCE_IMAGE_SIZE": 416,
            "MIN_OBJECT_AREA_RATIO": 0.05, "ACCEPT_CONFIDENCE_LIMIT": 0.65,
            "BOTTLE_ITEMS": {"plastic_bottle"}, "CAN_ITEMS": {"aluminum_can"},
            "POINTS": {"plastic_bottle": 1}, "send_to_esp32": commands.append,
        }
        exec(compile(ast.Module(body=functions, type_ignores=[]), "machine_flow.py", "exec"), namespace)
        for mode, command in (("enforce", "REJECT"), ("off", "BOTTLE"), ("observe", "BOTTLE")):
            self.config["mode"] = mode
            namespace["visual_inspector"] = VisualInspector(self.config, classifier=Classifier(1))
            result = namespace["verify_item"](self.frame)
            namespace["sort_item"](result)
            self.assertEqual(commands[-1], command)
            self.assertEqual(result["points"], 0 if mode == "enforce" else 1)


if __name__ == "__main__":
    unittest.main()
