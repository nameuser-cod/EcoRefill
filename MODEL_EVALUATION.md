# Bottle and can evaluation — September 5, 2026

The existing checkpoint was trained at image size 416, but the machine used
640 for inference. Matching inference to 416 improved correct acceptance on
the available validation images. The checkpoint was not retrained or replaced.

| Dataset | Previous size 640 | Selected size 416 |
| --- | --- | --- |
| Validation, all eligible images | 232/259 (89.6%) | 246/259 (95.0%) |
| Validation, plastic bottles | 217/242 (89.7%) | 229/242 (94.6%) |
| Validation, aluminum cans | 15/17 (88.2%) | 17/17 (100%) |
| Test, all images | 12/13 (92.3%) | 13/13 (100%) |

These percentages measure **correct acceptance of valid-object images**, not
overall machine accuracy. Each image contains one material class, sometimes
with multiple objects. Success means the machine accepts that material class;
rejecting a valid image counts as an error. This does not measure bounding-box
quality or counting accuracy.

## Method

- Evaluated `ecorefill-pi/models/ecorefill_best.pt` with Ultralytics 8.4.83,
  PyTorch 2.8.0, Python 3.9.6, CPU, and OpenCV image loading.
- Executed the actual `verify_item` and `normalize_class_name` functions and
  their constants, extracted using Python's AST. Hardware, Firebase, and the
  machine loop were not initialized. Annotated-image writes were suppressed.
- Kept candidate confidence 0.20, acceptance confidence 0.65, and minimum
  bounding-box area ratio 0.05 unchanged.
- Excluded validation images matching training images or earlier validation
  images by SHA-256 content or source filename before `.rf.`. This removed six
  of 265 validation images. No test images matched earlier splits by these checks.
- Compared the existing 640 setting with the checkpoint's original 416 setting
  on validation data. Selected 416 from validation results, then checked the
  actual updated function on the test split. The original configuration had
  also been evaluated on that test split as a baseline.
- Python syntax validation and `git diff --check` passed.

Detailed local results are in the ignored `runs/detection_baseline/` directory:
`machine_decisions.json`, `validation_416.json`, and `test_416.json`.

## Limits and next measurement

The dataset has no negative images, so it cannot measure acceptance of glass,
steel, hands, wrappers, or an empty chamber. The test split contains only three
bottle and ten can images. Dataset provenance, visually similar images with
different filenames, and separation by physical container or recording session
are not verified. These results do not establish 90% real-world machine accuracy.

To establish that target, collect an independent machine-camera test set with
both valid and invalid items across expected operating conditions. Record
correct classifications, false acceptances, and false rejections separately
for each material. Keep that set out of training and threshold selection.

The change is local to the repository. Copy the updated `machine_flow.py` to
the Raspberry Pi and restart the machine service to use the new inference
size. Re-evaluate the size when replacing the checkpoint.
