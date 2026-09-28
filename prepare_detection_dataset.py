"""Prepare reviewed TACO/YOLO data for EcoRefill. See DATASET_TRAINING.md."""

import argparse
import csv
import hashlib
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
import shutil
import tempfile

NAMES = {0: "plastic_bottle", 1: "aluminum_can"}
SPLITS = ("train", "val", "test")
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
BOTTLES = {"Clear plastic bottle", "Other plastic bottle"}
REVIEW_CATEGORIES = {"Drink can", "Food Can", "Aerosol", "Unlabeled litter",
                     "Other plastic", "Scrap metal"}
BACKGROUND_CATEGORIES = {
    "Aluminium foil", "Battery", "Aluminium blister pack", "Carded blister pack",
    "Glass bottle", "Plastic bottle cap", "Metal bottle cap", "Broken glass",
    "Toilet tube", "Other carton", "Egg carton", "Drink carton", "Corrugated carton",
    "Meal carton", "Pizza box", "Paper cup", "Disposable plastic cup", "Foam cup",
    "Glass cup", "Other plastic cup", "Food waste", "Glass jar", "Plastic lid",
    "Metal lid", "Magazine paper", "Tissues", "Wrapping paper", "Normal paper",
    "Paper bag", "Plastified paper bag", "Plastic film", "Six pack rings",
    "Garbage bag", "Other plastic wrapper", "Single-use carrier bag",
    "Polypropylene bag", "Crisp packet", "Spread tub", "Tupperware",
    "Disposable food container", "Foam food container", "Other plastic container",
    "Plastic glooves", "Plastic utensils", "Pop tab", "Rope & strings", "Shoe",
    "Squeezable tube", "Plastic straw", "Paper straw", "Styrofoam piece", "Cigarette",
}


def write_csv(path, fields, rows):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path):
    with Path(path).open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def load_coco(path):
    data = json.loads(Path(path).read_text())
    categories = {c["id"]: c["name"] for c in data["categories"]}
    images = {i["id"]: i for i in data["images"]}
    if len(images) != len(data["images"]) or len(categories) != len(data["categories"]):
        raise ValueError("Duplicate COCO image/category IDs")
    annotations, seen = defaultdict(list), set()
    for obj in data["annotations"]:
        key = (obj["image_id"], obj["id"])
        if key in seen:
            raise ValueError("Duplicate COCO annotation ID within an image")
        # TACO reuses a few annotation IDs in different images.
        seen.add(key)
        if obj["category_id"] not in categories or obj["image_id"] not in images:
            raise ValueError("COCO annotation refers to unknown image/category")
        annotations[obj["image_id"]].append(obj)
    return categories, images, annotations


def taco_review(annotations, output):
    categories, images, by_image = load_coco(annotations)
    rows = []
    for image_id, objects in by_image.items():
        for obj in objects:
            category = categories[obj["category_id"]]
            if category in REVIEW_CATEGORIES:
                rows.append(dict(annotation_id=f"{image_id}:{obj['id']}", image=images[image_id]["file_name"],
                                 category=category, bbox=json.dumps(obj["bbox"]),
                                 decision="skip", evidence=""))
    write_csv(output, ["annotation_id", "image", "category", "bbox", "decision", "evidence"], rows)
    return len(rows)


def inventory(images, output):
    root = Path(images).resolve()
    if not root.is_dir():
        raise ValueError(f"Image directory does not exist: {root}")
    rows = [dict(image=str(p), label="", split="train", group="", reviewed="no", notes="")
            for p in sorted(root.rglob("*")) if p.suffix.lower() in IMAGE_SUFFIXES]
    if not rows:
        raise ValueError(f"No images found in {root}")
    write_csv(output, ["image", "label", "split", "group", "reviewed", "notes"], rows)
    return len(rows)


def validate_box(class_id, values):
    if class_id not in NAMES or len(values) != 4 or not all(math.isfinite(v) for v in values):
        raise ValueError("Expected class 0/1 and four finite YOLO box coordinates")
    x, y, w, h = values
    if not (0 <= x <= 1 and 0 <= y <= 1 and 0 < w <= 1 and 0 < h <= 1):
        raise ValueError(f"Invalid normalized box: {values}")
    if min(x - w / 2, y - h / 2) < -1e-6 or max(x + w / 2, y + h / 2) > 1 + 1e-6:
        raise ValueError(f"Box extends outside the image: {values}")
    return f"{class_id} " + " ".join(f"{v:.8f}" for v in values)


