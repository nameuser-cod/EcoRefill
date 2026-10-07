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

**Enabled by default.** The controller initializes the HX711 and requires a
valid weight reading before accepting a bottle or can. The saved calibration
and 1300 g (1.3 kg) limits apply automatically. The installed 1 kg load cell's
capacity includes the platform and container; this software limit does not
increase its rated capacity. Weighing items up to 1300 g requires a higher-capacity
load cell with room for the platform and container, and a new calibration.

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
| Plastic bottle (`plastic_bottle`, `pet_bottle`) | Up to and including 1300 g | Above 1300 g |
| Aluminum can (`aluminum_can`, `aluminium_can`) | Up to and including 1300 g | Above 1300 g |

Other material, confidence, and visual rules still apply. When enabled, the weight
check is required even when visual inspection is `off` or `observe`. Rejected items send
`REJECT` to the Pi GPIO controller and earn zero points; existing session totals are retained.
The kiosk displays the weight-limit rejection reason. Local logs and Firestore
recycling records include `inspection.weight` with grams, limit, status, spread,
and measurement time when a reading is available.

The defaults in `machine/config.py` use the latest supplied calibration:
**offset -695343**, **199.538 counts/gram**, DT on GPIO 5 and SCK on GPIO 6.
The controller never automatically tares at startup or while weighing an item.
To use a later calibration, export both values before starting the controller:

```bash
export HX711_OFFSET=-695343
export HX711_COUNTS_PER_GRAM=199.538
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
instability rejects the item with the measured grams, sample range, and allowed
range in the error log. `HX711_MAX_SPREAD_G` configures this diagnostic tolerance.
Missing hardware, timeouts, detected clock-timing errors, saturation, nonpositive weight, and
unstable readings reject the item instead of accepting without a measurement.
An acquisition error resets HX711 serial framing on the next measurement.
If initialization fails, fix the connection/dependency and restart the service.

`No positive item weight detected` means the measured weight is zero or negative;
the maximum-weight limit has not been applied. The error includes the calculated
grams, raw median, offset, and counts-per-gram factor. Check that the empty plate
returns near zero and a known mass gives a stable positive reading. Recalibrate
with an empty plate only after resolving any drift or contact with the chute,
then update the controller's calibration environment variables and restart it.

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
