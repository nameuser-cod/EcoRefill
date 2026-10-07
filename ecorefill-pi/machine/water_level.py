"""Independent gallon-level sensing; cloud publication uses the heartbeat worker."""

from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import statistics
import time

from .config import GREEN_BUTTON_GPIO, BLUE_BUTTON_GPIO
from .diagnostics import log
from .ultrasonic import WaterLevelUltrasonicSensor


@dataclass(frozen=True)
class WaterLevelSettings:
    enabled: bool = False
    trig_gpio: int = 12  # Physical pin 32
    echo_gpio: int = 13  # Physical pin 33, through voltage divider
    full_distance_cm: float = 20.0
    first_distance_cm: float = 21.0
    first_percent: float = 85.0
    empty_distance_cm: float = 38.0
    confirm_readings: int = 3
    poll_seconds: float = 2.0

    def __post_init__(self):
        from .gpio_hardware import CONTROL_PINS

        reserved = CONTROL_PINS | {GREEN_BUTTON_GPIO, BLUE_BUTTON_GPIO, 5, 6}
        if type(self.enabled) is not bool:
            raise ValueError("Water-level enabled must be true or false.")
        if any(type(pin) is not int or not 0 <= pin <= 27 or pin in reserved
               for pin in (self.trig_gpio, self.echo_gpio)) or self.trig_gpio == self.echo_gpio:
            raise ValueError("Water-level GPIOs must be distinct, free BCM pins.")
        for value in (self.full_distance_cm, self.first_distance_cm, self.first_percent,
                      self.empty_distance_cm, self.poll_seconds):
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise ValueError("Water-level calibration and polling values must be finite numbers.")
        if not 0 < self.full_distance_cm < self.first_distance_cm < self.empty_distance_cm <= 500:
            raise ValueError("Water-level distances must satisfy 0 < full < first < empty <= 500 cm.")
        if not 0 < self.first_percent < 100:
            raise ValueError("Water-level first_percent must be between 0 and 100.")
        if type(self.confirm_readings) is not int or not 2 <= self.confirm_readings <= 100:
            raise ValueError("Water-level confirm_readings must be an integer from 2 to 100.")
        if not 0.2 <= self.poll_seconds <= 60:
            raise ValueError("Water-level poll_seconds must be between 0.2 and 60.")

    def validate_bin_pins(self, bin_settings):
        if self.enabled and bin_settings.enabled and (
            {self.trig_gpio, self.echo_gpio} & {bin_settings.trig_gpio, bin_settings.echo_gpio}
        ):
            raise ValueError("Water-level GPIOs conflict with the bin sensor.")

    @classmethod
    def from_file(cls, path=None):
        path = path or os.getenv("ECOREFILL_WATER_LEVEL_CONFIG")
        if not path:
            path = Path(__file__).resolve().parents[1] / "water-level.local.json"
            if not path.exists():
                return cls()
        with open(path, encoding="utf-8") as source:
            return cls(**json.load(source))


class WaterLevelMonitor:
    def __init__(self, settings):
        self.settings = settings
        self.distances = deque(maxlen=settings.confirm_readings)
        self.status = None

    def percentage(self, distance):
        s = self.settings
        if distance is None or distance <= s.full_distance_cm:
            return 100
        if distance < s.first_distance_cm:
            value = 100 - (100 - s.first_percent) * (
                distance - s.full_distance_cm
            ) / (s.first_distance_cm - s.full_distance_cm)
        else:
            value = s.first_percent * (s.empty_distance_cm - distance) / (
                s.empty_distance_cm - s.first_distance_cm
            )
        return round(max(0, min(100, value)))

    def observe(self, distance, now=None):
        if distance is None:
            status = "no_echo_assumed_full"
        elif (isinstance(distance, bool) or not isinstance(distance, (int, float))
              or not math.isfinite(distance) or not 0 < distance <= 600):
            self.distances.clear()
            self.status = None
            return self.reading(None, None, "invalid", now)
        elif distance <= self.settings.full_distance_cm:
            status = "blind_zone_assumed_full"
        else:
            status = "measured"
        if self.status != status:
            self.distances.clear()
        self.status = status
        self.distances.append(distance)
        if len(self.distances) < self.settings.confirm_readings:
            return None
        distance = None if distance is None else statistics.median(self.distances)
        return self.reading(self.percentage(distance), distance, status, now)

    @staticmethod
    def reading(percent, distance, status, now=None):
        return {"waterLevel": percent, "waterDistanceCm": distance, "waterLevelStatus": status,
                "waterLevelUpdatedAt": datetime.fromtimestamp(time.time() if now is None else now, timezone.utc)}


class WaterLevelMonitoring:
    def get_water_level_fields(self):
        if not self.water_level_settings.enabled:
            return {}
        with self.state_lock:
            if self.water_level_reading is None:
                return {"waterLevel": None, "waterDistanceCm": None,
                        "waterLevelStatus": "starting", "waterLevelUpdatedAt": None}
            reading = dict(self.water_level_reading)
            max_age = max(15, 3 * self.water_level_settings.poll_seconds * self.water_level_settings.confirm_readings)
            if time.monotonic() - self.water_level_observed_at > max_age:
                reading.update(waterLevel=None, waterDistanceCm=None, waterLevelStatus="stale")
            return reading

    def _save_water_level(self, reading):
        with self.state_lock:
            self.water_level_reading = reading
            self.water_level_observed_at = time.monotonic()

    def water_level_worker(self):
        settings = self.water_level_settings
        monitor = WaterLevelMonitor(settings)
        try:
            while not self.shutdown_event.is_set():
                try:
                    if self.water_level_sensor is None:
                        sensor = WaterLevelUltrasonicSensor(settings.trig_gpio, settings.echo_gpio)
                        sensor.open()
                        self.water_level_sensor = sensor
                        log(f"Gallon sensor ready on TRIG={settings.trig_gpio}, ECHO={settings.echo_gpio}.")
                    reading = monitor.observe(self.water_level_sensor.distance_cm())
                    if reading is not None:
                        self._save_water_level(reading)
                except Exception as error:
                    self._save_water_level(monitor.reading(None, None, "unavailable"))
                    monitor = WaterLevelMonitor(settings)
                    log("Water-level sensor check will retry:", error)
                    if self.water_level_sensor is not None:
                        try:
                            self.water_level_sensor.close()
                        except Exception as close_error:
                            log("Could not close water-level sensor:", close_error)
                        self.water_level_sensor = None
                    self.shutdown_event.wait(5)
                self.shutdown_event.wait(settings.poll_seconds)
        finally:
            if self.water_level_sensor is not None:
                self.water_level_sensor.close()
