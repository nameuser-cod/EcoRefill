"""Fresh edge-timed ultrasonic readings; serialize pings to avoid crosstalk."""

import threading
import time

from .weight_sensor import open_header

_PING_LOCK = threading.Lock()
_NEXT_PING_AT = 0.0


class UltrasonicEcho:
    def __init__(self, trig_gpio, echo_gpio):
        self.trig_gpio, self.echo_gpio = trig_gpio, echo_gpio
        self.io_lock = threading.RLock()
        # Pump-off writes must not wait for an ultrasonic echo/quiet interval.
        self.distance_lock = threading.RLock()
        self.echo_lock = threading.Lock()
        self.echo_done = threading.Event()
        self.armed_at = self.rise_at = self.width_ns = None

    def _echo_edge(self, chip, gpio, level, timestamp):
        with self.echo_lock:
            if self.armed_at is None or timestamp < self.armed_at:
                return
            if level == 1 and self.rise_at is None:
                self.rise_at = timestamp
            elif level == 0 and self.rise_at is not None:
                self.width_ns = timestamp - self.rise_at
                self.armed_at = None
                self.echo_done.set()

    def distance_cm(self):
        global _NEXT_PING_AT
        with self.distance_lock, _PING_LOCK:
            if self.handle is None:
                return None
            # Both the water and bin sensor share this quiet interval.
            delay = _NEXT_PING_AT - time.monotonic()
            if delay > 0:
                time.sleep(delay)
            try:
                return self._measure_distance_cm()
            finally:
                _NEXT_PING_AT = time.monotonic() + 0.06

    def _measure_distance_cm(self):
        if self.gpio.gpio_read(self.handle, self.echo_gpio):
            return None
        with self.echo_lock:
            self.echo_done.clear()
            self.rise_at = self.width_ns = None
            self.armed_at = time.monotonic_ns()
        try:
            self.gpio.tx_pulse(self.handle, self.trig_gpio, 10, 10, 0, 1)
            self.echo_done.wait(0.06)
            with self.echo_lock:
                width = self.width_ns
            if width is None or not 100_000 <= width <= 30_000_000:
                return None
            return width / 1_000_000_000 * 34300 / 2
        finally:
            with self.echo_lock:
                self.armed_at = None


class BinUltrasonicSensor(UltrasonicEcho):
    """Own only the bin sensor's GPIOs; never claim pump or servo pins."""

    def __init__(self, trig_gpio=16, echo_gpio=20):
        super().__init__(trig_gpio, echo_gpio)
        self.gpio = self.handle = self.callback = None
        self.trigger_claimed = False

    def open(self):
        import lgpio

        self.gpio = lgpio
        try:
            self.handle = open_header(lgpio)
            lgpio.gpio_claim_output(self.handle, self.trig_gpio, 0)
            self.trigger_claimed = True
            lgpio.gpio_claim_alert(self.handle, self.echo_gpio, lgpio.BOTH_EDGES)
            self.callback = lgpio.callback(
                self.handle, self.echo_gpio, lgpio.BOTH_EDGES, self._echo_edge,
            )
        except BaseException:
            self.close()
            raise

    def close(self):
        with self.distance_lock:
            try:
                if self.handle is not None and self.trigger_claimed:
                    self.gpio.gpio_write(self.handle, self.trig_gpio, 0)
            finally:
                try:
                    if self.callback is not None:
                        self.callback.cancel()
                finally:
                    if self.handle is not None:
                        self.gpio.gpiochip_close(self.handle)
                    self.handle = self.callback = None
                    self.trigger_claimed = False
