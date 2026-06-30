import os
import shutil
from pathlib import Path

# Source datasets
PLASTIC_DATASET = Path("plastic_bottle_dataset")
CAN_DATASET = Path("aluminum_can_dataset")

# Final merged dataset
OUTPUT_DATASET = Path("ecorefill_dataset")

# Final class IDs
# 0 = plastic_bottle
# 1 = aluminum_can

SPLITS = ["train", "valid", "test"]


def make_dirs():
    for split in SPLITS:
        (OUTPUT_DATASET / split / "images").mkdir(parents=True, exist_ok=True)
        (OUTPUT_DATASET / split / "labels").mkdir(parents=True, exist_ok=True)


def copy_dataset(source_dataset, new_class_id, prefix):
    for split in SPLITS:
        image_dir = source_dataset / split / "images"
        label_dir = source_dataset / split / "labels"

        if not image_dir.exists():
            print(f"Skipping missing folder: {image_dir}")
            continue

        for image_path in image_dir.iterdir():
            if image_path.suffix.lower() not in [".jpg", ".jpeg", ".png"]:
                continue

            new_image_name = f"{prefix}_{image_path.name}"
            new_label_name = f"{Path(new_image_name).stem}.txt"

            output_image_path = OUTPUT_DATASET / split / "images" / new_image_name
            output_label_path = OUTPUT_DATASET / split / "labels" / new_label_name

            shutil.copy(image_path, output_image_path)

            old_label_path = label_dir / f"{image_path.stem}.txt"

            if old_label_path.exists():
                with open(old_label_path, "r") as old_file:
                    lines = old_file.readlines()

                new_lines = []

                for line in lines:
                    parts = line.strip().split()

                    if len(parts) >= 5:
                        # Replace old class ID with our new class ID
                        parts[0] = str(new_class_id)
                        new_lines.append(" ".join(parts) + "\n")

                with open(output_label_path, "w") as new_file:
                    new_file.writelines(new_lines)
            else:
                # Create empty label file if no label exists
                output_label_path.touch()


def create_yaml():
    yaml_content = """path: ./ecorefill_dataset
train: train/images
val: valid/images
test: test/images

names:
  0: plastic_bottle
  1: aluminum_can
"""

    with open(OUTPUT_DATASET / "data.yaml", "w") as file:
        file.write(yaml_content)


make_dirs()

copy_dataset(
    source_dataset=PLASTIC_DATASET,
    new_class_id=0,
    prefix="plastic"
)

copy_dataset(
    source_dataset=CAN_DATASET,
    new_class_id=1,
    prefix="can"
)

create_yaml()

print("Done merging datasets.")
print("Final dataset created at: ecorefill_dataset")
print("Classes:")
print("0 = plastic_bottle")
print("1 = aluminum_can")