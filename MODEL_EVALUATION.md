# Bottle and can evaluation — September 5, 2026

## September 28, 2026 — TACO and Waste Segregation candidate

The user confirmed that the existing dataset's aluminum-can labels are verified
aluminum. Those examples are reused without mapping generic public-dataset can
labels to aluminum. Existing can polygons were explicitly converted into boxes;
subpixel export rounding at image edges was clipped. Original data and deployed
weights are preserved.

The first version is a curated subset, not the entirety of either new dataset:

| Split | Bottle images | Can images | Negative images | Total images |
| --- | ---: | ---: | ---: | ---: |
| Train | 151 | 68 | 77 | 296 |
| Validation | 34 | 17 | 11 | 62 |

There are 189 bottle boxes and 71 can boxes in training; validation has 40 bottle
boxes and 17 can boxes. Source totals across the splits are 255 existing project
images, 71 TACO images, and 32 Waste Segregation images.

TACO contributes 71 usable images from an initial 129-image archive batch.
The other 58 images are excluded because they include unverified can/ambiguous
annotations. The 32 Waste Segregation examples were visually reviewed as food
or produce scenes without visible accepted objects, with deliberate empty
negative labels. Graphics, mixed packaging and apparent duplicate scenes were
excluded. This selection does not cover the full range of rejected materials.

Existing bottle training images were sampled deterministically (seed 42) to
reduce the original imbalance while retaining the 68 can images. Two validation
candidates were excluded for duplicate pixels or source-name overlap with
training. This does not establish that every near-duplicate or physical object
has been separated across the original public dataset.

Dataset recipe and individual review/source records are in the local ignored
`datasets/review/candidate_v2_notes.json`, `datasets/review/existing_verified.csv`,
`datasets/review/waste_selected.csv`, and `datasets/ecorefill_v2/provenance.json`.
The new [training guide](DATASET_TRAINING.md) documents reproducible conversion,
training, and comparison commands.

The deployed baseline made all 62 expected material decisions correctly on this
public validation subset (34 bottles, 17 cans, 11 food-scene negatives), recorded
in `runs/detection_baseline_v2_public.json`. This diagnostic uses full public
images without the machine scan crop, with the existing material confidence
and area thresholds. It bypasses weight/visual inspection. It is **not** a
machine-camera accuracy result or an independent final test: these validation
examples participate in candidate checkpoint selection, and the existing
checkpoint's historical data provenance has not been fully reconstructed.

Two candidates were trained from the existing checkpoint at image size 416,
batch size 8 and seed 42 on the Mac GPU. The default-optimizer run stopped after
11 epochs and selected epoch 1. It regressed to 16/34 correct bottle acceptances,
with 16 bottle rejections and two bottles incorrectly accepted as cans, despite
rejecting every glass scene. It was not deployed.

The conservative run used AdamW, learning rate 0.0001, one warmup epoch, no mosaic,
and patience 5. It also stopped after 11 epochs, selecting epoch 6. Its validation
box metrics recorded for epoch 6 were mAP50 0.99202 and mAP50–95 0.95503; these are
bounding-box metrics, **not acceptance accuracy**.

Final material-decision comparisons at the unchanged acceptance thresholds:

| Public-image check | Existing model | Conservative candidate |
| --- | ---: | ---: |
| Correct bottle acceptance | 34/34 | 29/34 |
| Correct can acceptance | 17/17 | 17/17 |
| Correct food-scene rejection | 11/11 | 11/11 |
| Correct glass-scene rejection | 23/26 | 26/26 |
| Wrong-material acceptances on the validation subset | 0 | 0 |

The glass check uses 26 TACO scenes outside the training batch. An initial
29-scene selection was reviewed before inference; three ambiguous mixed scenes
were excluded. Some scenes contain small objects or multiple views of the same
physical bottle, so these image counts are not independent material trials.
The scenes were excluded from training, but comparisons were repeated across
candidates; this is exploratory evaluation, not an untouched final machine test.

