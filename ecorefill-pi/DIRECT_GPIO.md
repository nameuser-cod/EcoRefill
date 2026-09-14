# Raspberry Pi 5: direct sorter and dispenser

The machine app uses the Pi 5's GPIO directly for both sorting and dispensing.
Start it with `python3 machine_flow.py`; no controller-selection variable is
needed. The ESP32 serial connection path has been removed.

## Wiring

Use **BCM GPIO numbers** in code. The physical pin column identifies positions
on the Pi's 40-pin header. This table supersedes the earlier chat assignment of
relay controls to GPIO17/27: those pins already serve the machine's buttons.

| Component connection | BCM GPIO | Physical pin |
| --- | --- | --- |
| MG996R accept/reject gate signal | 18 | 12 |
| MG996R bottle/can sorter signal | 19 | 35 |
| HC-SR04 TRIG | 23 | 16 |
| HC-SR04 ECHO, through divider below | 24 | 18 |
| Relay 1 transistor base, through 1 kΩ | 22 | 15 |
| Relay 2 transistor base, through 1 kΩ | 26 | 37 |
| Common signal ground | GND | 6 (or another GND pin) |
| Existing green button | 17 | 11 |
| Existing blue button | 27 | 13 |
| HX711 DT / DOUT | 5 | 29 |
| HX711 SCK / CLK | 6 | 31 |
| HX711 VCC | 3.3 V power | 1 |
| HX711 GND | GND | 6 (or another GND pin) |

The optional HX711 uses GPIO5/6. Do not also connect the ESP32 to these
control signals. Do not enable another overlay using GPIO18/19, such as I2S or
an SPI chip select on these pins.

### Buttons and weight sensor

Connect each momentary button between its GPIO and GND. For a button labeled
COM/NO/NC, use COM and NO, leaving NC unused:

```text
Green button: NO -> GPIO17 / pin 11; COM -> GND / pin 9
Blue button:  NO -> GPIO27 / pin 13; COM -> GND / pin 14
```

The code enables internal pull-ups: released reads HIGH, pressed reads LOW.
The switch contacts need no 5 V connection. If the buttons are illuminated,
their LED terminals are separate from the switch contacts.

The load cell connects to the HX711's E+/E-/A+/A- terminals according to its
datasheet; the HX711 connects to the Pi using the four rows above. Follow the
module's printed labels, not wire colors. The project's wiring powers the
HX711 from Pi **3.3 V**, separate from the actuators' external 5 V supply.

Weighing is disabled by default. To enable it with direct GPIO control:

```sh
ECOREFILL_GPIO_CONFIG=./gpio.local.json \
WEIGHT_SENSOR_ENABLED=true python3 machine_flow.py
```

See [weight sensor calibration and diagnostics](WEIGHT_SENSOR.md) before relying
on gram readings. Stop the weight diagnostic before starting the full app.

### Power connections

```text
12 V battery -> buck converter, regulated 5.0 V OUT+
                                    +-> gate servo red
                                    +-> sorter servo red
                                    +-> HC-SR04 VCC
                                    +-> relay VCC and JD-VCC

Buck OUT- -> servo brown/black wires, HC-SR04 GND, relay GND,
             both transistor emitters, Pi GND

Pi 5 -> its own suitable USB-C supply
Pump -> its own rated supply, switched through the relay contacts
```

Keep external +5 V separate from the Pi's power pins. Route servo power and
return wires directly to the converter's distribution point; do not pass their
current through Pi ground pins or a small solderless breadboard. Servo signal
wires are normally orange/yellow; check the actual connectors.

### HC-SR04 ECHO divider

```text
HC-SR04 ECHO -- 330 Ω --+-- GPIO24 / physical pin 18
                      |
                    470 Ω
                      |
                  Common GND
```

This gives approximately 2.94 V for a 5 V echo. TRIG connects directly to
GPIO23. A resistor in series alone is not this divider.

### CW-021 relay inputs: two NPN interfaces

