# EcoRefill Raspberry Pi controller

Run these commands from the `ecorefill-pi` directory using the machine's Python
environment:

```bash
python3 machine_flow.py
```

## Where files belong

```text
ecorefill-pi/
├── machine_flow.py       # Controller launcher
├── run_tests.py          # Test runner with automatic path discovery
├── machine/              # Runtime, hardware, detection, payments, and notifications
├── tools/                # Standalone wiring, servo, relay, button, and scale checks
├── tests/                # Regression tests and fake hardware/cloud helpers
├── docs/                 # Setup, calibration, troubleshooting, and recovery guides
├── config/               # Example GPIO and visual inspection configuration
├── models/               # Trained model files
├── kiosk-dist/           # Built kiosk frontend
└── data/                 # Persistent upload, refill, reward, and notification queues
```

Keep local `gpio.local.json`, `inspection.local.json`, and Firebase credentials
in their configured locations. The existing model and queue paths are retained.

## Machine online status

The controller updates `machines/{MACHINE_ID}` with `machineStatus: "Online"`
and a server timestamp in `lastHeartbeatAt` every 30 seconds, including while
idle. The owner dashboard, owner profile, and machine finder show **Offline**
after 90 seconds without a heartbeat (checked every 5 seconds), including after
power loss or an internet outage. The next successful heartbeat restores
**Online**. A saved Online status without a heartbeat is treated as Offline.

Install the updated frontend and complete `machine/` package, then restart
`machine_flow.py` on the Pi. Its configured `MACHINE_ID` must match an existing
Firestore machine document. Presence uses the existing Firebase Admin
credentials and does not require a scheduled Cloud Function.

## Run tests

```bash
python3 run_tests.py
python3 run_tests.py test_machine_runtime.py
python3 run_tests.py test_push_notifications.py
```

From the application repository root, use `python3 ecorefill-pi/run_tests.py`.
The runner finds `tests/` automatically, so it also works when invoked by its
absolute path from another directory. Its tests use fake hardware and cloud
services; they do not operate the live machine.

## Hardware diagnostics

Stop the machine controller before running diagnostics that claim its pins.
Use Python module commands from `ecorefill-pi`:

```bash
sudo python3 -m tools.direct_gpio --prepare-pwm
python3 -m tools.direct_gpio --config gpio.local.json --distance
python3 -m tools.check_servos --diagnose-only
python3 -m tools.check_buttons
/usr/bin/python3 -m tools.check_weight --calibrate
```

Example configurations can be copied into the existing local paths:

```bash
cp config/gpio.example.json gpio.local.json
cp config/inspection.example.json inspection.local.json
```

## Guides

- [Controller debugging and file map](docs/DEBUGGING.md)
- [GPIO wiring and calibration](docs/DIRECT_GPIO.md)
- [HX711 weight sensor](docs/WEIGHT_SENSOR.md)
- [Visual inspection](docs/INSPECTION.md)
- [Offline recovery and local kiosk](docs/LOW_CONNECTIVITY.md)
- [Dispensing time and partial refunds](docs/TIMED_REFUNDS.md)
- [Public tunnel and phone registration](docs/CLOUDFLARE_TUNNEL.md)
- [Phone notification installation](docs/PHONE_NOTIFICATIONS.md)

When updating the Pi, copy `machine_flow.py` and the complete `machine/` package.
Copy `tools/`, `tests/`, `run_tests.py`, `docs/`, and `config/` to include the
diagnostics, test runner, and guides. Preserve the existing local settings,
credentials, model files, and `data/` directory.
