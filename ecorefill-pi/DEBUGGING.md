# Debugging the EcoRefill machine

Start the controller with the same command as before, from `ecorefill-pi`:

```sh
python3 machine_flow.py
```

When copying the controller to the Pi, copy the **whole `machine/` directory**
alongside `machine_flow.py`, `point_payments.py`, and `visual_inspection.py`.
Keep the existing model, credentials, and local inspection configuration.
The launcher is no longer a standalone copy of the controller.

## Adjust the camera scan box

The camera now watches and classifies only the center tray. In
`machine/config.py`, `DETECTION_REGION = (0.33, 0.04, 0.65, 0.96)` sets
the left, top, right, and bottom edges as fractions of the full image.
At 640 by 480 this crops x=211:416 and y=19:461. These initial bounds were
estimated from the machine screenshots; check them on the physical machine.

After a scan, open `detection_result.jpg`. It shows the selected object
without a yellow scan-region border. Predictions below the material's
acceptance threshold display **Uncertain material** and are recorded as
`unknown`, with no points awarded. Keep the whole container inside the
configured center crop. Adjust the four fractions and restart the
controller if the crop cuts off a container or includes the wall. Setting
`DETECTION_REGION = None` restores full-frame motion and inference.

Both motion detection and model inference use the same crop. Objects and
movement entirely outside it cannot trigger a scan or become model inputs.
The clean `captured_item.jpg` and scan-history photos retain the full view.
Inspection coordinates are translated back to the full camera image, so
existing size calibration remains in full-frame pixels. The minimum object
area also remains relative to the full frame.

The box does not force every object to be accepted and cannot guarantee the
correct material label. Initial screenshot checks recognized the green can
at 85%, but still mislabeled the silver can as a bottle at 83%. Test original
camera frames of both materials before relying on the new crop in operation.
The previous 3-second rearm pause is unchanged.

## Green or blue physical button does not respond

Stop the running machine controller first so two processes do not claim the
same GPIO pins. From `ecorefill-pi`, use the same Python interpreter and
environment as the controller:

```sh
python3 check_buttons.py
```

This uses the controller's button configuration and prints press/release events
without starting Firebase, the camera, the ESP32, or any machine workers.
Ctrl+C releases the GPIO inputs and exits; restart the controller afterward.

The diagnostic also polls raw `PIN LEVELS` independently of press callbacks.
Hold each button for one second: its level should change from `1` (released)
to `0` (pressed). Levels print on change and once per second so the script
still shows activity when no edges are reported. If levels change but no
`GREEN pressed` / `BLUE pressed` events appear, investigate GPIO edge callbacks.
If levels stay at `1` while held, check the switch contacts, ground connection,
and physical header pins; reinstalling `gpiozero` is not the first step.

Default wiring uses BCM numbering (not physical header numbering):

| Button | BCM GPIO | Physical header pin | Other switch terminal |
| --- | --- | --- | --- |
| Green | 17 | 11 | GND |
| Blue | 27 | 13 | GND |

`GREEN_BUTTON_GPIO` and `BLUE_BUTTON_GPIO` environment variables override the
BCM pin numbers. A released switch should report `released`; pressing it
connects its input to ground. If it is already `PRESSED` while untouched,
check the switch terminals and wiring. If initialization succeeds but pressing
does nothing, check the actual wired pins against the numbers printed.

If a button is `unavailable`, read the initialization traceback. Missing
`gpiozero`, an unavailable GPIO backend, permissions, or another process using
the pins can prevent initialization. The diagnostic prints the Python path
to help detect an interpreter/environment mismatch. On Raspberry Pi OS the
packages can be installed with:

```sh
sudo apt install python3-gpiozero python3-lgpio
```