The photographed board has 5 V Songle SRD-05VDC-SL-C relays. The supplied
sketch identifies it as active low; this implementation uses that behavior.
Use **two 2N3904 NPN transistors, two 1 kΩ resistors, and two 10 kΩ resistors**.
Wire each channel as follows, using the transistor manufacturer's lead pinout:

```text
Pi GPIO22 or GPIO26 -- 1 kΩ -- Base
                                |
                              10 kΩ
                                |
Common GND ---------------------+-- Emitter

Relay IN1 or IN2 ------------------- Collector
```

GPIO22 controls IN1; GPIO26 controls IN2. The 10 kΩ resistor is from base to
emitter. **Pi HIGH turns the relay ON; Pi LOW turns it OFF** through this
interface. Do not copy the sketch's active-low Pi output logic or connect IN1/2
straight to the Pi. The second relay is initialized OFF and remains OFF.

Power relay VCC and JD-VCC from external 5 V. If a jumper links those two
labeled pins, retain that link; never bridge either one to GND. Identify the
labels before wiring: the jumper header is partly obscured in the photo.
This common-ground arrangement does not retain galvanic isolation at the
control inputs.

With the pump and Pi disconnected, confirm the powered board activates a relay
when its IN pin is connected to module GND, and releases when disconnected.
This verifies the active-low assumption without exposing Pi GPIO to the input.

### Pump contacts

For a DC pump with its appropriate supply:

```text
Pump supply + -> relay channel 1 COM
Relay channel 1 NO -> pump +
Pump - -> pump supply -
```

Use the board's contact diagram or an unpowered continuity check to identify
COM and NO; do not infer their order from the rotated photo. With the relay
unpowered, COM-NC conducts and COM-NO is open. The printed resistive contact
rating is not a motor-starting rating. Use suppression appropriate to the pump;
for a simple brushed DC motor, a suitably rated flyback diode goes across the
motor, cathode/stripe to + and anode to -. The pump circuit can remain isolated
from Pi ground when it connects only through the relay contacts.

## Enable Pi 5 hardware PWM

The servos use RP1 **hardware PWM**, channels 2/3 on GPIO18/19. The HC-SR04 and
relays use `lgpio`. The code locates the RP1 GPIO chip by label and PWM0 by its
device-tree node, so it does not assume gpiochip0 versus gpiochip4 or select the
fan's PWM controller.

On the Pi, install the GPIO packages:

```sh
sudo apt install python3-lgpio python3-gpiozero
sudo nano /boot/firmware/config.txt
```

Add this in an applicable `[all]` section, without duplicating an existing PWM
overlay, then reboot:

```ini
[all]
dtoverlay=pwm-2chan
```

```sh
sudo reboot
```

After reboot, from the repository's `ecorefill-pi` directory:

```sh
sudo python3 direct_gpio.py --prepare-pwm
```

Run that preparation command **once after each boot, with the controller
stopped**. It exports channels 2/3 and grants the `gpio` group access to their
PWM attributes. Run the app as your normal user. That user needs membership in
`gpio` (standard on Raspberry Pi OS); if missing, add it with
`sudo usermod -aG gpio "$USER"` and log out/in. If using a virtual environment,
it must have access to `lgpio` (for example, create it with
`python3 -m venv --system-site-packages .venv`).

## Run the standalone controller

Stop the full machine app before running the console. Opening either controller
initializes both relay outputs OFF and centers both servos.

```sh
cd ~/ecorefill-app/ecorefill-pi
cp gpio.example.json gpio.local.json
python3 direct_gpio.py --config gpio.local.json --distance
```

This prints fresh distances or `NO ECHO`; use Ctrl+C to exit. Then start the
command console:

```sh
python3 direct_gpio.py --config gpio.local.json
```

Enter one command at a time:

```text
BOTTLE
CAN
REJECT
RESET
WATER_250
WATER_500
WATER_1000
QUIT
```

