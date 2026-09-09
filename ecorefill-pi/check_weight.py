"""Standalone HX711 diagnostic for Pi 5; no camera, Firebase, or motors."""

import argparse
import math
from pathlib import Path
import statistics
import sys
import time


class HX711:
    """Channel A, gain 128. Userspace timing is checked, never guaranteed."""

    def __init__(self, gpio, handle, dout=5, sck=6):
        self.gpio, self.handle = gpio, handle
        self.dout, self.sck = dout, sck

    def reset(self):
        self.gpio.gpio_write(self.handle, self.sck, 1)
        try:
            time.sleep(0.001)  # Deliberate power-down resets serial framing.
        finally:
            self.gpio.gpio_write(self.handle, self.sck, 0)
        time.sleep(0.5)  # 400 ms settling time at 10 samples/second.

    def pulse(self):
        start = time.monotonic_ns()
        try:
            self.gpio.gpio_write(self.handle, self.sck, 1)
        finally:
            self.gpio.gpio_write(self.handle, self.sck, 0)
        # Include both calls in the conservative bound on the high period.
        # Never sleep while SCK is high: >60 us powers down the HX711.
        if time.monotonic_ns() - start > 50_000:
            raise RuntimeError(
                "Clock timing exceeded 50 us. Stop other busy programs and retry."
            )

    def read_raw(self, timeout=2.0):
        deadline = time.monotonic() + timeout
        while self.gpio.gpio_read(self.handle, self.dout):
            if time.monotonic() >= deadline:
                raise TimeoutError(
                    "HX711 not ready: check power, GND, and DT/SCK pin labels."
                )
            time.sleep(0.001)
        value = 0
        for _ in range(24):
            self.pulse()
            value = (value << 1) | self.gpio.gpio_read(self.handle, self.dout)
        self.pulse()  # 25th pulse selects channel A, gain 128, for next reading.
        if not self.gpio.gpio_read(self.handle, self.dout):
            raise RuntimeError("DT stayed low after reading. Check DT/SCK wiring.")
        if value in (0x800000, 0x7FFFFF):
            raise RuntimeError("ADC saturated. Remove load and check load-cell wires.")
        return value - (1 << 24) if value & (1 << 23) else value

    def sample(self, count=15):
        values = [self.read_raw() for _ in range(count)]
        return statistics.median(values), max(values) - min(values)


def open_header(gpio):
    """Find RP1 by label: Pi 5 kernels have used both gpiochip4 and gpiochip0."""
    errors = []
    for device in sorted(Path("/dev").glob("gpiochip[0-9]*")):
        handle = None
        selected = False
        try:
            handle = gpio.gpiochip_open(int(device.name.removeprefix("gpiochip")))
            info = gpio.gpio_get_chip_info(handle)
            label = info[3]
            if isinstance(label, bytes):
                label = label.decode()
            if label == "pinctrl-rp1":
                selected = True
                print(f"Using {device} ({label})", flush=True)
                return handle
        except gpio.error as error:
            errors.append(f"{device}: {error}")
        finally:
            if handle is not None and not selected:
                gpio.gpiochip_close(handle)
    raise RuntimeError(
        "Could not access the Pi 5 RP1 GPIO chip. Run this on the Pi, using an "
        "account with GPIO access. " + "; ".join(errors)
    )


def calibration_factor(zero, loaded, grams, noise):
    if not math.isfinite(grams) or not 0 < grams < 1000:
        raise ValueError("Use a known mass greater than 0 and below 1000 grams.")
    if abs(loaded - zero) <= max(1, 10 * noise):
        raise ValueError(
            "Load change is too small compared with noise. Check mounting, "
            "let the platform settle, and retry."
        )
    return (loaded - zero) / grams


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--calibrate", action="store_true",
                        help="tare, measure a known mass, then display grams")
    args = parser.parse_args()
    try:
        import lgpio
    except ImportError:
        print("On the Pi run: sudo apt install python3-lgpio\n"
              "Then run this script with /usr/bin/python3.", file=sys.stderr)
        return 1

    handle = None
    clock_claimed = False
    try:
        handle = open_header(lgpio)
        lgpio.gpio_claim_input(handle, 5, lgpio.SET_PULL_UP)
        lgpio.gpio_claim_output(handle, 6, 0)
        clock_claimed = True
        sensor = HX711(lgpio, handle)
        sensor.reset()
        print("DT=GPIO5 (pin 29), SCK=GPIO6 (pin 31). Ctrl+C exits.", flush=True)
        zero, factor = 0, None
        if args.calibrate:
            input("Remove all items from the platform, let it settle, then press Enter: ")
            sensor.read_raw()  # Discard the conversion buffered before the prompt.
            zero, empty_noise = sensor.sample()
            print(f"Empty reading: {zero}; spread: {empty_noise} raw counts")
            grams = float(input("Enter the known calibration mass in grams (e.g. 100): "))
            if not math.isfinite(grams) or not 0 < grams < 1000:
                raise ValueError("Calibration mass must be greater than 0 and below 1000 g.")
            input("Place that mass on the platform, let it settle, then press Enter: ")
            sensor.read_raw()
            loaded, loaded_noise = sensor.sample()
            factor = calibration_factor(zero, loaded, grams, max(empty_noise, loaded_noise))
            print(f"Offset: {zero}; calibration factor: {factor:.8f} counts/gram")
            print("Save these numbers. Calibration is for this session only.")
            print("Remove the mass: the display should return close to 0 g.")
        else:
            print("RAW COUNTS, not grams. Place and remove a light object to check response.")
        while True:
            value, spread = sensor.sample(5)
            if factor is None:
                print(f"Raw: {value:12.0f}   spread: {spread}", flush=True)
            else:
                print(f"Weight: {(value - zero) / factor:9.1f} g", flush=True)
    except (KeyboardInterrupt, EOFError):
        print("\nStopped.")
        return 0
    except (lgpio.error, OSError, RuntimeError, ValueError) as error:
        print(f"Weight check failed: {error}", file=sys.stderr)
        return 1
    finally:
        if handle is not None:
            try:
                if clock_claimed:
                    lgpio.gpio_write(handle, 6, 0)
            finally:
                lgpio.gpiochip_close(handle)


if __name__ == "__main__":
    raise SystemExit(main())
