# Installed Pi detection update — October 7, 2026

The Raspberry Pi is configured to use the existing trained weights exported
to **full-precision NCNN, input size 416, one inference thread**. Normal startup
reads `inference.local.json`; source defaults and the original checkpoint remain
available for rollback. The installer did not start the controller.

| Pi comparison | Median material-decision time | Average CPU, one-core scale |
| --- | ---: | ---: |
| Original PyTorch, two threads | 131 ms | 245% |
| Full-precision NCNN, two threads | 67 ms | 191% |
| Selected NCNN, one thread | 96 ms | 102% |

The selected setting used approximately one of the Pi's four CPU cores during
the continuous saved-image benchmark. All 62 public validation decisions
matched their expected labels. One user-provided bottle and one aluminum can
were also correctly identified from original machine-camera photos, at 93%
and 95% model confidence respectively. Those two scores are not overall accuracy.

The smaller 640x480 motion stream worked on this camera while retaining
1280x960 main images. In short camera-only comparisons, motion-loop CPU fell
from approximately 6.8% to 4.8% of one core. Both paths used one OpenCV thread.
The final installed regression suite passed **287 tests**, with no skips.

NCNN's implicit FP16/BF16 execution is disabled. The initial reduced-precision
test incorrectly accepted a food-scene negative; full precision resolved that
difference. No acceptance thresholds or reward rules were changed.

To start the controller normally on the Pi:

```sh
cd /home/rpi/EcoRefill/ecorefill-pi
yolo-env/bin/python machine_flow.py
```

Use the existing machine startup/PWM preparation procedure as usual. The tests
did not operate sorting gates, dispense water, award points or change Firebase
records. Continuous operation with the live kiosk and diverse machine inputs
still needs validation; the recorded performance runs used saved images with
the controller and kiosk browser stopped. No throttling was reported during
these short measurements.

Reports, original validation images and the source backup are retained at:

```text
/home/rpi/ecorefill-inference-stage-20261007/
```

To temporarily use the original detector, override the local configuration:

```sh
cd /home/rpi/EcoRefill/ecorefill-pi
ECOREFILL_MODEL_PATH=models/ecorefill_best.pt yolo-env/bin/python machine_flow.py
```

For persistent rollback, rename `inference.local.json` to
`inference.local.json.disabled`. See [the performance guide](INFERENCE_PERFORMANCE.md)
for configuration and further testing. New YOLO26n training was not performed;
this update optimizes the existing custom detector.
