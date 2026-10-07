"""Benchmark production material decisions without cameras, GPIO or Firebase.

Manifest CSV: image,expected,group. Expected: plastic_bottle/aluminum_can/reject.
Use --images instead for timing only. Run one model per process for clean memory
measurements. Hardware/visual checks and preview file writes are bypassed.
"""

import argparse
from collections import Counter
import contextlib
import csv
import io
import json
import math
from pathlib import Path
import platform
import shutil
import statistics
import subprocess
import threading
import time
from types import SimpleNamespace


def pi_health():
    temperature = Path("/sys/class/thermal/thermal_zone0/temp")
    result = {"temperature_c": None, "throttled_bits": None}
    try:
        result["temperature_c"] = float(temperature.read_text()) / 1000
    except (OSError, ValueError):
        pass
    if shutil.which("vcgencmd"):
        try:
            command = subprocess.run(["vcgencmd", "get_throttled"], capture_output=True,
                                     text=True, timeout=1, check=True)
            result["throttled_bits"] = command.stdout.strip().split("=", 1)[1]
        except (OSError, subprocess.SubprocessError, IndexError):
            pass
    return result


def read_manifest(path):
    path = path.resolve()
    with path.open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    if not rows or any(row.get("expected") not in {"plastic_bottle", "aluminum_can", "reject"}
                       or not row.get("group", "").strip() or not row.get("image") for row in rows):
        raise ValueError("Manifest needs image, expected and group for every row.")
    for row in rows:
        row["image"] = str((path.parent / row["image"]).resolve())
    if len({row["image"] for row in rows}) != len(rows):
        raise ValueError("Manifest contains duplicate image paths.")
    return rows


