# Test the 1 kg HX711 scale on Raspberry Pi 5

Copy the `tools/` and `machine/` packages to the Pi's `ecorefill-pi` directory. This standalone
diagnostic uses DT on GPIO 5 (physical pin 29), SCK on GPIO 6 (pin 31),
3.3 V on pin 1, and GND on pin 6. Follow the HX711's printed labels.
Only one program should use these two signal pins at a time.

On Raspberry Pi OS, install the GPIO dependency and run from that directory:

```bash
sudo apt update
sudo apt install python3-lgpio
/usr/bin/python3 -m tools.check_weight
```

The script identifies the Pi 5 RP1 chip by its label, because its device number
varies across kernel versions. Using the system Python above makes the apt
package available even if your application uses a virtual environment.

Place a light object on the platform, then remove it. Raw counts should change
and return near their original value. Negative raw counts are normal. These
numbers are not grams. Press Ctrl+C to stop.

Next, use a known mass, such as a 100 g calibration weight:

```bash
/usr/bin/python3 -m tools.check_weight --calibrate
```

Follow the prompts to measure the empty platform and the known mass. The script
checks both reference sample ranges using the calculated factor. If either range
exceeds 3 g (or `HX711_MAX_SPREAD_G`), it reports `Calibration is unstable` and
exits without printing coefficients to save. Resolve the noise before retrying.
Otherwise it prints the offset and signed counts-per-gram factor, then displays grams.
Calibration lasts only for that run; save the printed numbers for later setup.
Remove the reference mass and verify near-zero readings, then check with a
different known mass. Displaying tenths of a gram does not establish accuracy.
The total supported load, including platform and container, must stay within
1 kg. Taring does not increase the load cell's capacity.

If readings time out, check power, common ground, and DT/SCK labels. If DT stays
low or the ADC saturates, check the load-cell connections and mounting. If the
clock timing check fails, stop CPU-heavy programs and rerun. Python on Linux
cannot guarantee HX711 pulse timing; this diagnostic stops on detected timing
violations rather than displaying that sample. Persistent failures need a
different acquisition method before integration into the running machine.

## Automatic rejection in the recycling controller

**Enabled by default.** The controller initializes the HX711 and rejects a bottle
or can only when a valid, stable weight reaches 255 g or more. The saved calibration
and 255 g rejection thresholds apply automatically. The installed 1 kg load cell's
capacity includes the platform and container; this software limit does not
increase its rated capacity.

Copy the updated `machine/` directory to the Pi and restart the controller for
this change to take effect. Remove any existing `WEIGHT_SENSOR_ENABLED=false`
override from the controller's environment, or set it to `true`. If a service
manager starts the controller, update the variable in that service.
To explicitly disable weighing:

```bash
WEIGHT_SENSOR_ENABLED=false python3 machine_flow.py
```

When disabled, the controller skips HX711 initialization, weight settling, and
sampling. It records `inspection.weight.status` as `disabled`. Material and
enabled visual checks still decide acceptance, sorting, and points. The
separate rearm delay also remains active.

The following behavior applies **when `WEIGHT_SENSOR_ENABLED=true`**.

The controller starts a **2-second** settling interval when the camera confirms
the item is still. Material detection and visual checks run during that interval.
If they pass, the controller waits only for any remaining settling time, then
takes a fresh HX711 measurement before sending a sorting command or awarding
points. `WEIGHT_SETTLE_SECONDS` in `machine/config.py` sets this interval. Items
already rejected by material or visual checks skip the measurement.

The separate **2-second pause before detecting the next item** and its
stable-frame check remain in place. Weight sampling still runs after AI
detection finishes, so the GPIO sampling loop does not compete with inference.

| Detected material | Passes the weight limit | Rejected |
| --- | --- | --- |
| Plastic bottle (`plastic_bottle`, `pet_bottle`) | Below 255 g, including zero and negative readings | 255 g or more |
| Aluminum can (`aluminum_can`, `aluminium_can`) | Below 255 g, including zero and negative readings | 255 g or more |

Other material, confidence, and visual rules still apply. When enabled, the weight
check runs even when visual inspection is `off` or `observe`. Rejected items send
`REJECT` to the Pi GPIO controller and earn zero points; existing session totals are retained.
The kiosk displays the weight-limit rejection reason. Local logs and Firestore
recycling records include `inspection.weight` with grams, limit, status, spread,
and measurement time when a reading is available.

The defaults in `machine/config.py` use the calibration measured on October 8,
2026 with a 255 g reference: **offset -647096**, **725.54509804 counts/gram**,
DT on GPIO 5 and SCK on GPIO 6.
The controller never automatically tares at startup or while weighing an item.
To use a later calibration, export both values before starting the controller:

```bash
export HX711_OFFSET=-647096
export HX711_COUNTS_PER_GRAM=725.54509804
export WEIGHT_SENSOR_ENABLED=true
python3 machine_flow.py
```

After updating the Pi, transfer the complete `machine/` and `tools/` packages.
Stop the
diagnostic with Ctrl+C before starting `machine_flow.py`; they use the same GPIO
pins. Use the usual machine Python environment and Firebase setup. The example
above does not replace the existing Firebase environment variables. If `lgpio`
is not available inside a virtual environment, install it in that environment
with `python3 -m pip install lgpio` (or use a venv with system site packages).

After the settling delay, each decision discards the buffered conversion and
takes 10 new samples with a separate 4-second acquisition deadline. If the
sample range exceeds **3 g**, the controller continues sampling and checks the
latest 10 readings until they settle or the original deadline expires. Persistent
instability bypasses the weight check, preserving the material/visual result.
The measured grams, sample range, and allowed range remain in the error log and
inspection record. `HX711_MAX_SPREAD_G` configures this diagnostic tolerance.
Missing hardware, timeouts, detected clock-timing errors, saturation, nonfinite weight, and
unstable readings also bypass the weight check. The inspection record uses
`status: pass`, `bypassed: true`, `measurement_status` (`unavailable`, `invalid`,
or `unstable`), and `detail` to distinguish a bypass from a verified weight pass.
An unstable reading is bypassed even if its provisional grams reach 255 g.
An acquisition error resets HX711 serial framing on the next measurement.
If initialization fails, fix the connection/dependency and restart the service.

Zero and negative finite readings pass the weight check and retain their signed
grams in the inspection record. They do not produce `No positive item weight detected`.
The weight rule rejects at exactly 255 g or more without rounding; material and
enabled visual checks still decide whether an item is accepted. Check calibration
if a known mass does not give the expected reading, then update the controller's
calibration environment variables and restart it.

The item must be supported entirely by the weighing plate, clear of the orange
chute, while the camera verifies it and the sensor samples it. Calibration cannot
compensate for changing chute contact. Recheck readings across the safe weighing
range on the running Pi, with the camera/model active. Keep the total load,
including the platform and container, within the load cell's 1 kg capacity.
The 3 g spread limit is a movement check, not a claim of accuracy; raw precision
is retained for threshold decisions.

References: [HX711 datasheet](https://cdn.sparkfun.com/datasheets/Sensors/ForceFlex/hx711_english.pdf),
[lgpio Python API source](https://github.com/joan2937/lg/blob/master/PY_LGPIO/lgpio_extra.py),
[Raspberry Pi GPIO guidance](https://pip-assets.raspberrypi.com/categories/685-app-notes-guides-whitepapers/documents/RP-006553-WP/A-history-of-GPIO-usage-on-Raspberry-Pi-devices-and-current-best-practices).
