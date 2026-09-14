"""Check Pi 5 PWM routing and move MG996Rs without the camera or sorter logic."""

import argparse
import signal
import subprocess
import time

from machine.gpio_hardware import PiGPIOHardware, find_pwm_chip
from machine.gpio_controller import ControllerSettings


SERVO_PINS = {"gate": (18, 12, 2), "sort": (19, 35, 3)}


def check_routing(names):
    """Read the live pin mux; an exported PWM channel alone is insufficient."""
    valid = True
    for name in names:
        gpio, physical, channel = SERVO_PINS[name]
        expected = f"PWM0_CHAN{channel}"
        print(f"{name}: GPIO{gpio}, physical pin {physical}, expected {expected}", flush=True)
        try:
            result = subprocess.run(
                ["pinctrl", "get", str(gpio)], capture_output=True, text=True,
                timeout=5, check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            print(f"Cannot verify pin routing: {error}. Run pinctrl get {gpio} on the Pi.", flush=True)
            valid = False
            continue
        print((result.stdout + result.stderr).strip(), flush=True)
        if result.returncode or expected not in result.stdout:
            valid = False
            print(
                f"GPIO{gpio} is not confirmed as {expected}. Check dtoverlay=pwm-2chan "
                "under [all], reboot, and stop programs/overlays using these pins.",
                flush=True,
            )
    return valid


def show_pwm_state(chip, name):
    channel = SERVO_PINS[name][2]
    path = chip / f"pwm{channel}"
    if not path.exists():
        print(f"{path} is not exported. Run sudo python3 direct_gpio.py --prepare-pwm.", flush=True)
        return
    values = " ".join(
        f"{key}={(path / key).read_text().strip()}"
        for key in ("enable", "period", "duty_cycle", "polarity")
    )
    print(f"{name} {path}: {values}", flush=True)


def exercise_servo(hardware, name, report, settings=None):
    settings = settings or ControllerSettings()
    if name == "gate":
        center, low, high = settings.gate_center_us, settings.gate_accept_us, settings.gate_reject_us
    else:
        center, low, high = settings.sort_center_us, settings.sort_bottle_us, settings.sort_can_us
    try:
        for pulse in (center, high, low, center):
            angle = round((pulse - 500) * 180 / 1900)
            hardware.servo(name, pulse)
            print(f"{name}: nominal {angle} degrees ({pulse} us at 50 Hz); observe movement now.", flush=True)
            report(name)
            time.sleep(1)
    finally:
        # Only the selected servo receives pulses; release it even on Ctrl+C.
        hardware.servos[name].close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--servo", choices=("gate", "sort", "both"), default="both")
    parser.add_argument("--config", help="Use the same servo calibration JSON as the machine app")
    parser.add_argument("--diagnose-only", action="store_true", help="Read pin routing and PWM state without moving servos")
    args = parser.parse_args()
    names = ("gate", "sort") if args.servo == "both" else (args.servo,)

    def terminate(*_):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, terminate)
    hardware = None
    try:
        routing_ok = check_routing(names)
        chip = find_pwm_chip()
        print(f"Header PWM controller: {chip} -> {(chip / 'device/of_node').resolve()}", flush=True)
        for name in names:
            show_pwm_state(chip, name)
        if args.diagnose_only:
            return 0 if routing_ok else 1
        if not routing_ok:
            print("No motion test performed: resolve pin routing first.", flush=True)
            return 1
        settings = ControllerSettings.from_file(args.config)
        print("Stop the machine app and detach servo linkages before this test. Relays stay OFF.", flush=True)
        hardware = PiGPIOHardware()
        hardware.open()
        hardware.all_off()
        for name in names:
            exercise_servo(hardware, name, lambda selected: show_pwm_state(chip, selected), settings)
        print(
            "Test finished. The reported values are software settings, not proof of an "
            "electrical waveform or motor movement.", flush=True,
        )
        return 0
    except KeyboardInterrupt:
        return 130
    except (OSError, RuntimeError) as error:
        print(f"Servo test failed: {error}", flush=True)
        return 1
    finally:
        if hardware is not None:
            hardware.close()


if __name__ == "__main__":
    raise SystemExit(main())
