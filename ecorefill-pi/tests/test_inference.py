"""Guard model compatibility, export resolution, and backend thread limits."""

from pathlib import Path
import json
import os
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from machine.inference import load_detection_model, validate_model_path
from tools.benchmark_detection import summarize_decisions


class InferenceTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.weights = self.root / "baseline.pt"
        self.weights.write_bytes(b"test weights")
        self.ncnn = self.root / "candidate_ncnn_model"
        self.ncnn.mkdir()
        (self.ncnn / "model.param").write_text("test")
        (self.ncnn / "model.bin").write_bytes(b"test")
        (self.ncnn / "metadata.yaml").write_text("task: detect\nimgsz: [416, 416]\n")

    def read_config(self, settings, overrides=None):
        path = self.root / "inference.local.json"
        path.write_text(json.dumps(settings))
        environment = {key: value for key, value in os.environ.items() if not key.startswith("ECOREFILL_INFERENCE_")
                       and key not in {"ECOREFILL_MODEL_PATH", "ECOREFILL_MOTION_LOW_RES"}}
        environment.update({"ECOREFILL_INFERENCE_CONFIG": str(path), **(overrides or {})})
        return subprocess.run([sys.executable, "-c", """
import json
from machine import config
print(json.dumps([config.MODEL_PATH, config.INFERENCE_IMAGE_SIZE, config.INFERENCE_THREADS, config.MOTION_LOW_RES]))
"""], cwd=Path(__file__).resolve().parents[1], env=environment, capture_output=True, text=True)

    def test_local_settings_persist_a_verified_model_without_changing_source_defaults(self):
        result = self.read_config({"model_path": "models/verified_ncnn_model", "image_size": 416,
                                   "threads": 1, "motion_low_res": True})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), ["models/verified_ncnn_model", 416, 1, True])

    def test_environment_can_override_persistent_settings_for_rollback(self):
        result = self.read_config({"model_path": "models/verified_ncnn_model", "threads": 1},
                                  {"ECOREFILL_MODEL_PATH": "models/ecorefill_best.pt",
                                   "ECOREFILL_INFERENCE_THREADS": "2", "ECOREFILL_MOTION_LOW_RES": "false"})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), ["models/ecorefill_best.pt", 416, 2, False])

    def test_invalid_settings_fail_before_any_hardware_initialization(self):
        for settings in ({"threads": True}, {"threads": 0}, {"image_size": 319}, {"model_path": ""},
                         {"motion_low_res": "false"}, {"threadz": 1}):
            with self.subTest(settings=settings):
                result = self.read_config(settings)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("ValueError", result.stderr)

    def test_missing_path_cannot_trigger_a_pretrained_download(self):
        with self.assertRaises(ValueError):
            validate_model_path(self.root / "yolo26n.pt", 416)

    def test_ncnn_requires_matching_files_and_export_resolution(self):
        self.assertEqual(validate_model_path(self.ncnn, 416), self.ncnn)
        with self.assertRaisesRegex(ValueError, "does not match"):
            validate_model_path(self.ncnn, 320)
        (self.ncnn / "model.bin").unlink()
        with self.assertRaisesRegex(ValueError, "matching .bin"):
            validate_model_path(self.ncnn, 416)

    def test_ncnn_without_detection_metadata_is_rejected(self):
        (self.ncnn / "metadata.yaml").write_text("task: classify\nimgsz: [416, 416]\n")
        with self.assertRaisesRegex(ValueError, "object detection"):
            validate_model_path(self.ncnn, 416)
        (self.ncnn / "metadata.yaml").unlink()
        with self.assertRaisesRegex(ValueError, "metadata.yaml"):
            validate_model_path(self.ncnn, 416)

    def load_fake(self, path, labels, threads=2):
        net = Mock(opt=SimpleNamespace(), load_param=Mock(return_value=0), load_model=Mock(return_value=0))
        backend = SimpleNamespace(names=labels, net=net)
        net.load_param.side_effect = lambda *_: 0 if net.opt.num_threads == threads else -1

        class Predictor:
            def __init__(self, overrides):
                self.args = overrides

            def setup_model(self, model, verbose=False):
                self.model = backend

        class Model:
            task = "detect"
            model = object()
            overrides = {}

            @property
            def names(self):
                return self.predictor.model.names

        modules = {"ultralytics": SimpleNamespace(YOLO=Mock(return_value=Model())),
                   "ultralytics.models.yolo.detect": SimpleNamespace(DetectionPredictor=Predictor)}
        with patch.dict(sys.modules, modules), patch("machine.inference.configure_cpu_threads") as configure:
            model = load_detection_model(path, 416, threads)
            configure.assert_called_once_with(threads)
        return model, backend

    def test_ncnn_thread_limit_is_set_before_any_inference(self):
        model, backend = self.load_fake(self.ncnn, {0: "plastic_bottle", 1: "aluminum_can"})
        self.assertEqual(backend.net.opt.num_threads, 2)
        self.assertFalse(backend.net.opt.use_vulkan_compute)
        self.assertFalse(backend.net.opt.use_fp16_packed)
        self.assertFalse(backend.net.opt.use_fp16_storage)
        self.assertFalse(backend.net.opt.use_fp16_arithmetic)
        self.assertFalse(backend.net.opt.use_bf16_storage)
        backend.net.clear.assert_called_once_with()
        backend.net.load_param.assert_called_once_with(str(self.ncnn / "model.param"))
        backend.net.load_model.assert_called_once_with(str(self.ncnn / "model.bin"))
        self.assertEqual(model.predictor.args["device"], "cpu")
        self.assertEqual(model.overrides["device"], "cpu")

    def test_generic_pretrained_labels_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "explicitly"):
            self.load_fake(self.weights, {0: "bottle", 1: "can"})

    def test_wrong_material_accepts_are_not_counted_as_correct_recycling(self):
        summary = summarize_decisions([
            {"expected": "aluminum_can", "predicted": "plastic_bottle"},
            {"expected": "reject", "predicted": "plastic_bottle"},
            {"expected": "plastic_bottle", "predicted": "reject"},
            {"expected": "aluminum_can", "predicted": "aluminum_can"},
        ])
        self.assertEqual(summary["correct"], 1)
        self.assertEqual(summary["false_accepts"], 1)
        self.assertEqual(summary["false_rejects"], 1)
        self.assertEqual(summary["wrong_material_accepts"], 1)


if __name__ == "__main__":
    unittest.main()
