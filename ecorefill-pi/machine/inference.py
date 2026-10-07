"""Load local detection weights with bounded CPU use and no hardware access."""

import os
from pathlib import Path


def validate_model_path(path, image_size):
    path = Path(path).expanduser().resolve()
    if path.is_file() and path.suffix == ".pt":
        return path
    if not path.is_dir() or not path.name.endswith("_ncnn_model"):
        raise ValueError(f"Expected a local .pt file or *_ncnn_model directory: {path}")
    params = list(path.glob("*.param"))
    if len(params) != 1 or not params[0].with_suffix(".bin").is_file():
        raise ValueError("NCNN directory needs one .param and its matching .bin file.")
    import yaml

    metadata_path = path / "metadata.yaml"
    if not metadata_path.is_file():
        raise ValueError("NCNN metadata.yaml is required to verify class names and export size.")
    metadata = yaml.safe_load(metadata_path.read_text())
    if not isinstance(metadata, dict) or metadata.get("task") != "detect":
        raise ValueError("Expected NCNN metadata for an object detection model.")
    if metadata.get("imgsz") != [image_size, image_size]:
        raise ValueError(f"NCNN export size {metadata.get('imgsz')} does not match {image_size}; "
                         "use a matching export and ECOREFILL_INFERENCE_SIZE.")
    return path


def configure_cpu_threads(threads):
    if threads < 1:
        raise ValueError("Inference threads must be positive.")
    # Set before numerical libraries are imported. Explicit library settings
    # below also cover programs that have already imported torch or OpenCV.
    for variable in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
                     "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
        os.environ[variable] = str(threads)
    import torch
    import cv2

    torch.set_num_threads(threads)
    cv2.setNumThreads(1)


def load_detection_model(path, image_size=416, threads=2):
    """Initialize both formats on CPU, including NCNN's separate thread pool."""
    if image_size < 32 or image_size % 32:
        raise ValueError("Inference size must be a positive multiple of 32.")
    path = validate_model_path(path, image_size)
    configure_cpu_threads(threads)
    from ultralytics import YOLO
    from ultralytics.models.yolo.detect import DetectionPredictor

    class BoundedCPUPredictor(DetectionPredictor):
        def setup_model(self, model, verbose=False):
            super().setup_model(model, verbose=verbose)
            if path.is_dir():
                net = getattr(self.model, "net", None)
                if net is None:
                    raise RuntimeError("NCNN backend does not expose its thread settings; check Ultralytics version.")
                # NCNN convolution pipelines capture num_threads at load time.
                # Ultralytics has already loaded the net using its defaults:
                # rebuild it, setting options BEFORE either file is loaded.
                net.clear()
                net.opt.num_threads = threads
                net.opt.use_vulkan_compute = False
                # ARM can enable FP16 execution even for an FP32 export. Keep
                # material decisions in full precision across host platforms.
                net.opt.use_fp16_packed = False
                net.opt.use_fp16_storage = False
                net.opt.use_fp16_arithmetic = False
                net.opt.use_bf16_storage = False
                param = next(path.glob("*.param"))
                if net.load_param(str(param)) != 0 or net.load_model(str(param.with_suffix(".bin"))) != 0:
                    raise RuntimeError(f"Failed to reload NCNN weights with CPU thread limit: {path}")

    model = YOLO(str(path), task="detect")
    if model.task != "detect":
        raise ValueError("EcoRefill requires detection weights, not classification/segmentation weights.")
    # predict() merges these again on every call. Keep CPU in the model's
    # overrides too, so a training-device setting cannot replace our predictor
    # and discard NCNN's thread limit on the first real item.
    model.overrides.update({"device": "cpu", "imgsz": image_size, "batch": 1})
    model.predictor = BoundedCPUPredictor(overrides={
        **model.overrides, "device": "cpu", "imgsz": image_size,
        "batch": 1, "verbose": False, "save": False,
    })
    model.predictor.setup_model(model.model)
    names = model.names
    labels = set(names.values())
    if not labels & {"plastic_bottle", "pet_bottle"} or not labels & {"aluminum_can", "aluminium_can"}:
        raise ValueError(f"Model must include plastic bottles and aluminum cans explicitly; got {names}.")
    return model
