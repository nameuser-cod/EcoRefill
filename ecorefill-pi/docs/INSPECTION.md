# Camera inspection

The existing material detector stays in place. `machine/visual_inspection.py` adds
optional approximate size measurement and a **separate** trained appearance
classifier before sorting and awarding points. No existing checkpoint has
been retrained. This module leaves weight `not_checked`; the controller then
applies the separate [HX711 weight check](WEIGHT_SENSOR.md) to items
that passed material and visual checks when `WEIGHT_SENSOR_ENABLED=true`.
Weighing is temporarily disabled by default and recorded as `disabled`.
Weight is never simulated.

## Start by collecting real examples

Run from the `ecorefill-pi` directory on the Pi. Copy
`config/inspection.example.json` to `inspection.local.json`, and set
`capture_directory` to `inspection_samples`. Leave `mode` as `off` and both
checks disabled. Start the existing machine service with this environment:

```sh
export ECOREFILL_INSPECTION_CONFIG="$PWD/inspection.local.json"
python3 machine_flow.py
```

If you normally use a service manager, set the same environment variable in
that service instead of starting a second process. Paths inside the JSON are
relative to the JSON file. Copy `machine_flow.py` and the complete `machine/`
directory when transferring
the controller to the Pi. See [the controller file map](DEBUGGING.md).

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

Size is measured in the original camera frame (1280 × 960 by default), not the detector's
resized inference image. A YOLO box is approximate, and one flat scale factor
cannot correct every perspective/depth error in a three-dimensional bottle.

Existing 640 × 480 calibrations must be redone for the new capture size. Update
`frame_size_px`, `inspection_region_px`, and both millimetres-per-pixel values
before enabling size enforcement. Changing the camera position, lens, or sensor
view also requires recalibration even if the output resolution stays the same.

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

## Show Small, Medium, and Large on the recycling screen

The kiosk displays `Bottle size: Small`, `Medium`, or `Large` after a matched
plastic-bottle scan. The group and measured dimensions are also stored under
`inspection.size` in the recycling record. An unmatched, ambiguous, or unavailable
measurement displays `Bottle size uncertain`. With inspection off, no size label
is displayed. Accepted items with a confirmed size earn **0.5 points for Small**,
**1 point for Medium**, or **1.5 points for Large**. Profile names are matched
without regard to capitalization or surrounding spaces. Accepted items without
a confirmed Small/Medium/Large group retain the 0.5-point base reward, including
cans when size checking targets only bottles. Rejected items earn zero.

Use the fixed upright position and calibration procedure above. The following
helper prepares a **new observation config** without starting any hardware:

1. Install the updated controller and collect reference scans using the capture
   instructions above. New capture JSON files include the original `frame_size_px`
   as well as the full-frame detection box. Choose a clear reference scan and
   measure that upright bottle's horizontal width and vertical height in mm.
2. Copy `config/bottle-profiles.example.json` to `bottle-profiles.local.json`.
   Replace every `null` with measured minimum and maximum dimensions for your
   Small, Medium, and Large groups. Include multiple bottles and repeat placements
   to understand the variation. Limits apply to the camera's horizontal and vertical
   axes. Each minimum must be below its maximum. Do not use guessed values.
3. Run this command from `ecorefill-pi`, substituting the reference filename and
   your two measurements for the uppercase placeholders:

   ```sh
   python3 -m tools.calibrate_bottle_size \
     --reference inspection_samples/REFERENCE.json \
     --width-mm MEASURED_WIDTH_MM \
     --height-mm MEASURED_HEIGHT_MM \
     --profiles bottle-profiles.local.json \
     --output bottle-size.local.json
   ```

   The helper refuses missing measurements and overlapping profiles, including
   shared boundaries that could match two groups. Existing output files are
   preserved; choose a new output filename when recalibrating.
4. Set `ECOREFILL_INSPECTION_CONFIG` to the **absolute path** of
   `bottle-size.local.json` in your machine service and restart it. Deploy the
   updated kiosk build too (`npm run build:kiosk` from the repository root).
   Do not start a second controller alongside the service.
5. Test other physical bottles in each group on the running machine. Compare
   the reported `inspection.size.width_mm` and `height_mm` with ruler measurements,
   and check the displayed groups. Improve positioning or adjust measured limits
   if the results vary. Real-machine accuracy is not established by software tests.

The generated config targets both `plastic_bottle` and `pet_bottle`. Cans receive
`size.status: not_applicable`, and their existing material checks still apply.
It starts in `observe` mode, so size alone does not change acceptance. Confirmed
size groups affect rewards in both `observe` and `enforce` modes; use supervised
calibration sessions before offering these rewards to users. Keep observation
mode to label sizes, or switch to `enforce` only after validation if unsupported
bottle sizes should be rejected. For pre-existing inspection configurations,
merge the generated `size` section into your config to retain other checks.
The optional `size.materials` list scopes only the size check; cleanliness checks
still apply independently. Without that list, size checking applies to all materials.

## Enable rejection after validation

Set `mode` to `enforce` and restart the process. **Every enabled check must
pass.** You can enable cleanliness before size calibration is ready, or vice
versa. Missing models/calibration, uncertain results, partial views, multiple
meaningful detections, unsupported sizes, or overlapping size profiles reject
the item with zero points. Enforce mode with no checks enabled also rejects.
Off mode and observe mode do not enforce visual checks. When enabled, the separate
[HX711 weight check](WEIGHT_SENSOR.md) rejects both bottles and cans
above 500 g, or items whose weight cannot be verified.

Reports and rejection reasons are saved in local session logs and recycling
records. Visual inspection needs no new cloud service; the separate weight
reader requires `lgpio` on the Pi. The code
only rejects multiple objects that the detector actually finds; it cannot
guarantee detection of stacked or hidden items.

A pass means acceptable **visible appearance**, not verified cleanliness or
emptiness. An opaque can, a label, or the back of a bottle can hide contents.
The HX711 weight check detects excess measured mass using the configured
calibration and limits. Passing that check does not prove that a container is
empty or clean. Never use camera confidence as a substitute weight reading.

References: [Ultralytics classification](https://docs.ultralytics.com/tasks/classify/)
and [OpenCV calibration](https://docs.opencv.org/4.x/dc/dbb/tutorial_py_calibration.html).