`RESET` interrupts a running operation, turns relays off, and centers the servos.
Other commands while busy are rejected. `QUIT`, Ctrl+C, EOF, and SIGTERM cancel
work, turn relays off, and disable servo PWM. You can also run a single command:

```sh
python3 direct_gpio.py --config gpio.local.json --command BOTTLE
```

For the first sorting tests, detach the mechanical linkage. For the first relay
tests, disconnect the pump and observe the relay indicators/clicks.

## If the servos do not move

Stop the full machine app. With the linkages detached, run this diagnostic from
the Pi's `ecorefill-pi` directory:

```sh
python3 check_servos.py --diagnose-only
sudo python3 direct_gpio.py --prepare-pwm
python3 check_servos.py --servo gate
python3 check_servos.py --servo sort
```

The diagnostic checks live pin routing using `pinctrl get`. GPIO18 must report
`PWM0_CHAN2`; GPIO19 must report `PWM0_CHAN3`. It does not move servos if routing
cannot be verified. If either pin reports input, output, SPI, or I2S, check that
`dtoverlay=pwm-2chan` applies under `[all]`, reboot, and stop conflicting programs
or overlays. Exporting PWM channels alone does not set the header pin routing.

Each motion test sends only the selected servo to nominal **90°, 180°, then its
accept/bottle position, then 90°**, holding each setting for one second. The gate
accept position is 0° (500 µs); the sorter bottle position is 45° (975 µs).
The 90° and 180° defaults are 1450 and 2400 µs, using the original sketch's
500–2400 µs range. Use
`--config gpio.local.json` to test your saved positions. Both relays stay OFF, the sensor is not sampled,
and the camera/model/Firebase are not loaded. A missing sensor need not be wired
for this test. All controller resources must nevertheless be available; stop any
other process claiming their GPIOs before running it.

During movement, the printed PWM settings should include `enable=1`,
`period=20000000`, and `duty_cycle=1450000`, `2400000`, `500000` (gate accept),
or `975000` (sorter bottle) with the defaults. Those are
software settings, not a measured waveform. The test disables PWM afterward.

If those settings and pin routing are correct but a servo remains still, check
its signal lead against the **physical** pin number (gate 12, sort 35), common
ground, and voltage at the servo's power connector while motion is requested.
Where available, an oscilloscope/logic analyzer can confirm actual 50 Hz pulses.
Report the diagnostic output and whether the motor is silent, buzzing, or moving
to narrow down power, wiring, signal-level compatibility, or mechanical issues.

### Measure the actual PWM without a scope

`check_pwm_signal.py` uses a temporary jumper to measure the output's pulse
timing on a second Pi input. It does not rely on PWM sysfs readback.

Stop the app and power down before changing connections. Disconnect both servo
signal wires, then connect **physical pin 12 (GPIO18) to physical pin 36
(GPIO16)** with a jumper. Leave external servo power off for this measurement;
no external voltage connects to the jumper. GPIO16 is unused by the normal
controller. Power the Pi, prepare PWM if rebooted, then run:

```sh
sudo python3 direct_gpio.py --prepare-pwm
python3 check_pwm_signal.py --servo gate
```

The input should measure approximately 50 Hz at each requested pulse width:
1500, 1300, and 1700 µs. Three `PASS` lines confirm that the Pi input detected
those pulses. This does not measure signal voltage or establish that a servo
accepts that voltage. `INSUFFICIENT EDGES` or `TIMING MISMATCH` means the output
has not been verified; the temporary jumper and edge capture also need checking.

To measure the sort output, power down and move the jumper's output end from
physical pin 12 to physical pin 35; keep its input end on physical pin 36. Use
`python3 check_pwm_signal.py --servo sort`. Remove the temporary jumper and
restore servo signals with power off before returning to normal operation.

## Run with the existing EcoRefill app

From the same directory, using the Python environment already configured for
the camera, model, and Firebase dependencies:

```sh
ECOREFILL_GPIO_CONFIG=./gpio.local.json python3 machine_flow.py
```

