"""Check physical button inputs without starting the camera, Firebase, or motors."""

import signal
import sys

from machine.config import BLUE_BUTTON_GPIO, GREEN_BUTTON_GPIO
from machine.diagnostics import configure_logging
from machine.runtime import MachineRuntime


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
            available.append(button)
            print(
                f"{color}: {'PRESSED' if button.is_pressed else 'released'} "
                f"({type(button.pin_factory).__name__})",
                flush=True,
            )
            button.when_released = lambda color=color: print(f"{color} released", flush=True)

        if not available:
            return 1

        print("Press and release each button. Ctrl+C exits.", flush=True)
        while True:
            signal.pause()
    except KeyboardInterrupt:
        return 0
    finally:
        machine.close()


if __name__ == "__main__":
    raise SystemExit(main())