The selected Python environment must be able to import those packages. For
Pi 5, GPIO Zero documents `lgpio` as the supported backend; see
[GPIO Zero pin factories](https://gpiozero.readthedocs.io/en/stable/api_pins.html).
To explicitly select it for a diagnostic run:

```sh
GPIOZERO_PIN_FACTORY=lgpio python3 check_buttons.py
```

If both events appear in the standalone check, restart the controller and
check its logs and `/api/machine/state`. Green needs at least one accepted item
and queues reward creation in the recycling worker. Blue requires an empty
batch and an idle, rejected, or error phase. It sets `water_refill_requested`,
which the kiosk must read to open the water screen.

## Find the right file

| Problem or change | Start here | Useful methods or settings |
| --- | --- | --- |
| Machine ID, GPIO pins, timeouts, prices, confidence thresholds | [`machine/config.py`](machine/config.py) | `MACHINE_ID`, `WATER_OPTIONS`, `ACCEPT_CONFIDENCE_LIMIT` |
| Startup, shutdown, resource ownership | [`machine/runtime.py`](machine/runtime.py) | `MachineRuntime.start`, `run`, `close` |
| Session totals, phases, green/blue button behavior | [`machine/state.py`](machine/state.py) | `update_state`, `reset_state`, `rearm_for_next_item`, `request_water_refill` |
| ESP32 missing, sorter commands, water acknowledgements | [`machine/serial_controller.py`](machine/serial_controller.py) | `get_esp32_connection`, `send_to_esp32`, `run_water_command` |
| Camera failures, motion detection, repeated scans | [`machine/camera.py`](machine/camera.py) | `restart_camera`, `wait_for_item_motion`, `frame_has_motion` |
| Material accepted or rejected incorrectly | [`machine/detection.py`](machine/detection.py) | `verify_item`, `sort_item` |
| Size or cleanliness inspection | [`visual_inspection.py`](visual_inspection.py) | `VisualInspector`; see [inspection setup](INSPECTION.md) |
| Recycling loop, saved items, batch reward creation | [`machine/recycling.py`](machine/recycling.py) | `machine_worker`, `save_recycling_to_firestore`, `finalize_recycling_session` |
| Phone refill requests, deductions, refunds, completion | [`machine/water_worker.py`](machine/water_worker.py) | `water_request_worker`, `process_water_refill_request` |
| Firebase credentials or bearer token verification | [`machine/firebase.py`](machine/firebase.py) | `initialize_firebase`, `require_firebase_user` |
| Kiosk recycling API | [`machine/machine_api.py`](machine/machine_api.py) | `api_machine_*` |
| Water session API | [`machine/water_api.py`](machine/water_api.py) | `api_*_water_refill_session` |
| Claiming recycling points | [`machine/rewards_api.py`](machine/rewards_api.py) | `api_redeem_recycling_reward` |
| Route paths and local/public exposure | [`machine/routes.py`](machine/routes.py) | `create_apps` |
| Public endpoint/tunnel discovery | [`machine/tunnel.py`](machine/tunnel.py) | `start_redemption_tunnel`, `watch_redemption_tunnel` |
| GCash point purchases and owner reviews | [`point_payments.py`](point_payments.py) | `PointPayments`, `register_payment_routes` |
| Log formatting and tracebacks | [`machine/diagnostics.py`](machine/diagnostics.py) | `configure_logging`, `log` |

## How the modules fit together

`MachineRuntime` combines the workflow classes and owns the shared resources:
`self.db`, `self.picam2`, `self.esp32`, the model, state dictionary, locks, and
events. A call such as `self.run_water_command(...)` goes to the method in
`serial_controller.py` on that same runtime instance. There is one runtime per
controller process. The workflow classes are mixins, not separate controllers
to instantiate independently.

Importing `machine_flow` or constructing `MachineRuntime()` does not initialize
Firebase, open the camera/serial port, start a server, or spawn worker threads.
`start()` performs initialization and starts workers; `run()` also serves the
local API and calls `close()` on exit. `create_apps(runtime)` registers routes
without starting a server or hardware, which lets tests use Flask's test client.

Hardware and Firebase imports live inside the methods that need them. This
lets state tests and imports run on a development computer without Pi libraries.
The real service still needs the dependencies described in the main README.

The principal flows are:

```text
Camera motion -> material/visual inspection -> ESP32 sort -> saved item + totals
Green button -> finish event -> recycling worker -> batch reward QR
Blue button -> paused recycling + water_refill_requested -> kiosk water screen
Phone request in Firestore -> water worker -> point transaction -> ESP32 -> result
Reward QR claim -> rewards API -> Firebase transaction -> reset matching session
```

`rearm_for_next_item()` preserves the current customer's totals.
`reset_state()` clears them for a new customer. The green button only sets an
event; the recycling worker creates the reward after the current scan finishes.
The serial controller retains the rule that water commands are never retried
after a `DISPENSING` acknowledgement.

## Read logs and inspect state

Logs include time, severity, thread, source file, and line number:

```text
2026-09-07 10:30:00,000 INFO [recycling] detection.py:100 YOLO detection: ...
```

The recycling thread is named `recycling`; the refill thread is `water-refill`.
Messages logged inside an exception handler include the original traceback.
Start with the exception at the end of that traceback, then follow its file
and line number. Existing session/request IDs remain in the messages.

To save both normal messages and tracebacks while running in a terminal:

```sh
python3 -u machine_flow.py 2>&1 | tee machine-debug.log
```

`ECOREFILL_LOG_LEVEL` controls the standard logging level (default `INFO`).
`DEBUG` also exposes debug messages from dependencies that use Python logging.
If a service manager already runs the controller, read its logs rather than
starting a second copy that would compete for the camera and serial port.

Read the current machine state from a terminal on the Pi:

```sh
curl -s http://127.0.0.1:5000/api/machine/state | python3 -m json.tool
```

Check `phase`, `message`, `error`, `batchSessionId`, `sessionId`, and the item
totals together. The public server on port 5001 provides redemption and payment
routes; machine controls and water session routes belong to the local API.

The existing diagnostic files remain relative to the working directory:

- `captured_item.jpg`: captured scan image when that capture path is used.
- `detection_result.jpg`: most recent annotated detection.
- `sessions_log.txt`: item/session results and inspection details.
- Inspection samples: the directory set by the local inspection configuration.

Model and default credential paths also retain their existing working-directory
behavior, so launch from `ecorefill-pi`.

## Run checks without hardware

From the repository root, using a Python environment with Flask, Flask-CORS,
NumPy, and OpenCV installed:

```sh
python3 -m unittest discover -s ecorefill-pi -p 'test_*.py' -v
```

The tests use fake serial connections, camera/model objects, and Firebase
services. They do not connect to the live machine or modify real balances.
They cover session state, button guards, serial reconnect behavior, HTTP route
boundaries, startup cleanup, visual inspection, and payment rules. The visual
inspection integration test imports the controller directly rather than
extracting functions from source text.

To step through a focused test from `ecorefill-pi`:

```sh
python3 -m pdb -m unittest test_machine_runtime.SerialTests.test_disconnect_after_dispensing_never_resends
```

These checks do not validate physical camera timing, GPIO wiring, the ESP32
firmware, real dispensing, or live Firebase/tunnel connectivity. Verify those
on the Pi after transferring the refactor.
