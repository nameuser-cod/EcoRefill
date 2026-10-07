# Upright gallon water-level monitoring

Mount the waterproof ultrasonic probe above the open mouth of the upright
gallon, pointing straight down at the water. The JSN-SR04T V2 has a 20 cm
blind zone; the bottle neck and shoulders can also reflect the sound. Check
the actual board version and test this mounting position before relying on
the display. Sensor reference:
[JSN-SR04T V2 datasheet](https://robu-prod-media.s3.ap-south-1.amazonaws.com/uploads/2019/10/JSN-SR04T-2.0.pdf).

## Percentage mapping

The requested rule treats a missing echo as **100%** after three consecutive
missing echoes. The dashboard labels this as an estimate. A disconnected
sensor, a blocked opening, or an out-of-range target can also produce no echo;
software cannot distinguish those conditions from water inside the blind zone.
An actual GPIO/initialization exception shows unavailable instead of full.

| Sensor distance | Display |
| --- | --- |
| No echo, confirmed | 100%, estimated |
| 20 cm or less, confirmed | 100%, estimated |
| 21 cm | 85% |
| 22 cm | 80% |
| 23 cm | 75% |
| 24 cm | 70% |
| 28 cm | 50% |
| 33 cm | 25% |
| 38 cm or more, within sensor range | 0% |

Values between calibration points are interpolated and rounded to the nearest
whole percentage. Three consecutive readings of the same kind are required;
valid distances use their median to reduce splashes and isolated reflections.
Invalid numeric readings clear the estimate. An estimate that stops refreshing
is published as unavailable after `max(15, 3 * poll_seconds * confirm_readings)`
seconds (18 seconds with the defaults).

The default **38 cm empty distance is an assumed endpoint**, chosen to continue
85% at 21 cm by subtracting 5 percentage points per additional centimeter.
Measure your actual sensor-to-bottom distance and update `empty_distance_cm`.
Changing that endpoint changes the slope below 85%. These percentages are a
custom distance estimate; the bottle's curved shape means they are not a
calibrated measurement of remaining liters.

## Separate sensor wiring

Stop the machine controller and switch off power before wiring. This is an
additional sensor: keep the customer-container sensor on BCM23/24 and the
bin sensor on BCM16/20.

| Gallon sensor connection | Raspberry Pi connection |
| --- | --- |
| VCC | 5 V, physical pin 2 or 4, for a 5 V compatible board |
| GND | Common GND |
| TRIG | BCM12, physical pin 32 |
| ECHO | BCM13, physical pin 33, through the divider below |

For a 5 V ECHO, connect ECHO through **330 ohms** to a junction. Connect the
junction to BCM13 and through **470 ohms** to GND. Keep the controller board
dry. Follow the pin labels on the actual board rather than the photo's pin
order. The existing [GPIO wiring guide](DIRECT_GPIO.md) describes the same
Pi input protection. Never connect a 5 V ECHO directly to a Pi GPIO.

All three ultrasonic sensors share a ping lock and 60 ms quiet interval to
reduce crosstalk. Check the dispenser's container-removal behavior again after
installation. This monitor only supplies the dashboard reading; the existing
container sensor still controls whether dispensing can proceed.

## Install and verify

Copy the complete updated `machine/` package and `tools/` directory, plus
`config/water-level.example.json`, to the Pi's existing `ecorefill-pi` folder.
Preserve credentials, other local settings, models and `data/`.
With the controller stopped, run from `ecorefill-pi`:

```bash
cp config/water-level.example.json water-level.local.json
python3 -m tools.check_water_level --config water-level.local.json
```

First aim the probe at a flat target at 21, 22 and 23 cm. Expect 85%, 80% and
75% after confirmation. Then test the full, partly full and empty bottle.
Verify real echoes before accepting the no-echo/full assumption. The diagnostic
operates only the sensor, without moving the pump or servos or writing cloud data.

After stopping the diagnostic, start the controller normally:

```bash
python3 machine_flow.py
```

The controller automatically loads `water-level.local.json` beside
`machine_flow.py`, independently of the working directory. Alternatively set
`ECOREFILL_WATER_LEVEL_CONFIG` to an absolute JSON path. Without a config file,
the feature is disabled so an unwired additional sensor does not invent a
full reading. Set `"enabled": false` to disable it. Conflicting pins are rejected
before hardware startup, including pins assigned by a custom bin configuration.

Sensing runs every 2 seconds. The latest confirmed reading uploads to
`machines/{MACHINE_ID}` with the existing 30-second heartbeat, using `waterLevel`,
`waterDistanceCm`, `waterLevelStatus` and `waterLevelUpdatedAt`. Cloud calls stay
off the sensing thread. Sensing continues offline; the next successful heartbeat
publishes the latest local reading. Install the updated frontend to see the
estimated-full label. No Firestore rules change is needed for the Pi's existing
Admin credentials.

```bash
python3 run_tests.py test_water_level.py test_machine_presence.py test_bin_monitor.py test_machine_runtime.py test_gpio_controller.py
```

Automated verification uses simulated hardware. Wiring, physical distance
calibration, neck reflections and actual cloud delivery need checking on the Pi.
