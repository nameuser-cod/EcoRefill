"""Train a candidate checkpoint; never install it into the machine automatically."""

import argparse
import json
from functools import partial
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--model", default="yolov8n.pt")
    parser.add_argument("--epochs", type=int, default=50)
    parser.add_argument("--imgsz", type=int, default=416)
    parser.add_argument("--batch", type=int, default=8)
    parser.add_argument("--device", default="cpu", help="cpu, mps (Apple GPU), or CUDA index")
    parser.add_argument("--name", default="ecorefill_taco_waste")
    parser.add_argument("--patience", type=int, default=10, help="Early stopping after this many unimproved epochs")
    parser.add_argument("--nms-time-limit", type=float, default=1.0,
                        help="Validation NMS seconds per image; avoids batch truncation on MPS")
    parser.add_argument("--optimizer", default="auto", choices=["auto", "AdamW", "SGD"])
    parser.add_argument("--lr0", type=float, default=0.01,
                        help="Initial learning rate; use an explicit optimizer to honor this")
    parser.add_argument("--warmup-epochs", type=float, default=3.0)
    parser.add_argument("--mosaic", type=float, default=1.0)
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()
    if min(args.epochs, args.imgsz, args.batch, args.patience, args.nms_time_limit) <= 0:
        parser.error("epochs, imgsz, batch, patience and nms-time-limit must be positive")
    if args.lr0 <= 0 or args.warmup_epochs < 0 or not 0 <= args.mosaic <= 1:
        parser.error("lr0 must be positive, warmup-epochs nonnegative and mosaic between 0 and 1")
    try:
        import yaml
        config = yaml.safe_load(args.data.read_text())
        if config.get("names") != {0: "plastic_bottle", 1: "aluminum_can"}:
            raise ValueError("Expected class 0 plastic_bottle and class 1 aluminum_can")
        report = json.loads(args.data.with_name("report.json").read_text())
        if not report.get("training_ready"):
            raise ValueError("Dataset is not ready: " + "; ".join(report.get("blockers", [])))
        print(json.dumps(report["counts"], indent=2))
    except (OSError, ValueError, AttributeError) as error:
        parser.error(str(error))
    if args.check_only:
        print("Preparation report passes. No training started.")
        return
    from ultralytics import YOLO
    from ultralytics.utils import nms
    model = YOLO(args.model)
    original_nms = nms.non_max_suppression
    # The pinned Ultralytics default can time out before processing a complete
    # validation batch on MPS. This changes the time allowance, not thresholds.
    nms.non_max_suppression = partial(original_nms, max_time_img=args.nms_time_limit)
    try:
        model.train(data=str(args.data.resolve()), epochs=args.epochs, imgsz=args.imgsz,
                    batch=args.batch, device=args.device, project=str(Path("runs/detect").resolve()),
                    name=args.name, seed=42, deterministic=True, workers=0, exist_ok=False,
                    patience=args.patience, optimizer=args.optimizer, lr0=args.lr0,
                    warmup_epochs=args.warmup_epochs, mosaic=args.mosaic)
    finally:
        nms.non_max_suppression = original_nms
    print(f"Candidate training completed: {model.trainer.save_dir}")
    print("Evaluate on held-out machine-camera images before replacing deployed weights.")


if __name__ == "__main__":
    main()
