# Bottle and can detection with lower Pi CPU use

The runtime supports the existing PyTorch checkpoint and custom NCNN exports.
It defaults to `models/ecorefill_best.pt`, input size **416**, two inference
threads, and one inference after an item has settled. Acceptance thresholds,
material routing, points, weight checks and visual inspection are retained.
NCNN runs on CPU with its own thread pool explicitly limited, and OpenCV uses
one thread. NCNN's implicit FP16/BF16 execution is disabled before loading:
the Pi's default reduced precision produced a false acceptance that disappeared
at full precision. These limits leave room for other services, but do not guarantee
responsiveness or temperatures without measurements on the installed Pi.

On **Pi 5**, idle motion checks copy a secondary **640x480 RGB888** stream instead
of repeatedly copying and resizing the 1280x960 main stream. The normalized scan
region, motion thresholds, rearm behavior and one-second stillness requirement
are retained. Once the item settles, capture the main stream for detection,
inspection and history photos. Check item triggering and sorting on the real
camera after installation. Set `ECOREFILL_MOTION_LOW_RES=false` to use the old
main-stream motion path, including on cameras/platforms without RGB lores support.

## Install optional tools

From the repository root, in the machine's existing Python environment:

```sh
python -m pip install -r requirements-inference.txt
```

Keep the existing Pi hardware packages from `requirements.txt`. On the export
workstation only, also install `pnnx`. The runtime integration is verified with
Ultralytics **8.4.83**; changing versions requires rechecking backend thread
settings and material decisions. The existing Pi installation was also verified
with Ultralytics 8.4.113, PyTorch 2.13.0 and OpenCV 5.0.0.93; its packages were
retained, adding only `ncnn==1.0.20260526` with `pip install --no-deps`.

## Export the current checkpoint first

```sh
cd ecorefill-pi
python -m tools.export_detection \
  --model models/ecorefill_best.pt \
  --output models/ecorefill_416_ncnn_model --imgsz 416
```

The exporter works on a temporary copy, refuses existing output directories,
and records the source checkpoint's SHA-256 and export settings. Generated
NCNN directories are ignored by Git; copy the complete directory to the Pi.
They require a matching `.param`/`.bin` pair and `metadata.yaml`. Exporting does
not activate the candidate or overwrite the deployed checkpoint.

For macOS 14, the PNNX 20260526 wheel's binary may require macOS 15 despite its
wheel tag. Use a compatible exporter such as `pnnx==20250430`, or export on
Linux. Do not change the Pi's runtime packages to solve a workstation issue.

Export each tested size separately. The loader rejects an NCNN export whose
metadata size differs from `ECOREFILL_INFERENCE_SIZE`.

## Compare decisions and processing time on the Pi

Use a CSV manifest of original full-frame camera images:

```csv
image,expected,group
photos/bottle_01.jpg,plastic_bottle,bottle-container-01
photos/can_01.jpg,aluminum_can,can-container-01
photos/glass_01.jpg,reject,glass-container-01
```

With the controller stopped and a known item positioned in the tray, capture
an original frame without operating servos or the pump:

```sh
python -m tools.capture_validation --output inspection_samples/bottle-01.jpg \
  --manifest inspection_samples/validation.csv --expected plastic_bottle \
  --group bottle-container-01
```

Use `--expected aluminum_can` only for a verified aluminum can and `reject`
for a verified unsupported object or empty tray. The tool appends your label;
it does not infer the material or create bounding-box training annotations.

Paths resolve relative to the manifest. Include varied bottles, verified
aluminum cans, glass, steel cans, other packaging, and empty trays. Keep all
views of a physical container/session in one dataset split. Use validation
images to choose model/size/settings; reserve separate containers for a final
test. Public-image diagnostics do not establish machine-camera accuracy.

Run one model per process with the kiosk open and normal background services
running. The benchmark never connects to the camera, Firebase, servos or pump.
Avoid running a second detector simultaneously; stop the controller's recycling
worker for this offline comparison. Test the actual controller separately below.

```sh
python -m tools.benchmark_detection \
  --model models/ecorefill_best.pt --manifest /path/to/validation.csv \
  --threads 2 --repeats 10 --output /tmp/ecorefill-pytorch-416.json

python -m tools.benchmark_detection \
  --model models/ecorefill_416_ncnn_model --manifest /path/to/validation.csv \
  --threads 2 --repeats 10 --output /tmp/ecorefill-ncnn-416.json
```

