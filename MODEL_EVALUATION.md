# Bottle and can evaluation — September 5, 2026

## September 9 machine-camera report

Two actual aluminum cans appeared in scan history as `plastic_bottle`, at
53% (rejected) and 66% (accepted). The bottle acceptance threshold is now
75%; the can threshold remains 65%. This rejects the reported borderline
bottle predictions rather than sending them to the bottle gate. It does not
correct their predicted labels or prevent confident misclassifications, and
may reject more valid bottles. The model checkpoint is unchanged.

Decision/routing tests replay those confidence values and check the 95%
bottle shown in the same report. They do not run image inference. The saved
416 evaluation reports contain only aggregate results and errors, so they
cannot establish the acceptance rate at the new bottle threshold. The
historical results below use the former 65% threshold for both materials.
Evaluate original machine-camera images of cans and bottles before claiming
an accuracy improvement or retraining the model.

### Follow-up: confident can misclassification

The September 9, 11:47:45 screenshot shows a can annotated as
`plastic_bottle 0.92`. The 75% bottle threshold cannot prevent this error.
The screenshot alone does not explain a rejection: this material prediction
would pass the current threshold, although optional visual inspection can
still reject it.

Local diagnostic inference reproduced the wrong class with the existing
checkpoint. The screenshot's camera view (pixels x=84:1364, y=68:1028) was
resized to 640 by 480 before prediction at candidate confidence 0.20:

- At inference size 416, the central can was labeled `plastic_bottle` at
  0.8976. A separate false `aluminum_can` detection covered the left wall
  at 0.3582.
- At size 640, the central can was still labeled `plastic_bottle`, at 0.4386;
  the strongest prediction was a background `plastic_bottle` at 0.5479.
  Changing size therefore did not correct recognition on this example.

This is an annotated screenshot, not the original camera frame. Its overlay
and resizing can affect inference; these results are diagnostic evidence,
not a clean evaluation or a reason to tune settings to this single image.

The checkpoint names are `{0: plastic_bottle, 1: aluminum_can}`, matching
the dataset configuration. Counting current training labels found 1,000
images containing bottle annotations and 68 containing can annotations
(1,271 bottle boxes and 71 can boxes). The imbalance is a possible
contributor, not a proven explanation; the local data count does not verify
the exact contents of the checkpoint's historical training run.

The configured Picamera2 `RGB888` output supplies BGR pixel order, matching
Ultralytics' NumPy input convention; the inference path needs no channel
swap. See the [Picamera2 manual](https://datasheets.raspberrypi.com/camera/picamera2-manual.pdf)
and [Ultralytics input documentation](https://docs.ultralytics.com/modes/predict/).

Next, collect original, unannotated `captured_item.jpg` files for several
physical cans and bottles in the machine across positions and lighting.
Use correctly labeled examples for fine-tuning, reserve separate physical
containers/capture sessions for evaluation, and validate both recognition
and routing before replacing the deployed checkpoint. No further runtime
settings or model weights were changed for this diagnostic.

## Original evaluation

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
