"""Check physical button inputs without starting the camera, Firebase, or motors."""

import sys
import time

from machine.config import BLUE_BUTTON_GPIO, GREEN_BUTTON_GPIO
from machine.diagnostics import configure_logging
from machine.runtime import MachineRuntime


def monitor_inputs(buttons):
    """Poll electrical levels independently of GPIO edge callbacks."""
    previous = None
    last_report = float("-inf")
    while True:
        levels = tuple(int(button.pin.state) for _, button in buttons)
        now = time.monotonic()
        if levels != previous or now - last_report >= 1:
            print(
                "PIN LEVELS: " + " | ".join(
                    f"{color}={level} ({'released' if level else 'PRESSED'})"
                    for (color, _), level in zip(buttons, levels)
                ),
                flush=True,
            )
            previous = levels
            last_report = now
        time.sleep(0.05)


def main():
    configure_logging()
    machine = MachineRuntime()
    # Use the controller's exact GPIO setup, but report presses independently
    # of session totals and machine phases.
    machine.request_finish_recycling_session = lambda: print("GREEN pressed", flush=True)
    machine.request_water_refill = lambda: print("BLUE pressed", flush=True)

    print(f"Python: {sys.executable}", flush=True)
    print(
        f"Inputs: GREEN BCM {GREEN_BUTTON_GPIO}, BLUE BCM {BLUE_BUTTON_GPIO}. "
        "Each button connects its GPIO input to GND when pressed.",
        flush=True,
    )
    try:
        machine.initialize_buttons()
        available = []
        for color, button in (("GREEN", machine.green_button), ("BLUE", machine.blue_button)):
            if button is None:
                print(f"{color}: unavailable; see initialization error above.", flush=True)
                continue
            available.append((color, button))
            print(
                f"{color}: {'PRESSED' if button.is_pressed else 'released'} "
                f"({type(button.pin_factory).__name__})",
                flush=True,
            )
            button.when_released = lambda color=color: print(f"{color} released", flush=True)

        if not available:
            return 1

        print(
            "Hold each button for one second, then release. "
            "PIN LEVELS should change from 1 to 0 while held. Ctrl+C exits.",
            flush=True,
        )
        monitor_inputs(available)
    except KeyboardInterrupt:
        return 0
    finally:
        machine.close()


if __name__ == "__main__":
    raise SystemExit(main())