def parse_labels(path, allow_segments=False):
    lines = []
    for line in Path(path).read_text().splitlines():
        if not line.strip():
            continue
        parts = line.split()
        if parts[0] not in ("0", "1"):
            raise ValueError(f"{path}: expected class 0 or 1")
        values = [float(v) for v in parts[1:]]
        if allow_segments and len(values) >= 6 and len(values) % 2 == 0:
            if not all(math.isfinite(v) and 0 <= v <= 1 for v in values):
                raise ValueError(f"{path}: invalid normalized polygon")
            xs, ys = values[::2], values[1::2]
            values = [(min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2,
                      max(xs) - min(xs), max(ys) - min(ys)]
        elif len(parts) != 5:
            raise ValueError(f"{path}: expected two-class YOLO boxes, not polygons")
        if allow_segments and len(values) == 4 and all(math.isfinite(v) for v in values):
            x, y, w, h = values
            left, top, right, bottom = x - w / 2, y - h / 2, x + w / 2, y + h / 2
            # Existing Roboflow exports have sub-pixel edge rounding errors.
            if min(left, top) >= -1e-4 and max(right, bottom) <= 1 + 1e-4:
                left, top, right, bottom = max(0, left), max(0, top), min(1, right), min(1, bottom)
                values = [(left + right) / 2, (top + bottom) / 2, right - left, bottom - top]
        lines.append(validate_box(int(parts[0]), values))
    return sorted(set(lines))


def convert_labels(source, output):
    source, output = Path(source), Path(output)
    if output.exists():
        raise ValueError(f"Output exists: {output}")
    files = sorted(source.glob("*.txt"))
    if not files:
        raise ValueError(f"No YOLO label files in {source}")
    converted = {p.name: parse_labels(p, allow_segments=True) for p in files}
    output.mkdir(parents=True)
    for name, lines in converted.items():
        (output / name).write_text("\n".join(lines) + ("\n" if lines else ""))
    return len(converted)


def image_info(path):
    from PIL import Image
    with Image.open(path) as image:
        if image.getexif().get(274, 1) != 1:
            raise ValueError(f"{path}: normalize EXIF orientation and update boxes before import")
        image.load()
        size = image.size
        pixels = image.convert("RGB").tobytes()
    return size, hashlib.sha256(str(size).encode() + pixels).hexdigest()


def taco_records(root, review_path, skipped):
    root = Path(root).resolve()
    categories, images, by_image = load_coco(root / "annotations.json")
    unknown = set(categories.values()) - BOTTLES - REVIEW_CATEGORIES - BACKGROUND_CATEGORIES
    if unknown:
        raise ValueError(f"Unknown TACO categories need an explicit mapping: {sorted(unknown)}")
    reviews = {}
    lookup = {f"{i}:{a['id']}": (images[i]["file_name"], categories[a["category_id"]], a["bbox"])
              for i, objects in by_image.items() for a in objects}
    if review_path:
        for row in read_csv(review_path):
            key = row["annotation_id"]
            identity = (row["image"], row["category"], json.loads(row["bbox"]))
            if key in reviews or lookup.get(key) != identity:
                raise ValueError(f"Duplicate/stale TACO review: {key}")
            if row["decision"] not in {"skip", "background", *NAMES.values()}:
                raise ValueError(f"Unknown TACO decision: {row['decision']}")
            if row["decision"] != "skip" and not row["evidence"].strip():
                raise ValueError(f"TACO review {key} needs material/inspection evidence")
            reviews[key] = row
    for image_id, info in sorted(images.items()):
        objects = by_image[image_id]
        if not objects:
            skipped.append(dict(source="taco", image=info["file_name"], reason="no annotations"))
            continue
        lines, unresolved, evidence, clipped_boxes = [], False, [], 0
        for obj in objects:
            category = categories[obj["category_id"]]
            review = reviews.get(f"{image_id}:{obj['id']}")
            if review:
                decision = review["decision"]
                evidence.append(review)
            elif category in BOTTLES:
                decision = "plastic_bottle"
            elif category in REVIEW_CATEGORIES:
                decision = "skip"
            else:
                decision = "background"
            if decision == "skip" or obj.get("iscrowd", 0):
                unresolved = True
            elif decision in NAMES.values():
                width, height = info["width"], info["height"]
                if width <= 0 or height <= 0:
                    raise ValueError(f"Invalid dimensions: {info['file_name']}")
                x, y, w, h = obj["bbox"]
                if not all(math.isfinite(v) for v in (x, y, w, h)) or w <= 0 or h <= 0:
                    raise ValueError(f"Invalid COCO box in {info['file_name']}: {obj['bbox']}")
                # Some official TACO boxes extend slightly beyond image edges.
                # Preserve their visible intersection and record the adjustment.
                left, top = max(0, x), max(0, y)
                right, bottom = min(width, x + w), min(height, y + h)
                clipped_boxes += int((left, top, right, bottom) != (x, y, x + w, y + h))
                lines.append(validate_box(0 if decision == "plastic_bottle" else 1,
                             [(left + right) / (2 * width), (top + bottom) / (2 * height),
                              (right - left) / width, (bottom - top) / height]))
        if unresolved:
            skipped.append(dict(source="taco", image=info["file_name"], reason="unverified object/material or crowd"))
            continue
        path = (root / info["file_name"]).resolve()
        if root not in path.parents:
            raise ValueError("COCO image path escapes dataset directory")
        yield dict(source="taco", image=path, labels=sorted(set(lines)), split="train",
                   group=f"taco:{image_id}", expected_size=(info["width"], info["height"]),
                   clipped_boxes=clipped_boxes, review=evidence)


def manifest_records(spec, skipped):
    source, separator, filename = spec.partition("=")
    if not separator or not source or source == "taco":
        raise ValueError("Use --manifest source_name=/path/to/review.csv; name cannot be taco")
    manifest = Path(filename).resolve()
    for row in read_csv(manifest):
        if row["reviewed"].strip().lower() != "yes":
            skipped.append(dict(source=source, image=row["image"], reason="not reviewed"))
            continue
        if row["split"] not in SPLITS or not row["group"].strip() or not row["notes"].strip():
            raise ValueError(f"{manifest}: reviewed rows need split, group and review notes")
        if not row["label"].strip():
            raise ValueError(f"{row['image']}: provide a label file; verified negatives need an existing empty file")
        image = (manifest.parent / row["image"]).resolve()
        label = (manifest.parent / row["label"]).resolve()
        yield dict(source=source, image=image, labels=parse_labels(label), split=row["split"],
                   group=row["group"].strip(), review=dict(row))


def build_dataset(output, taco_root=None, taco_review_path=None, manifests=()):
    output = Path(output).resolve()
    if output.exists():
        raise ValueError(f"Output already exists; choose a new version: {output}")
    if not taco_root and not manifests:
        raise ValueError("Provide --taco-root and/or --manifest")
    if taco_review_path and not taco_root:
        raise ValueError("--taco-review requires --taco-root")
    skipped, records = [], []
    if taco_root:
        records.extend(taco_records(taco_root, taco_review_path, skipped))
    for spec in manifests:
        records.extend(manifest_records(spec, skipped))
    unique, hashes, groups = [], {}, {}
    counts = {s: Counter(images=0, negative_images=0, plastic_bottle=0, aluminum_can=0) for s in SPLITS}
    source_counts = Counter()
    for record in records:
        path = record["image"]
        if path.suffix.lower() not in IMAGE_SUFFIXES:
            raise ValueError(f"Unsupported image: {path}")
        size, digest = image_info(path)
        if record.get("expected_size", size) != size:
            raise ValueError(f"COCO dimensions do not match {path}")
        split, group = record["split"], record["group"]
        if group in groups and groups[group] != split:
            raise ValueError(f"Group {group!r} crosses splits; keep each container/session together")
        groups[group] = split
        if digest in hashes:
            previous = hashes[digest]
            if previous["split"] != split:
                raise ValueError(f"Duplicate image crosses splits: {path} and {previous['image']}")
            if previous["labels"] != record["labels"]:
                raise ValueError(f"Duplicate image has conflicting annotations: {path}")
            skipped.append(dict(source=record["source"], image=str(path), reason="duplicate pixels"))
            continue
        hashes[digest] = record
        record["sha256_pixels"] = digest
        unique.append(record)
        counts[split]["images"] += 1
        counts[split]["negative_images"] += int(not record["labels"])
        counts[split].update(NAMES[int(line.split()[0])] for line in record["labels"])
        source_counts[record["source"]] += 1
    if not unique:
        raise ValueError("No usable reviewed images; no dataset created")
    blockers = [f"{s}: missing {name} boxes" for s in ("train", "val") for name in NAMES.values() if not counts[s][name]]
    blockers += [f"{s}: missing verified negative images" for s in ("train", "val") if not counts[s]["negative_images"]]
    warnings = []
    for split in ("train", "val"):
        positives = [counts[split][name] for name in NAMES.values()]
        if min(positives) > 0 and max(positives) / min(positives) > 5:
            warnings.append(f"{split}: more than 5:1 class imbalance; inspect counts before training")
    report = dict(classes=NAMES, counts=counts, source_images=source_counts, warnings=warnings,
                  clipped_taco_boxes=sum(r.get("clipped_boxes", 0) for r in unique),
                  training_ready=not blockers, blockers=blockers, skipped=skipped,
                  limitations=["Exact pixel checks do not detect resized/near-duplicate images.",
                               "Review groups to prevent physical-container/session leakage.",
                               "Readiness checks do not measure model accuracy."])
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".ecorefill-build-", dir=output.parent) as temp:
        stage = Path(temp) / "dataset"
        for split in SPLITS:
            for kind in ("images", "labels"):
                (stage / split / kind).mkdir(parents=True, exist_ok=True)
        provenance = []
        for record in unique:
            split, image = record["split"], record["image"]
            stem = record["sha256_pixels"]
            name = stem + image.suffix.lower()
            shutil.copyfile(image, stage / split / "images" / name)
            labels = record["labels"]
            (stage / split / "labels" / f"{stem}.txt").write_text("\n".join(labels) + ("\n" if labels else ""))
            provenance.append(dict(record, image=str(image), output_image=f"{split}/images/{name}"))
        config = f"path: {json.dumps(str(output))}\ntrain: train/images\nval: val/images\n"
        if counts["test"]["images"]:
            config += "test: test/images\n"
        config += "names:\n  0: plastic_bottle\n  1: aluminum_can\n"
        (stage / "data.yaml").write_text(config)
        (stage / "report.json").write_text(json.dumps(report, indent=2) + "\n")
        (stage / "provenance.json").write_text(json.dumps(provenance, indent=2) + "\n")
        if output.exists():
            raise ValueError(f"Output appeared during build: {output}")
        stage.rename(output)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    review = sub.add_parser("taco-review")
    review.add_argument("--annotations", type=Path, required=True)
    review.add_argument("--output", type=Path, required=True)
    inv = sub.add_parser("inventory")
    inv.add_argument("--images", type=Path, required=True)
    inv.add_argument("--output", type=Path, required=True)
    convert = sub.add_parser("convert-labels", help="Convert existing two-class YOLO polygons to boxes")
    convert.add_argument("--labels", type=Path, required=True)
    convert.add_argument("--output", type=Path, required=True)
    build = sub.add_parser("build")
    build.add_argument("--taco-root", type=Path)
    build.add_argument("--taco-review", type=Path)
    build.add_argument("--manifest", action="append", default=[], metavar="SOURCE=CSV")
    build.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == "taco-review":
            print(f"Wrote {taco_review(args.annotations, args.output)} review rows to {args.output}")
        elif args.command == "inventory":
            print(f"Wrote {inventory(args.images, args.output)} image rows to {args.output}")
        elif args.command == "convert-labels":
            print(f"Converted {convert_labels(args.labels, args.output)} label files to {args.output}")
        else:
            report = build_dataset(args.output, args.taco_root, args.taco_review, args.manifest)
            print(json.dumps({k: v for k, v in report.items() if k != "skipped"}, indent=2))
            print(f"Skipped {len(report['skipped'])} records. Details: {args.output / 'report.json'}")
    except (ValueError, OSError, KeyError, TypeError) as error:
        parser.exit(2, f"Dataset preparation failed: {error}\n")


if __name__ == "__main__":
    main()
