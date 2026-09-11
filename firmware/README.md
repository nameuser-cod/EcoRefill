# EcoRefill ESP32 controller

Open `ecorefill_controller/ecorefill_controller.ino` in Arduino IDE, select the
actual ESP32 board and serial port, install the ESP32 board package and the
**ESP32Servo** library, and upload. The sketch retains the supplied pin assignments
and active-low relay configuration. It has not been uploaded to a physical board.

| Device | GPIO |
| --- | --- |
| Accept/reject servo | 19 |
| Sorting servo | 18 |
| Water relay | 5 |
| Spare relay (kept off) | 23 |
| Ultrasonic trigger / echo | 32 / 33 |

## Behavior and protocol

Send one ASCII command per line at **115200 baud**: `BOTTLE`, `CAN`, `REJECT`,
`RESET`, `WATER_250`, `WATER_500`, or `WATER_1000`. CRLF and lowercase commands
are accepted. Lines are limited to 31 bytes before the newline and must complete
within one second. An oversized, invalid, or expired line is discarded through
its next newline; its suffix is never treated as a command.

- Operations advance without long delays. `RESET` turns both relays off as soon
  as the command is processed, cancels the active operation with
  `ERROR <command> CANCELLED`, centers the servos, and reports `OK RESET` after a
  one-second settling interval. A sensor measurement can occupy up to 30 ms.
- Commands arriving while busy are consumed, not queued, and receive
  `ERROR <command> BUSY`. A duplicate of the active water command reports its
  existing waiting/dispensing state without restarting its timer.
- Water starts after two consecutive valid readings at or below 10 cm, with a
  200 ms interval after each measurement, as in the original sketch. Waiting expires after 30 seconds with
  `ERROR <command> NO_BOTTLE`.
- While dispensing, any valid reading at or below 14 cm confirms presence.
  The original thresholds are retained: four consecutive valid readings beyond
  14 cm stop with `CONTAINER_REMOVED`; twenty consecutive missing echoes stop
  with `SENSOR_LOST`. Measurements have a 100 ms interval after each reading,
  plus up to 30 ms waiting for an echo. Continuous no-echo shutdown therefore
  takes roughly 2.5–2.6 seconds, rather than the previous replacement's 600 ms.
  A combined run of twenty far/no-echo readings also stops with `SENSOR_LOST`,
  closing the original loophole where alternating failures reset each other.
  One valid reading within 14 cm clears both counters. Actual bottle movement
  cannot be proven from a distance reading alone.
- `DISPENSING <command>` and `OK <command>` retain the Pi's existing water protocol.
  Relay shutdown always occurs before completion/error messages are queued.
- Once a refill starts, another water request receives
  `ERROR <command> REMOVE_CONTAINER` until the idle controller observes one second
  of continuous absence. Both readings beyond 14 cm and no echo count as absence
  **only during this rearming check while the pump is off**, to allow an empty
  backdrop. A subsequent refill still requires two valid close readings. Sensor
  faults can imitate absence; this is not a transaction identifier or proof of
  physical removal. `RESET` preserves this latch; power cycling does not.
- Sorting success is reported after the sorter has had time to return to center.
  Bottle/can cycles take about 3.6 seconds; reject cycles take about 2.9 seconds.
- Input and output use fixed buffers. Input floods and a full serial transmitter
  cannot indefinitely block the control loop. Output reserves space for final
  responses, but sustained flooding can drop replies. The sender should maintain
  only one outstanding operation and continuously read responses.

The repository's Pi water reader recognizes the response format, including new
error reasons. Its sorting sender is currently fire-and-forget: it does not wait
for `OK` or handle `BUSY`, so callers must not send another sorting command until
the cycle finishes. The Pi also holds a serial lock while waiting for water;
calling its normal sorting/reset sender from another thread cannot interrupt that
wait. Firmware cancellation applies when `RESET` actually reaches the ESP32.

The plain command protocol cannot distinguish a legitimate new request from a
late retry after completion, removal, or a reboot. Exactly-once dispensing across
reconnections would require transaction IDs and persistent coordination on both
the Pi and ESP32.

## Calibration and hardware checks

Pump durations remain **25, 30 and 45 seconds** for the 250/500/1000 commands.
These are the user's original values, not verified volume calibration. Measure
the actual output for each command and adjust `WATER_*_TIME`; do not substitute
the old comment's hypothetical 2.5/5/10-second values without measurement.

Check on the actual machine before unattended use:

1. With the pump disconnected, confirm both relays remain inactive at power-up,
   reset, and reconnect. Firmware preloads the OFF latch before enabling GPIO
   output, but external circuitry must keep the active-low relay inactive before
   `setup()` runs and while the ESP32 is unpowered/resetting. GPIO 5 is a strapping
   pin on the original ESP32; verify the specific board and relay wiring.
2. Verify the sensor's electrical levels are compatible with the ESP32 input and
   that its readings distinguish the bottle from the background. Adjust the
   distance thresholds and bad-reading limits based on measured spill volume
   and real pump noise.
3. Test container removal, sensor disconnection, a short sensor dropout, `RESET`
   while waiting/dispensing/sorting, and repeated water commands. Confirm rearming
   works with your background and mounting.
4. Measure each water amount and confirm the servo endpoints do not force the
   mechanism against its stops.

Software timers do not stop a welded relay or enforce a cutoff if the processor
itself stops executing. Reset-time relay behavior and these physical failures
require appropriate hardware design.

## Regression tests

From the repository root, on a host with Clang:

```sh
clang++ -std=c++11 -Wall -Wextra -Werror -fsanitize=address,undefined \
  -I firmware/tests/stubs firmware/tests/controller_test.cpp \
  -o /tmp/ecorefill-controller-test
/tmp/ecorefill-controller-test
```

The tests compile the actual sketch with simulated time, GPIO, servos, ultrasonic
echoes and serial I/O. They cover mixed far/no-echo failures, sensor recovery,
consecutive detection, wait timeout, cancellation, duplicate commands, removal
rearming, malformed/oversized/expired input, serial backpressure, sorting order,
relay initialization order, and timer rollover. These host tests do not verify
ESP32 core/library compatibility, electrical behavior, or dispensing accuracy.

Implementation references: [ESP32 GPIO source](https://github.com/espressif/arduino-esp32/blob/master/cores/esp32/esp32-hal-gpio.c),
[ESP32 GPIO and strapping-pin documentation](https://docs.espressif.com/projects/esp-idf/en/stable/esp32/api-reference/peripherals/gpio.html),
[ESP32 UART API](https://docs.espressif.com/projects/arduino-esp32/en/latest/api/serial.html),
and [ESP32Servo](https://github.com/madhephaestus/ESP32Servo).
