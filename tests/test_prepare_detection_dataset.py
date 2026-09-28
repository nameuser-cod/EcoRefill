"""Regression coverage for material labels, negative images and data leakage."""

import csv
import json
from pathlib import Path
import tempfile
import unittest

from PIL import Image

from prepare_detection_dataset import build_dataset, inventory, taco_review, parse_labels


class PreparationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.serial = 0

    def image(self, name):
        self.serial += 1
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (100, 80), (self.serial * 20, 0, 0)).save(path)
        return path

    def coco(self, categories_by_image):
        categories = ["Clear plastic bottle", "Drink can", "Glass bottle", "Food Can"]
        images, annotations = [], []
        for i, names in enumerate(categories_by_image):
            path = self.image(f"taco/{i}.png")
            images.append(dict(id=i, file_name=path.name, width=100, height=80))
            for name in names:
                annotations.append(dict(id=len(annotations), image_id=i,
                                        category_id=categories.index(name), bbox=[10, 20, 40, 40], iscrowd=0))
        root = self.root / "taco"
        (root / "annotations.json").write_text(json.dumps(dict(images=images, annotations=annotations,
            categories=[dict(id=i, name=name) for i, name in enumerate(categories)])))
        return root

    def manifest(self, rows, name="review.csv"):
        path = self.root / name
        with path.open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=["image", "label", "split", "group", "reviewed", "notes"])
            writer.writeheader()
            writer.writerows(rows)
        return f"reviewed={path}"

    def row(self, name, labels="", split="train", group=None):
        image = self.image(name)
        label = image.with_suffix(".txt")
        label.write_text(labels)
        return dict(image=str(image), label=str(label), split=split,
                    group=group or name, reviewed="yes", notes="Fixture verified material and all boxes")

    def test_coco_conversion_and_unverified_can_excludes_whole_image(self):
        taco = self.coco([["Clear plastic bottle"], ["Clear plastic bottle", "Drink can"], ["Glass bottle"], ["Food Can"]])
        report = build_dataset(self.root / "out", taco)
        self.assertEqual(report["counts"]["train"]["images"], 2)
        self.assertEqual(report["counts"]["train"]["plastic_bottle"], 1)
        self.assertEqual(report["counts"]["train"]["negative_images"], 1)
        self.assertEqual(len(report["skipped"]), 2)
        text = "".join(p.read_text() for p in (self.root / "out/train/labels").glob("*.txt"))
        self.assertEqual(text, "0 0.30000000 0.50000000 0.40000000 0.50000000\n")
        self.assertFalse(report["training_ready"])

    def test_verified_can_keeps_correct_class(self):
        taco = self.coco([["Drink can"]])
        review = self.root / "taco.csv"
        taco_review(taco / "annotations.json", review)
        with review.open() as handle:
            rows = list(csv.DictReader(handle))
        rows[0].update(decision="aluminum_can", evidence="Material verified from product specification")
        with review.open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)
        report = build_dataset(self.root / "out", taco, review)
        self.assertEqual(report["counts"]["train"]["aluminum_can"], 1)

    def test_coco_edge_boxes_clipped_and_reported(self):
        taco = self.coco([["Clear plastic bottle"]])
        path = taco / "annotations.json"
        data = json.loads(path.read_text())
        data["annotations"][0]["bbox"] = [-2, 20, 42, 40]
        path.write_text(json.dumps(data))
        report = build_dataset(self.root / "out", taco)
        self.assertEqual(report["clipped_taco_boxes"], 1)
        label = next((self.root / "out/train/labels").glob("*.txt")).read_text()
        self.assertEqual(label, "0 0.20000000 0.50000000 0.40000000 0.50000000\n")

    def test_taco_reused_annotation_id_is_scoped_to_image(self):
        taco = self.coco([["Drink can"], ["Drink can"]])
        path = taco / "annotations.json"
        data = json.loads(path.read_text())
        data["annotations"][1]["id"] = data["annotations"][0]["id"]
        path.write_text(json.dumps(data))
        review = self.root / "review.csv"
        self.assertEqual(taco_review(path, review), 2)
        with review.open() as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual({r["annotation_id"] for r in rows}, {"0:0", "1:0"})

    def test_unknown_categories_cannot_silently_become_background(self):
        taco = self.coco([["Clear plastic bottle"]])
        path = taco / "annotations.json"
        data = json.loads(path.read_text())
        data["categories"][0]["name"] = "generic bottle"
        path.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError, "Unknown TACO categories"):
            build_dataset(self.root / "out", taco)

    def test_can_review_requires_evidence(self):
        taco = self.coco([["Drink can"]])
        path = self.root / "review.csv"
        taco_review(taco / "annotations.json", path)
        with path.open() as handle:
            rows = list(csv.DictReader(handle))
        rows[0]["decision"] = "aluminum_can"
        with path.open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=rows[0])
            writer.writeheader()
            writer.writerows(rows)
        with self.assertRaisesRegex(ValueError, "needs material/inspection evidence"):
            build_dataset(self.root / "out", taco, path)

    def test_verified_negatives_and_both_classes_allow_training(self):
        rows = []
        for split in ("train", "val"):
            for i, labels in enumerate(("0 0.5 0.5 0.4 0.4", "1 0.5 0.5 0.4 0.4", "")):
                rows.append(self.row(f"{split}-{i}.png", labels, split))
        report = build_dataset(self.root / "out", manifests=[self.manifest(rows)])
        self.assertTrue(report["training_ready"])
        self.assertNotIn("test:", (self.root / "out/data.yaml").read_text())

    def test_missing_label_is_not_silently_negative(self):
        row = self.row("bottle.png")
        Path(row["label"]).unlink()
        with self.assertRaises(FileNotFoundError):
            build_dataset(self.root / "out", manifests=[self.manifest([row])])
        self.assertFalse((self.root / "out").exists())

    def test_duplicate_across_splits_rejected(self):
        row = self.row("same.png")
        duplicate = dict(row, split="val", group="different-group")
        with self.assertRaisesRegex(ValueError, "Duplicate image crosses splits"):
            build_dataset(self.root / "out", manifests=[self.manifest([row, duplicate])])

    def test_duplicate_within_split_deduplicated(self):
        row = self.row("same.png")
        report = build_dataset(self.root / "out", manifests=[self.manifest([row, row])])
        self.assertEqual(report["counts"]["train"]["images"], 1)
        self.assertEqual(report["skipped"][0]["reason"], "duplicate pixels")

    def test_conflicting_duplicate_annotations_rejected(self):
        row = self.row("same.png")
        label = self.root / "conflict.txt"
        label.write_text("1 0.5 0.5 0.4 0.4")
        with self.assertRaisesRegex(ValueError, "conflicting annotations"):
            build_dataset(self.root / "out", manifests=[self.manifest([row, dict(row, label=str(label))])])

    def test_same_container_cannot_cross_splits(self):
        rows = [self.row("a.png", group="can-1"), self.row("b.png", split="val", group="can-1")]
        with self.assertRaisesRegex(ValueError, "Group .* crosses splits"):
            build_dataset(self.root / "out", manifests=[self.manifest(rows)])

    def test_invalid_boxes_rejected(self):
        for label in ("2 0.5 0.5 0.4 0.4", "0 nan 0.5 0.4 0.4", "0 0.1 0.5 0.8 0.4", "0 0.5 0.5 0 0.4"):
            with self.subTest(label=label), self.assertRaises(ValueError):
                row = self.row("bad.png", label)
                build_dataset(self.root / "out", manifests=[self.manifest([row])])

    def test_existing_can_polygons_require_explicit_conversion_and_keep_class(self):
        label = self.root / "can.txt"
        label.write_text("1 0.2 0.2 0.6 0.2 0.6 0.8 0.2 0.8")
        with self.assertRaises(ValueError):
            parse_labels(label)
        self.assertEqual(parse_labels(label, allow_segments=True),
                         ["1 0.40000000 0.50000000 0.40000000 0.60000000"])

    def test_inventory_does_not_approve_folder_labels(self):
        self.image("plastic_bottles/one.png")
        review = self.root / "inventory.csv"
        self.assertEqual(inventory(self.root / "plastic_bottles", review), 1)
        with review.open() as handle:
            row = next(csv.DictReader(handle))
        self.assertEqual(row["reviewed"], "no")
        self.assertEqual(row["label"], "")

    def test_existing_output_not_overwritten(self):
        output = self.root / "out"
        output.mkdir()
        with self.assertRaisesRegex(ValueError, "Output already exists"):
            build_dataset(output)


if __name__ == "__main__":
    unittest.main()
