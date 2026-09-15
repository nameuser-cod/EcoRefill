"""Standalone wiring check and command console; no camera/Firebase required."""

import argparse
import signal
import threading
import time

from machine.gpio_controller import ControllerSettings, GPIOController
from machine.gpio_hardware import create_hardware, prepare_pwm


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", help="Calibration JSON; defaults match gpio.example.json")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--prepare-pwm", action="store_true", help="Export PWM and grant gpio group access (sudo, once per boot)")
    mode.add_argument("--distance", action="store_true", help="Print fresh sensor readings; Ctrl+C exits")
    mode.add_argument("--command", help="Execute one command and exit")
    args = parser.parse_args()
    if args.prepare_pwm:
        print(f"Prepared {prepare_pwm()} channels 2 and 3.")
        return 0

    def terminated(*_):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, terminated)
    hardware = create_hardware()
    controller = GPIOController(
        hardware, ControllerSettings.from_file(args.config),
        emit=lambda message: print(message, flush=True),
    )
    worker = None

    def execute(command):
        ok, error = controller.execute(command)
        # BUSY/invalid/closed errors occur before the controller's normal output.
        if error and (error.startswith("INVALID_COMMAND") or error.endswith(("BUSY", "CLOSED"))):
            print(error, flush=True)
        return ok

    try:
        controller.open()
        if args.distance:
            while True:
                distance = hardware.distance_cm()
                print("NO ECHO" if distance is None else f"DISTANCE {distance:.1f} CM", flush=True)
                time.sleep(0.2)
        if args.command:
            return 0 if execute(args.command) else 1
        print("Commands: BOTTLE CAN REJECT RESET WATER_250 WATER_500 WATER_1000 QUIT", flush=True)
        while True:
            command = input("> ").strip().upper()
            if not command:
                continue
            if command in {"QUIT", "EXIT"}:
                break
            if command == "RESET":
                execute(command)
            elif worker is not None and worker.is_alive():
                print(f"ERROR {command} BUSY", flush=True)
            else:
                worker = threading.Thread(target=execute, args=(command,), name="gpio-command")
                worker.start()
    except (KeyboardInterrupt, EOFError):
        pass
    finally:
        controller.close()
        if worker is not None:
            worker.join()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
