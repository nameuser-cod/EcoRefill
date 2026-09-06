"""Train a separate appearance classifier from manually reviewed tray crops."""

import argparse
import hashlib
from pathlib import Path


LABELS = {"visually_acceptable", "visibly_dirty"}
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def validate_dataset(root):
    seen = {}
    for split in ("train", "val", "test"):
        directory = root / split
        if not directory.is_dir() or {
            path.name for path in directory.iterdir() if path.is_dir()
        } != LABELS:
            raise ValueError(f"{directory} must contain exactly {sorted(LABELS)}")
        for label in sorted(LABELS):
            images = [path for path in (directory / label).rglob("*")
                      if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES]
            if not images:
                raise ValueError(f"No images in {directory / label}")
            for path in images:
                digest = hashlib.sha256(path.read_bytes()).hexdigest()
                if digest in seen and seen[digest] != (split, label):
                    raise ValueError(f"Duplicate image across splits or labels: {path}")
                seen[digest] = (split, label)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--epochs", type=int, default=50)
    parser.add_argument("--imgsz", type=int, default=224)
    parser.add_argument("--model", default="yolov8n-cls.pt")
    parser.add_argument("--device", default="cpu")
    args = parser.parse_args()
    validate_dataset(args.data)

    from ultralytics import YOLO

    model = YOLO(args.model)
    if model.task != "classify":
        parser.error("Use a classification checkpoint, such as yolov8n-cls.pt")
    model.train(data=str(args.data.resolve()), epochs=args.epochs,
                imgsz=args.imgsz, device=args.device,
                project="runs/classify", name="ecorefill_cleanliness")
    best = Path(model.trainer.best)
    print(f"Candidate checkpoint: {best}")
    print("Held-out test results (not used for training):")
    YOLO(str(best)).val(data=str(args.data.resolve()), split="test", device=args.device)
    print("Review dirty-container false acceptances before deploying this checkpoint.")


if __name__ == "__main__":
    main()