Set `ECOREFILL_GPIO_CONFIG` in your existing service configuration to load your
calibration file, and run PWM preparation before the service starts after each
boot. Without a calibration file, `python3 machine_flow.py` uses the defaults in
`gpio.example.json`. The obsolete `ECOREFILL_CONTROLLER` variable is ignored and
can be removed. Relative calibration paths resolve from the working directory;
use an absolute path in a service if needed.

The existing sorting and water APIs route to the direct controller. Sorting
waits for the mechanism to settle before the camera rearms; a reported sorting
failure does not award points. Water completion/errors retain the existing
format. There is no automatic retry of a GPIO refill or fallback to the ESP32.

## Calibration and timing

Edit `gpio.local.json` for both the console and the app:

- Servo positions are **pulse widths in microseconds**, not degrees. Defaults
  are **500/1450/2400 µs at 50 Hz** for nominal **0°/90°/180°**, matching the
  pasted sketch's pulse range. Gate accept uses 0°; sorter bottle uses
  **45° (975 µs)**. Gate reject
  and sorter can use 180°; startup/reset use 90°. Physical travel varies by servo:
  stop the test if a motor presses against a mechanical stop or stalls.
  Adjust each saved position for the actual mechanism rather than forcing a
  servo beyond its physical travel.
- `water_250_seconds`, `water_500_seconds`, and `water_1000_seconds` retain the
  supplied **25/30/45 seconds**. These are timers, not measured volumes. Collect
  and measure water for each selection before treating the labels as mL.
- Water waits at most 30 seconds for **two consecutive** readings within 10 cm.
  Missing readings reset that count. The app marks dispensing before pump-on;
  after that callback completes, the controller rechecks bottle presence.
- Four consecutive valid readings beyond 14 cm stop with `CONTAINER_REMOVED`.
  Twenty consecutive readings without confirmed presence (no echo or too far)
  stop with `SENSOR_LOST`. A valid reading within 14 cm clears both counters.
  Samples are separated by 100 ms, with up to 60 ms waiting for echo delivery;
  those limits deliberately tolerate short dropouts and do not stop instantly.
- The spare relay stays OFF. No command directly energizes it.

An existing `gpio.local.json` overrides the new defaults. To update just its six
servo positions while retaining your pump timers and sensor thresholds, run from
the Pi's `ecorefill-pi` directory with the machine stopped:

```sh
python3 - <<'PY'
import json
from pathlib import Path
path = Path('gpio.local.json')
data = json.loads(path.read_text()) if path.exists() else {}
data.update(gate_center_us=1450, gate_accept_us=500, gate_reject_us=2400,
            sort_center_us=1450, sort_bottle_us=975, sort_can_us=2400)
path.write_text(json.dumps(data, indent=2) + '\n')
PY
```

The controller checks deadlines and shuts the pump off in cleanup, but it is
not an independent hardware cutoff. A frozen Pi, SIGKILL, or welded relay can
defeat software shutdown. Validate actual sensor readings, removal behavior,
relay startup/shutdown, servo travel, and pump output on the machine. This code
was checked with simulated hardware and has not been electrically tested here.

## Sources and tests

- [Pi 5 PWM channel mapping and overlay](https://github.com/Pioreactor/rpi_hardware_pwm)
- [RP1 device-tree PWM0/PWM1 definitions](https://github.com/raspberrypi/linux/blob/rpi-6.12.y/arch/arm64/boot/dts/broadcom/rp1.dtsi)
- [Linux PWM sysfs interface](https://docs.kernel.org/driver-api/pwm.html)
- [lgpio pulse and edge callback API](https://github.com/joan2937/lg/blob/master/PY_LGPIO/lgpio_extra.py)
- [HC-SR04 divider](https://gpiozero.readthedocs.io/en/stable/api_input.html#distancesensor-hc-sr04)

Run local regressions without Pi hardware:

```sh
python3 -m unittest test_gpio_controller test_machine_runtime test_weight_sensor
```
