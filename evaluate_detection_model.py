"""Compare material decisions on full-frame machine photos, without hardware.

CSV columns: image,expected,group. Expected: plastic_bottle/aluminum_can/reject.
This evaluates camera/material decisions only, not weight or cleanliness.
"""

import argparse
from collections import Counter
import contextlib
import csv
import io
import json
from pathlib import Path
import sys
from types import SimpleNamespace


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--model", action="append", required=True, metavar="NAME=CHECKPOINT")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--full-frame", action="store_true",
                        help="Public-dataset diagnostic: bypass machine crop; not a machine accuracy result")
    parser.add_argument("--device", default="cpu", help="Inference device; default CPU matches the Pi path")
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Choose a new output report; existing reports are not overwritten")
    manifest = args.manifest.resolve()
    with manifest.open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    expected_labels = {"plastic_bottle", "aluminum_can", "reject"}
    if not rows or any(r.get("expected") not in expected_labels or not r.get("group", "").strip() for r in rows):
        parser.error("Manifest needs image, expected and group; expected must be plastic_bottle/aluminum_can/reject")
    specs = {}
    for spec in args.model:
        name, separator, checkpoint = spec.partition("=")
        if not separator or not name or name in specs or not Path(checkpoint).is_file():
            parser.error("Each model must have a unique NAME and an existing local checkpoint")
        specs[name] = checkpoint

    import cv2
    from ultralytics import YOLO
    sys.path.insert(0, str(Path(__file__).resolve().parent / "ecorefill-pi"))
    from machine.detection import MaterialDetection
    from machine import config
    from machine import scan_region
    if args.full_frame:
        scan_region.DETECTION_REGION = None

    class OfflineDetector(MaterialDetection):
        def save_detection_preview(self, frame, detection=None):
            pass

        def apply_weight_check(self, result, settling_started=None):
            return result

    report = {"scope": "Material decision only; weight and visual inspection bypassed. No sorting or rewards.",
              "input_mode": "public-dataset full-frame diagnostic" if args.full_frame else "machine camera crop",
              "manifest": str(manifest), "settings": {
                  "device": args.device,
                  "image_size": config.INFERENCE_IMAGE_SIZE,
                  "scan_region": scan_region.DETECTION_REGION,
                  "bottle_confidence": config.BOTTLE_ACCEPT_CONFIDENCE_LIMIT,
                  "accept_confidence": config.ACCEPT_CONFIDENCE_LIMIT,
                  "candidate_confidence": config.DETECTION_CONFIDENCE_LIMIT,
                  "minimum_area": config.MIN_OBJECT_AREA_RATIO}, "models": {}}
    for name, checkpoint in specs.items():
        detector = OfflineDetector()
        detector.model = YOLO(checkpoint).to(args.device)
        if detector.model.names != {0: "plastic_bottle", 1: "aluminum_can"}:
            parser.error(f"{name}: checkpoint classes do not match the dataset")
        detector.visual_inspector = SimpleNamespace(apply=lambda result, *_: result)
        decisions, confusion = [], Counter()
        for row in rows:
            path = (manifest.parent / row["image"]).resolve()
            frame = cv2.imread(str(path))
            if frame is None:
                parser.error(f"Unable to read {path}")
            with contextlib.redirect_stdout(io.StringIO()):
                result = detector.verify_item(frame)
            predicted = result["item"] if result["accepted"] else "reject"
            confusion[(row["expected"], predicted)] += 1
            decisions.append(dict(image=str(path), expected=row["expected"], group=row["group"],
                                  predicted=predicted, confidence=result["confidence"]))
        totals = Counter(row["expected"] for row in rows)
        false_accepts = sum(v for (truth, pred), v in confusion.items() if truth == "reject" and pred != "reject")
        valid = totals["plastic_bottle"] + totals["aluminum_can"]
        false_rejects = sum(v for (truth, pred), v in confusion.items() if truth != "reject" and pred == "reject")
        wrong_material = sum(v for (truth, pred), v in confusion.items() if truth != "reject" and pred not in (truth, "reject"))
        summary = dict(images=len(rows), expected_counts=dict(totals), false_accepts=false_accepts,
                       false_accept_rate=false_accepts / totals["reject"] if totals["reject"] else None,
                       false_rejects=false_rejects, false_reject_rate=false_rejects / valid if valid else None,
                       wrong_material_accepts=wrong_material,
                       confusion={truth: {pred: confusion[(truth, pred)] for pred in sorted(expected_labels)}
                                  for truth in sorted(expected_labels)})
        report["models"][name] = dict(checkpoint=str(Path(checkpoint).resolve()), summary=summary, decisions=decisions)
        print(name, json.dumps(summary, indent=2))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as handle:
        json.dump(report, handle, indent=2)
        handle.write("\n")


if __name__ == "__main__":
    main()
