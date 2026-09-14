"""Measure real servo PWM edges through a temporary GPIO16 loopback jumper.

Stop the machine app and disconnect servo signals. Jumper physical pin 12
(gate) or 35 (sort) to physical pin 36 (GPIO16 input). No external voltage.
"""

import argparse
from collections import deque
from contextlib import ExitStack
import signal
import statistics
import threading
import time

from check_servos import check_routing
from machine.gpio_hardware import PiGPIOHardware


def measure_edges(edges, expected_us):
    """Use edge timestamp differences, independent of callback delivery time."""
    widths, periods = [], []
    rise = previous_rise = None
    for level, timestamp in edges:
        if level == 1:
            if previous_rise is not None:
                periods.append((timestamp - previous_rise) / 1000)
            rise = previous_rise = timestamp
        elif level == 0 and rise is not None:
            widths.append((timestamp - rise) / 1000)
            rise = None
    if len(widths) < 5 or len(periods) < 5:
        return False, f"INSUFFICIENT EDGES: {len(widths)} complete pulses received"
    width = statistics.median(widths)
    period = statistics.median(periods)
    if period <= 0:
        return False, "INVALID EDGE TIMESTAMPS"
    good_widths = sum(abs(value - expected_us) <= 150 for value in widths)
    good_periods = sum(abs(value - 20000) <= 2000 for value in periods)
    passed = good_widths / len(widths) >= 0.8 and good_periods / len(periods) >= 0.8
    status = "PASS" if passed else "TIMING MISMATCH"
    return passed, (
        f"{status}: requested {expected_us} us; measured {width:.0f} us, "
        f"{1_000_000 / period:.1f} Hz; {len(widths)} pulses"
    )


class EdgeCapture:
    def __init__(self):
        self.lock = threading.Lock()
        self.edges = deque(maxlen=512)

    def callback(self, chip, gpio, level, timestamp):
        if level in (0, 1):
            with self.lock:
                self.edges.append((level, timestamp))

    def clear(self):
        with self.lock:
            self.edges.clear()

    def snapshot(self):
        with self.lock:
            return list(self.edges)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--servo", choices=("gate", "sort"), default="gate")
    args = parser.parse_args()

    def terminate(*_):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, terminate)
    try:
        if not check_routing((args.servo,)):
            return 1
        with ExitStack() as cleanup:
            hardware = PiGPIOHardware()
            cleanup.callback(hardware.close)
            hardware.open()
            hardware.all_off()
            gpio = hardware.gpio
            capture = EdgeCapture()
            gpio.gpio_claim_alert(hardware.handle, 16, gpio.BOTH_EDGES, gpio.SET_PULL_DOWN)
            callback = gpio.callback(hardware.handle, 16, gpio.BOTH_EDGES, capture.callback)
            cleanup.callback(callback.cancel)
            passed = True
            for pulse in (1500, 1300, 1700):
                hardware.servo(args.servo, pulse)
                time.sleep(0.1)  # Let the previous pulse setting and notifications settle.
                capture.clear()
                time.sleep(0.6)
                ok, message = measure_edges(capture.snapshot(), pulse)
                print(message, flush=True)
                passed = passed and ok
            print(
                "PWM pulse timing confirmed at the GPIO16 input. This does not measure signal voltage or servo power."
                if passed else
                "PWM not confirmed. Check the temporary jumper; otherwise investigate the Pi output/edge capture.",
                flush=True,
            )
            return 0 if passed else 1
    except KeyboardInterrupt:
        return 130
    except Exception as error:
        print(f"PWM measurement failed: {error}", flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