def summarize_decisions(decisions):
    confusion = Counter((row["expected"], row["predicted"]) for row in decisions)
    labels = ("plastic_bottle", "aluminum_can", "reject")
    return {
        "images": len(decisions),
        "expected_counts": dict(Counter(row["expected"] for row in decisions)),
        "correct": sum(row["expected"] == row["predicted"] for row in decisions),
        "false_accepts": sum(count for (truth, predicted), count in confusion.items()
                             if truth == "reject" and predicted != "reject"),
        "false_rejects": sum(count for (truth, predicted), count in confusion.items()
                             if truth != "reject" and predicted == "reject"),
        "wrong_material_accepts": sum(count for (truth, predicted), count in confusion.items()
                                      if truth != "reject" and predicted not in (truth, "reject")),
        "confusion": {truth: {predicted: confusion[(truth, predicted)] for predicted in labels}
                      for truth in labels},
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=Path, required=True)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--manifest", type=Path)
    source.add_argument("--images", type=Path, help="Image directory; performance only, no accuracy claims")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--imgsz", type=int, default=416)
    parser.add_argument("--threads", type=int, default=2)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--warmup", type=int, default=2)
    parser.add_argument("--interval", type=float, default=0, help="Seconds between items; 0 is a stress test")
    parser.add_argument("--full-frame", action="store_true", help="Public images only; disables machine scan crop")
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Choose a new output; existing reports are never overwritten")
    if args.threads < 1 or args.repeats < 1 or args.warmup < 0 or args.interval < 0:
        parser.error("Threads/repeats must be positive, warmup/interval nonnegative")
    if args.imgsz < 32 or args.imgsz % 32:
        parser.error("--imgsz must be a positive multiple of 32")
    try:
        if args.manifest:
            rows = read_manifest(args.manifest)
        else:
            rows = [{"image": str(path.resolve())} for path in sorted(args.images.rglob("*"))
                    if path.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"} and path.is_file()]
        if not rows or any(not Path(row["image"]).is_file() for row in rows):
            parser.error("Provide existing images; no images found or manifest image missing")
    except (OSError, ValueError) as error:
        parser.error(str(error))

    from machine.inference import load_detection_model
    model = load_detection_model(args.model, args.imgsz, args.threads)
    import cv2
    import psutil
    import ultralytics
    from machine import detection, scan_region
    from machine import config

    detection.INFERENCE_IMAGE_SIZE = args.imgsz
    if args.full_frame:
        scan_region.DETECTION_REGION = None

    class OfflineDetector(detection.MaterialDetection):
        def save_detection_preview(self, *_):
            pass

        def apply_weight_check(self, result, settling_started=None):
            return result

    detector = OfflineDetector()
    detector.model = model
    detector.visual_inspector = SimpleNamespace(apply=lambda result, *_: result)

    def predict(row):
        frame = cv2.imread(row["image"])
        if frame is None:
            raise ValueError(f"Unable to decode {row['image']}")
        # Excludes disk decoding. Includes crop, preprocessing, inference and
        # production confidence/area decisions, unlike inference-only FPS.
        started = time.perf_counter()
        with contextlib.redirect_stdout(io.StringIO()):
            result = detector.verify_item(frame)
        return result, (time.perf_counter() - started) * 1000

    for index in range(args.warmup):
        predict(rows[index % len(rows)])

    process = psutil.Process()
    samples, stop = [], threading.Event()

    def sample():
        samples.append({"elapsed_s": time.perf_counter() - started,
                        "process_rss_mb": process.memory_info().rss / 1024 ** 2,
                        "system_cpu_percent": psutil.cpu_percent(), **pi_health()})

    def monitor():
        while not stop.wait(1):
            sample()

    psutil.cpu_percent()
    health_before = pi_health()
    started = time.perf_counter()
    cpu_before = process.cpu_times()
    sample()
    worker = threading.Thread(target=monitor, daemon=True)
    worker.start()
    durations, decisions = [], []
    try:
        for repeat in range(args.repeats):
            for row in rows:
                result, milliseconds = predict(row)
                durations.append(milliseconds)
                if repeat == 0 and args.manifest:
                    decisions.append({**row, "predicted": result["item"] if result["accepted"] else "reject",
                                      "confidence": float(result["confidence"])})
                if args.interval:
                    time.sleep(args.interval)
    finally:
        stop.set()
        worker.join(timeout=3)
    elapsed = time.perf_counter() - started
    cpu_after = process.cpu_times()
    sample()
    cpu_seconds = cpu_after.user + cpu_after.system - cpu_before.user - cpu_before.system
    ordered = sorted(durations)
    temperatures = [row["temperature_c"] for row in samples if row["temperature_c"] is not None]
    report = {
        "scope": "Offline material decisions only; no camera, hardware, visual/weight checks, cloud or rewards. "
                 "Measure the live kiosk and idle motion workload separately.",
        "host": {"system": platform.system(), "machine": platform.machine(), "cpu_count": psutil.cpu_count(),
                 "ultralytics": ultralytics.__version__},
        "settings": {"model": str(args.model.resolve()), "image_size": args.imgsz, "threads": args.threads,
                     "repeats": args.repeats, "warmup": args.warmup, "interval_s": args.interval,
                     "scan_region": scan_region.DETECTION_REGION,
                     "bottle_confidence": config.BOTTLE_ACCEPT_CONFIDENCE_LIMIT,
                     "can_confidence": config.ACCEPT_CONFIDENCE_LIMIT,
                     "candidate_confidence": config.DETECTION_CONFIDENCE_LIMIT,
                     "minimum_area": config.MIN_OBJECT_AREA_RATIO,
                     "manifest": str(args.manifest.resolve()) if args.manifest else None,
                     "images": len(rows)},
        "performance": {"scans": len(durations), "elapsed_s": elapsed,
                        "decision_median_ms": statistics.median(durations),
                        "decision_p95_ms": ordered[max(0, math.ceil(len(ordered) * .95) - 1)],
                        "decision_max_ms": max(durations),
                        "process_cpu_percent_one_core": cpu_seconds / elapsed * 100,
                        "process_cpu_percent_all_cores": cpu_seconds / elapsed / (psutil.cpu_count() or 1) * 100,
                        "sampled_peak_rss_mb": max(row["process_rss_mb"] for row in samples),
                        "sampled_max_temperature_c": max(temperatures) if temperatures else None},
        "pi_health_before": health_before, "pi_health_after": pi_health(), "samples": samples,
        "material_summary": summarize_decisions(decisions) if decisions else None,
        "decisions": decisions,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as handle:
        json.dump(report, handle, indent=2)
        handle.write("\n")
    print(json.dumps({"performance": report["performance"], "materials": report["material_summary"]}, indent=2))
    print(f"Report: {args.output}")


if __name__ == "__main__":
    main()