**Decision: retain the deployed checkpoint.** The new candidate improves glass
rejection on these examples but rejects five valid bottle images. The user has
no original machine-camera photos available yet, so neither candidate establishes
that the previously reported can-as-bottle problem is fixed. No runtime thresholds,
reward rules, hardware code, or deployed weights were changed.

Local artifacts:

- Conservative candidate: `runs/detect/ecorefill_taco_waste_conservative/weights/best.pt`
- First candidate: `runs/detect/ecorefill_taco_waste_v2/weights/best.pt`
- Final validation comparison: `runs/detection_comparison_conservative_public.json`
- Final glass comparison: `runs/detection_comparison_conservative_glass.json`
- Complete source inventory: `datasets/review/download_report.json` (1,500 TACO
  images and 15,366 Waste Segregation image files downloaded and extracted).

The deployed checkpoint's SHA-256 remained
`a7d59d7aacd1c84c4400354aa37bc98755ecb68725f3efa98897ce03f8810ac2`.
All 16 preparation regression tests and 12 material-decision tests passed.
The converter was additionally exercised on actual TACO images, and both final
models were run through the production material-decision code with the scan crop
disabled for these public-image diagnostics. Original full-frame machine photos
remain the next required evidence before deployment.

## September 9 machine-camera report

### 15:41 preview and uncertain-material handling

The latest screenshot shows a can labeled `plastic_bottle 0.69`. This is
below the existing 75% bottle acceptance threshold, so it is rejected.
The preview now draws the selected detection using the acceptance threshold:
this prediction displays **Uncertain material**, and its returned material is
`unknown` so new history records do not identify it as plastic. Raw model
predictions remain in diagnostic logs. The yellow scan-area border and title
are removed; the center crop still applies to inference and motion.

Regression tests replay the reported 69% prediction and check rejection,
zero points, unknown material, and the preview label. They also check that
the scan border is absent and the clean input and crop coordinates are
preserved. These are software behavior tests, not an image accuracy result.
The checkpoint is unchanged: recognizing this can correctly and addressing
confident wrong labels still require original machine-camera training and
independent evaluation images. An annotated screenshot is insufficient to
validate that model improvement.

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

### Center scan region follow-up

At the user's request, motion and inference now share the center-tray crop
`DETECTION_REGION = (0.33, 0.04, 0.65, 0.96)`, or x=211:416, y=19:461 at
640 by 480. This excludes the left wall and objects to the right from model
input. Detection overlays show the region on the full camera view, and
inspection receives coordinates translated back to that full view.

The existing model and acceptance thresholds were retained. Diagnostic
checks through `verify_item` on the supplied screenshots produced:

| Screenshot | Actual center item | Prediction using scan crop | Decision |
| --- | --- | --- | --- |
| September 9, 11:47:45 | Silver aluminum can | `plastic_bottle`, 0.8301 | Wrongly accepted as bottle |
| September 9, 11:54:55 | Green aluminum can | `aluminum_can`, 0.8533 | Correctly accepted as can |

For the second screenshot, camera-view boundaries were estimated at
x=505:1265, y=333:903 in its 1996-by-1248 displayed version, scaled to the
source screenshot dimensions, then resized to 640 by 480. Both inputs
contain existing annotations. Outputs are in the ignored
`runs/scan_region_check/` directory and may show old screenshot annotations
outside the new yellow box; those pixels were not supplied to the model.

These two checks demonstrate mixed results, not an accuracy estimate. The
region prevents outside-background detections but does not fix the silver
can's wrong class. Cropping changes the model input, so the historical
full-frame evaluation below does not measure this configuration.

All 93 machine tests passed, including scan isolation for motion and
inference, full-frame inspection coordinates, clean-input preservation,
empty-scan rejection, and existing routing tests. Physical camera alignment,
motion sensitivity, and material accuracy still need validation on the Pi.

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
