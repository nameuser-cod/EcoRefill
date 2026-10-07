# Center bin ultrasonic sensor and owner full-bin alert

Mount **one HC-SR04 above the middle of the recycling bin, pointing down** at
the contents. Keep its view clear of the chute, rim, divider and side walls.
This sensor measures the height of the pile in the center; uneven piles away
from that point may need checking when choosing the mounting position.

The bin sensor uses separate pins from the existing water-container sensor.
Both sensors use the existing `lgpio` dependency, kernel edge timestamps, and
a shared ping lock with a 60 ms quiet interval after each measurement to reduce
crosstalk. Recheck container-removal behavior on the actual water dispenser
after installing the additional sensor.

## Wiring

Stop the controller and switch off power before connecting wires.

| HC-SR04 connection | Raspberry Pi connection |
| --- | --- |
| VCC | 5 V, physical pin 2 or 4 |
| GND | Common GND, for example physical pin 39 |
| TRIG | BCM16, physical pin 36 |
| ECHO | BCM20, physical pin 38, **through the divider below** |

Connect ECHO through **330 ohms** to a junction. Connect that junction to BCM20
and through **470 ohms** to GND. Never connect the HC-SR04's 5 V ECHO directly
to a Pi GPIO. This follows the
[GPIO Zero HC-SR04 wiring instructions](https://gpiozero.readthedocs.io/en/stable/api_input.html#distancesensor-hc-sr04).
The water sensor stays on BCM23/24. BCM16 is also used as a temporary test
input in the PWM diagnostic: disconnect the bin sensor before that diagnostic,
then restore it afterward with power off.

## Configure and check distances

Copy the complete updated `machine/` directory, `tools/check_bin.py`, and
`config/bin.example.json` into the Pi's existing installation. Preserve its
credentials, model, local settings and `data/` directory. From `ecorefill-pi`,
with the controller stopped:

```bash
cp config/bin.example.json bin.local.json
python3 -m tools.check_bin --config bin.local.json
```

The diagnostic prints fresh distances without creating alerts or moving the
mechanism. Check an empty bin, a pile at the intended full line, and a falling
bottle. Adjust `full_distance_cm` to the distance from the sensor face to the
desired full line. Choose a larger `clear_distance_cm` that is comfortably
below the measured empty-bin distance. Both distances are in centimeters.
The defaults are starting values; calibrate them to the actual bin.

Start the controller using its existing environment and settings, adding:

```bash
ECOREFILL_BIN_CONFIG=./bin.local.json python3 machine_flow.py
```

Set `ECOREFILL_BIN_CONFIG` to an absolute path in the Pi service environment
when starting automatically. Without this variable the feature is enabled
using the example defaults. Set `"enabled": false` in the loaded JSON to
disable bin monitoring. GPIO conflicts with the buttons, water sensor,
servos, pump relay or HX711 are rejected before startup.

## Alert behavior

- Read every 2 seconds. Three consecutive valid readings of **10 cm or less**
  create one unread **bin full** owner alert: “The recycling bin is full.
  Please empty the bin.”
- Missing, out-of-range or failed readings break the confirmation sequence.
  A single falling item does not confirm fullness.
- While full, no additional alerts are created, including after a restart or
  the owner marking the alert read or resolving it.
- Three consecutive valid readings of **20 cm or more** rearm the sensor after
  emptying. Readings between the two thresholds keep the current state.
- `confirm_readings`, `poll_seconds`, both distance thresholds, and both BCM
  GPIOs are configurable in `bin.local.json`.

Alerts appear in the existing owner Dashboard and Alerts page. For phone
delivery, the assigned owner must enable Android notifications as described in
[Phone notifications](PHONE_NOTIFICATIONS.md). The Pi needs internet access
for cloud and phone delivery. Existing notification rules skip phone delivery
for alerts older than 24 hours.

The full/clear latch and pending alerts are committed together in the existing
SQLite journal. Detection continues offline; queued alerts upload when the
connection returns. Permanent Admin-only receipts in `machine_sensor_events`
prevent a lost upload acknowledgment from recreating a resolved/deleted alert.
The existing Firestore rules deny client access to those receipts; no frontend
or rules deployment is needed. The monitor reports fullness; it does not stop
recycling or dispensing. On-machine wiring, calibration, and phone delivery
still need verification; automated tests use simulated hardware and cloud.

```bash
python3 run_tests.py test_bin_monitor.py test_gpio_controller.py test_machine_runtime.py test_push_notifications.py
```
