# Retraining EcoRefill with TACO and Waste Segregation

The machine continues to accept only `plastic_bottle` (0) and `aluminum_can`
(1). Preparation and training never replace `ecorefill-pi/models/ecorefill_best.pt`.
The existing `ecorefill_dataset` is preserved. New data lives in ignored
`datasets/` directories and candidate weights in `runs/`.

## Sources and material verification

- [TACO](https://github.com/pedropro/TACO) supplies COCO detection annotations.
  Use the directory containing `annotations.json` and `batch_*` image folders.
  [Kaggle mirror](https://www.kaggle.com/datasets/kneroma/tacotrashdataset).
- [Waste Segregation](https://www.kaggle.com/datasets/aashidutt3/waste-segregation-image-dataset)
  supplies classification images. Its page lists CC BY-NC-SA 4.0 and says no
  commercial use. Combining it with another dataset does not remove that restriction.
  TACO image rights must also be checked separately from its toolkit license.

`Drink can`, `Food Can`, and `metal cans` do not verify aluminum. Use actual
material information (for example, reliable product specifications or verified
physical samples). Appearance, model confidence, or a folder name is insufficient.
Leave uncertain cans out. Do not relabel all cans as aluminum to increase counts.

## Environment

Run commands from the project root. The existing environment is usable:

```sh
source yolo-env/bin/activate
```

On a new workstation, create a virtual environment and install
`requirements-training.txt`. It omits the Pi hardware packages. The training
version is pinned to the locally verified Ultralytics version.

## 1. Review TACO's ambiguous annotations

```sh
python prepare_detection_dataset.py taco-review \
  --annotations datasets/raw/taco/data/annotations.json \
  --output datasets/review/taco.csv
```

Each CSV row identifies an annotation, its image, original category and COCO
box `[left, top, width, height]`. Keep these identity fields intact.

The review `annotation_id` is `image_id:annotation_id`, because TACO reuses some
annotation IDs across different images.

Set the decision and evidence fields as follows:

| decision | Meaning |
| --- | --- |
| `skip` | Unknown; exclude the entire image, including any bottle in it. Default. |
| `aluminum_can` | Verified aluminum can. Record verification in `evidence`. |
| `plastic_bottle` | A reviewed correction to a plastic bottle. Explain in `evidence`. |
| `background` | Verified object outside the two accepted classes. Explain in `evidence`. |

The converter automatically maps `Clear plastic bottle` and `Other plastic bottle`
to class 0. This policy accepts plastic bottles generally; it does not certify PET
resin or drink-container suitability. Other known, non-target TACO categories
become background. Ambiguous categories (including unlabeled litter) require
review. Crowd annotations exclude the image. Review images for missing accepted
objects and label errors before training, including the automatically mapped ones.

All TACO images go to **train**. Validation and test examples come from separately
reviewed manifests below, so outdoor TACO metrics do not substitute for machine
performance. Review CSVs cannot be overwritten by the template command.

## 2. Annotate Waste Segregation and machine photos

```sh
python prepare_detection_dataset.py inventory \
  --images datasets/raw/waste/Dataset \
  --output datasets/review/waste.csv
```

The inventory does not infer bounding boxes or trust folder names. Select useful
real photos, remove slides/collages/mislabeled examples, and annotate **every**
accepted object using YOLO detection format in your annotation editor:

```text
0 0.50 0.50 0.30 0.70
1 0.40 0.50 0.20 0.40
```

These are examples, not labels to copy. Each line is `class x_center y_center
width height`, normalized to the image dimensions. Do not use the entire image
as the object box unless the object actually fills it.

For images verified to contain no accepted objects, create an **empty `.txt`
file**. A missing label file is an error, not a negative example. Images containing
unverified cans should remain unreviewed; do not mark them as negatives.

Fill the selected CSV rows:

- `image`: original image path (inventory fills this in).
- `label`: path to the reviewed YOLO `.txt` file. Relative paths resolve from the CSV.
- `split`: `train`, `val`, or `test`.
- `group`: a stable physical-container/capture-session ID. All views of the same
  object/session and its augmented copies must stay in one split. Use globally
  consistent IDs across manifests. For web images, group common source images
  and near duplicates together; do not assume the supplied split is leak-free.
- `reviewed`: `yes` only after checking all boxes, materials and image content.
- `notes`: describe review and aluminum verification where applicable.

Unreviewed rows are skipped. Collect varied cans and bottles, glass bottles,
steel cans, wrappers, hands, and empty-tray images from the actual camera.
Training images may be full frames or properly reannotated scan-region crops.
Evaluation images must be **original full frames**, without prediction overlays;
the evaluation script applies the production crop itself.

Create a separate inventory/manifest for machine photos in the same way. Hold
out separate physical objects/sessions for validation and test. Do not tune
thresholds or select checkpoints on the final test set.

## 3. Build a versioned dataset

The existing project can labels use segmentation polygons. To reuse the
user-confirmed aluminum examples, convert these explicitly to detection boxes
in a separate folder, preserving class IDs:

```sh
python prepare_detection_dataset.py convert-labels \
  --labels ecorefill_dataset/train/labels \
  --output datasets/review/existing_labels/train
```

Repeat for `valid` when needed. Import the images and converted labels through
a reviewed manifest. Keep original source groups and exclude duplicates shared
with training before choosing validation images. The original files are untouched.
The explicit conversion also clips normalized box-edge rounding errors of at
most 0.0001; larger out-of-bounds boxes still fail validation.

```sh
python prepare_detection_dataset.py build \
  --taco-root datasets/raw/taco/data \
  --taco-review datasets/review/taco.csv \
  --manifest waste=datasets/review/waste.csv \
  --manifest machine=datasets/review/machine.csv \
  --output datasets/ecorefill_v2
```

Omit the machine manifest until it exists. `merge_datasets.py` accepts the same
commands; the old all-labels-to-one-class merge has been removed.

Outputs: `data.yaml`, YOLO image/label folders, `report.json` with class/negative
counts and skipped-image reasons, and `provenance.json` with source/review records.
Existing destinations are refused; use a new version after changing reviews.
Invalid boxes, mismatched image dimensions, EXIF rotation, conflicting labels,
and cross-split groups/identical pixels fail the build. Pixel hashing catches
metadata-only copies but not resized, recompressed or near-duplicate images;
those still require source/group review. Normalize rotated images and reannotate
before import, rather than rotating pixels without their boxes.

COCO boxes extending beyond an image edge are clipped to their visible
intersection; the adjustment count is recorded in the report and provenance.
Boxes with no visible area are rejected. Reviewed YOLO boxes must already fit.

Partial builds are allowed for inspection. Training requires both classes and
negative images in **both train and val**. Review the counts for imbalance even
when this minimum passes; one example per class is not an adequate training set.
Do not edit prepared outputs after building: change reviews and rebuild instead.

## 4. Train a candidate

```sh
python train_ecorefill_model.py --data datasets/ecorefill_v2/data.yaml --check-only
python train_ecorefill_model.py --data datasets/ecorefill_v2/data.yaml \
  --model yolov8n.pt --epochs 50 --imgsz 416 --batch 8 --device cpu
```

Use `--device mps` for a supported Apple GPU or `--device 0` for CUDA. Start with
416 to match the current runtime. A different training resolution needs separate
runtime validation. Training produces a new run under `runs/detect/`; it never
copies weights into the machine. Importing training/merge modules has no side effects.
The default early-stopping patience is 10 epochs. The pinned Ultralytics NMS
time allowance is raised to 1 second per image to avoid incomplete validation
batches observed on this Mac's GPU; confidence/IoU thresholds are unchanged.

For a gentler fine-tune of the existing checkpoint, explicitly select the
optimizer so Ultralytics does not replace the requested learning rate:

```sh
python train_ecorefill_model.py --data datasets/ecorefill_v2/data.yaml \
  --model ecorefill-pi/models/ecorefill_best.pt --device mps \
  --epochs 20 --patience 5 --optimizer AdamW --lr0 0.0001 \
  --warmup-epochs 1 --mosaic 0 --name ecorefill_taco_waste_conservative
```

Always compare decisions at the actual acceptance thresholds: a high detection
mAP can coexist with poor acceptance when confidence scores or classes shift.

## 5. Compare actual material decisions

Create `datasets/review/machine_test.csv` with columns `image,expected,group`.
Expected values are `plastic_bottle`, `aluminum_can`, or `reject`. Each frame
should depict the intended single inserted item (or an empty tray). Use the
same held-out full frames for both models:

```sh
python evaluate_detection_model.py \
  --manifest datasets/review/machine_test.csv \
  --model baseline=ecorefill-pi/models/ecorefill_best.pt \
  --model candidate=runs/detect/ecorefill_taco_waste/weights/best.pt \
  --output runs/detection_comparison.json
```

Use the actual run directory printed by training. This executes the production
material-decision code with its scan crop, confidence and area thresholds, but
bypasses hardware, weight, visual inspection, sorting and rewards. It reports
wrong-material acceptances, false acceptances of rejected items, false rejections,
and a confusion matrix. Missing denominators produce null rates, not 0% errors.
Separately validate weight/inspection and physical sorting before deployment.
Do not claim improvement or install a candidate until these comparisons support it.

For a separate diagnostic on public dataset images, `--full-frame` disables the
machine crop. Such results cannot be reported as machine-camera accuracy.

## Software checks

```sh
python -m unittest discover -s tests -p 'test_prepare_detection_dataset.py' -v
```

Reference: [Ultralytics detection labels](https://docs.ultralytics.com/datasets/detect/)
and [training options](https://docs.ultralytics.com/modes/train/).
