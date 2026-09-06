# Camera inspection without a load cell

The existing material detector stays in place. `visual_inspection.py` adds
optional approximate size measurement and a **separate** trained appearance
classifier before sorting and awarding points. No existing checkpoint has
been retrained. Weight is recorded as `not_installed` and never simulated.

## Start by collecting real examples

Run from the `ecorefill-pi` directory on the Pi. Copy
`inspection.example.json` to `inspection.local.json`, and set
`capture_directory` to `inspection_samples`. Leave `mode` as `off` and both
checks disabled. Start the existing machine service with this environment:

```sh
export ECOREFILL_INSPECTION_CONFIG="$PWD/inspection.local.json"
python3 machine_flow.py
```

If you normally use a service manager, set the same environment variable in
that service instead of starting a second process. Paths inside the JSON are
relative to the JSON file. Copy `visual_inspection.py` together with the
updated `machine_flow.py` when transferring this change to the Pi.

Each scan with one confidently recognized material saves a square, padded
container crop and JSON metadata. Captures are **unlabeled**; material
predictions cannot label cleanliness. In off mode, the original acceptance
rules still apply: collection does not reject dirt. Use supervised test items.
Turn capture off by setting `capture_directory` back to `null` when finished.

Keep the camera, focus, lighting, resolution, and upright container position
fixed. Review crops for dirt, food residue, visible liquid, or foreign objects.
Define what counts as unacceptable before labeling. Include ordinary labels,
glare, dents, and different colors among acceptable examples so the model
does not simply learn those as dirt. Exclude ambiguous or obscured examples
from the two training labels, but retain them for separate challenge testing.

Arrange manually labeled crops like this on your training computer:

```text
cleanliness_dataset/
  train/visually_acceptable/
  train/visibly_dirty/
  val/visually_acceptable/
  val/visibly_dirty/
  test/visually_acceptable/
  test/visibly_dirty/
```

Assign each physical container and recording session to only one split,
including clean/dirty versions of the same container. The script checks exact
file duplicates, but cannot detect different photos of the same container.
Use diverse real examples; a fixed image count cannot guarantee accuracy.

From the repository root, in an environment with Ultralytics installed:

```sh
python3 train_cleanliness_model.py --data cleanliness_dataset --device cpu
```

Training may download the initial classification checkpoint. It creates a
candidate checkpoint under `runs/classify/`, evaluates it on the held-out test
split, and prints its path. It does not replace the material model or deploy
anything. Training can use a separate computer; inference runs on the Pi.

Copy the validated candidate to `ecorefill-pi/models/cleanliness_best.pt`.
Set `cleanliness.enabled` to `true` and `mode` to `observe`. This records
predictions without changing acceptance. Test dirty false acceptances,
acceptable false rejections, and uncertain views with the actual machine.
The sample confidence of 0.9 is a starting setting, **not** a measured accuracy
or a guarantee; select the threshold on validation examples, then evaluate
the final threshold on untouched test containers. Measure inference delay
on your Pi before relying on its throughput.

## Calibrate approximate size for your upright tray

Size is measured in the original 640 × 480 camera frame, not the detector's
resized inference image. A YOLO box is approximate, and one flat scale factor
cannot correct every perspective/depth error in a three-dimensional bottle.

1. Fix the camera and mark an upright inspection position so users cannot
   move containers closer to the lens. Keep the whole object visible.
2. Measure reference containers with a ruler and record their YOLO box widths
   and heights (`x2 - x1`, `y2 - y1`) from the captured JSON metadata.
3. Estimate `mm_per_pixel_x = actual_width_mm / box_width_px` and
   `mm_per_pixel_y = actual_height_mm / box_height_px`. Check several reference
   containers. Correct camera distortion or improve positioning first if the
   scale changes substantially across the allowed area.
4. Set `inspection_region_px` to the usable area in the original camera frame.
   The entire detected box must fit inside it. This image region does not
   verify distance from the camera; the physical guide must do that.
5. Add non-overlapping profiles for each accepted class using **measured**
   limits. Each profile has `name`, `width_mm: [minimum, maximum]`, and
   `height_mm: [minimum, maximum]`. Width is horizontal, height is vertical.
   Empty profiles and null calibration values intentionally cannot pass.
6. Enable `size`, use `observe`, and compare reported dimensions with ruler
   measurements on other containers before choosing final limits. Recalibrate
   after moving the camera or changing its resolution, focus, or crop.

These groups describe exterior dimensions, not verified capacity or an exact
empty weight. Crushed or tilted containers can fall outside their size group.

## Enable rejection after validation

Set `mode` to `enforce` and restart the process. **Every enabled check must
pass.** You can enable cleanliness before size calibration is ready, or vice
versa. Missing models/calibration, uncertain results, partial views, multiple
meaningful detections, unsupported sizes, or overlapping size profiles reject
the item with zero points. Enforce mode with no checks enabled also rejects.
Off mode and observe mode retain the existing material acceptance behavior.

Reports and rejection reasons are saved in local session logs and recycling
records. No new cloud service or load-cell dependency is required. The code
only rejects multiple objects that the detector actually finds; it cannot
guarantee detection of stacked or hidden items.

A pass means acceptable **visible appearance**, not verified cleanliness or
emptiness. An opaque can, a label, or the back of a bottle can hide contents.
The future weight check will help detect excess mass but will also need
physical calibration and tested limits. Never use camera confidence as a
substitute weight reading.

References: [Ultralytics classification](https://docs.ultralytics.com/tasks/classify/)
and [OpenCV calibration](https://docs.opencv.org/4.x/dc/dbb/tutorial_py_calibration.html).
