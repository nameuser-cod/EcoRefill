"""HX711 acquisition for the Pi 5 diagnostic and recycling controller."""

import math
from pathlib import Path
import statistics
import threading
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


class WeightReadingError(RuntimeError):
    def __init__(self, status, message, reading=None):
        super().__init__(message)
        self.status = status
        self.reading = reading or {}


class CalibratedScale:
    """Own GPIO and acquire a fresh, bounded sample window for each item."""

    def __init__(self, offset, factor, max_spread_g=3.0):
        if not math.isfinite(offset) or not -(1 << 23) < offset < (1 << 23):
            raise ValueError("HX711 offset must be a finite 24-bit reading")
        if not math.isfinite(factor) or factor == 0:
            raise ValueError("HX711 calibration factor must be finite and nonzero")
        if not math.isfinite(max_spread_g) or max_spread_g <= 0:
            raise ValueError("HX711 maximum spread must be finite and positive")
        self.offset, self.factor = offset, factor
        self.max_spread_g = max_spread_g
        self.gpio = self.handle = self.sensor = None
        self.clock_claimed = False
        self.needs_reset = False
        self.lock = threading.Lock()

    def open(self):
        import lgpio

        self.gpio = lgpio
        try:
            self.handle = open_header(lgpio)
            lgpio.gpio_claim_input(self.handle, 5, lgpio.SET_PULL_UP)
            lgpio.gpio_claim_output(self.handle, 6, 0)
            self.clock_claimed = True
            self.sensor = HX711(lgpio, self.handle)
            self.sensor.reset()
        except BaseException:
            self.close()
            raise

    def read_weight(self):
        with self.lock:
            if self.sensor is None:
                raise WeightReadingError("unavailable", "Weight sensor is unavailable")
            try:
                if self.needs_reset:
                    self.sensor.reset()
                    self.needs_reset = False
                deadline = time.monotonic() + 4.0

                def fresh_raw():
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise TimeoutError("Weight measurement timed out")
                    value = self.sensor.read_raw(timeout=min(2.0, remaining))
                    if time.monotonic() > deadline:
                        raise TimeoutError("Weight measurement timed out")
                    return value

                # HX711 holds an unread conversion. Discard it so an empty or
                # previous-item reading never enters this item's sample window.
                fresh_raw()
                values = [fresh_raw() for _ in range(10)]
                grams = (statistics.median(values) - self.offset) / self.factor
                spread = (max(values) - min(values)) / abs(self.factor)
                if not math.isfinite(grams) or not math.isfinite(spread):
                    raise WeightReadingError("invalid", "Invalid weight reading")
                reading = {"grams": grams, "spread_g": spread, "samples": len(values),
                           "measured_at": time.time()}
                if spread > self.max_spread_g:
                    raise WeightReadingError("unstable", "Weight did not settle", reading)
                if grams <= 0:
                    raise WeightReadingError("invalid", "No positive item weight detected", reading)
                return reading
            except WeightReadingError:
                raise
            except Exception as error:
                # Timing violations can leave serial framing/gain selection
                # incomplete. Reset before the next item; never reuse a sample.
                self.needs_reset = True
                raise WeightReadingError("unavailable", str(error)) from error

    def close(self):
        with self.lock:
            if self.handle is not None:
                try:
                    if self.clock_claimed:
                        self.gpio.gpio_write(self.handle, 6, 0)
                finally:
                    self.gpio.gpiochip_close(self.handle)
                    self.handle = self.sensor = None
                    self.clock_claimed = False