Reports include median, p95 and maximum material-decision latency, average
process CPU usage, sampled process RAM, CPU temperature and Pi throttle flags,
plus false accepts, false rejects and bottle/can confusion. One-core CPU usage
can exceed 100%; the all-core figure divides by the host's logical CPU count.
Temperature and flags are null where unsupported. RAM and temperatures are
sampled approximately once per second and can miss short peaks. Initial warmup
is excluded from timing. Reports refuse overwrite.

The decision timing includes cropping, preprocessing, inference and the
production confidence/area rules, but excludes disk decoding, preview writes,
camera capture, weight/visual inspection and sorting. CPU usage covers the
entire measured loop, including image decoding, optional waiting and monitoring.
Material metrics count each image once, independent of timing repeats.

With `--images /path/to/photos`, reports contain timing only, with no material
metrics. `--full-frame` disables the machine crop for public-image diagnostics;
leave it off for machine photos. Use `--interval 3` to approximate spaced item
arrivals after the default continuous stress test. Let the Pi return to a
similar starting temperature before comparing candidates.

Compare two threads against one if kiosk responsiveness is poor. Test **320**
only as a separately exported candidate, using `--imgsz 320` in both export
and benchmark. Keep 416 if smaller input increases wrong accepts or rejects.

## Activate a verified export

After the candidate passes material decisions and Pi load measurements, set
these variables in the controller's service environment, then restart it:

```sh
export ECOREFILL_MODEL_PATH="/absolute/path/to/ecorefill_416_ncnn_model"
export ECOREFILL_INFERENCE_SIZE=416
export ECOREFILL_INFERENCE_THREADS=2
python machine_flow.py
```

For persistent settings without editing controller source, copy
`config/inference.example.json` to `inference.local.json` after verification.
The example selects NCNN 416 with **one thread**, the recommended lower-load
setting from the Pi measurements. Normal `python machine_flow.py` then reads
those settings. Set `ECOREFILL_INFERENCE_CONFIG` to use a different JSON path.
Individual environment variables override the JSON values. Invalid fields,
types or image sizes fail before hardware initialization. Local settings are
excluded from Git and deployment archives.

The service starts only with local compatible weights. It does not download a
generic pretrained detector or silently fall back to another model. Generic
`bottle`/`can` weights are rejected because the material names are required.

Verify repeated real items and idle operation with the actual kiosk: correct
triggering, one scan per item, bottle/can routing, preserved photos, responsive
buttons, water controls, and temperature/throttle flags. `vcgencmd measure_temp`
and `vcgencmd get_throttled` report Pi temperature and power/thermal conditions.
The offline benchmark cannot validate these live behaviors. A fan and adequate
power are still needed for sustained workloads.

To temporarily return to the existing checkpoint, overriding any local settings:

```sh
export ECOREFILL_MODEL_PATH="models/ecorefill_best.pt"
export ECOREFILL_INFERENCE_SIZE=416
export ECOREFILL_MOTION_LOW_RES=false
python machine_flow.py
```

For a persistent rollback, rename `inference.local.json` to
`inference.local.json.disabled` and remove inference overrides from the service
environment. Keep the original checkpoint and the pre-update source backup.

## YOLO26n candidate training

The existing checkpoint is a small detector. A newer model is an experiment,
not a demonstrated fix for can-as-bottle errors. Collect original machine-camera
images and prepare reviewed labels and independent splits using
[the training guide](../../DATASET_TRAINING.md). Then train on the workstation:

```sh
python train_ecorefill_model.py \
  --data datasets/ecorefill_machine/data.yaml --model yolo26n.pt \
  --imgsz 416 --epochs 50 --device mps --name ecorefill_yolo26n_machine
```

`yolo26n.pt` is pretrained initialization, which Ultralytics may download; it
is not a bottle/can model until custom training completes. Use `--device cpu`
or the appropriate CUDA device on other workstations. Export the resulting
custom `best.pt` with the tool above, then compare both that export and its
PyTorch source using the same held-out manifest. NCNN export and padding can
change predictions; evaluate the actual deployed format. No new accuracy claim
or activation is justified by public-dataset scores alone.

References: [Ultralytics on Raspberry Pi](https://docs.ultralytics.com/guides/raspberry-pi/),
[NCNN export](https://docs.ultralytics.com/integrations/ncnn/),
[Picamera2 manual](https://datasheets.raspberrypi.com/camera/picamera2-manual.pdf).
