"""One center-mounted bin sensor, persistent fullness latch and owner alerts."""

from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import math
import os
import time
import uuid

from .config import MACHINE_ID, GREEN_BUTTON_GPIO, BLUE_BUTTON_GPIO
from .diagnostics import log
from .ultrasonic import BinUltrasonicSensor


@dataclass(frozen=True)
class BinSettings:
    enabled: bool = True
    trig_gpio: int = 16  # Physical pin 36
    echo_gpio: int = 20  # Physical pin 38, through voltage divider
    full_distance_cm: float = 10.0
    clear_distance_cm: float = 20.0
    confirm_readings: int = 3
    poll_seconds: float = 2.0

    def __post_init__(self):
        from .gpio_hardware import CONTROL_PINS

        reserved = CONTROL_PINS | {GREEN_BUTTON_GPIO, BLUE_BUTTON_GPIO, 5, 6}
        if type(self.enabled) is not bool:
            raise ValueError("Bin enabled must be true or false.")
        if any(type(pin) is not int or not 0 <= pin <= 27 or pin in reserved
               for pin in (self.trig_gpio, self.echo_gpio)) or self.trig_gpio == self.echo_gpio:
            raise ValueError("Bin GPIOs must be distinct, free BCM pins (not buttons, HX711 or controller pins).")
        for value in (self.full_distance_cm, self.clear_distance_cm, self.poll_seconds):
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
                raise ValueError("Bin distances and polling interval must be finite positive numbers.")
        if not 2 <= self.full_distance_cm < self.clear_distance_cm <= 400:
            raise ValueError("Bin distances must satisfy 2 <= full < clear <= 400 cm.")
        if type(self.confirm_readings) is not int or not 2 <= self.confirm_readings <= 100:
            raise ValueError("Bin confirm_readings must be an integer from 2 to 100.")
        if not 0.2 <= self.poll_seconds <= 60:
            raise ValueError("Bin poll_seconds must be between 0.2 and 60.")

    @classmethod
    def from_file(cls, path=None):
        path = path or os.getenv("ECOREFILL_BIN_CONFIG")
        if not path:
            return cls()
        with open(path, encoding="utf-8") as source:
            return cls(**json.load(source))


class BinFullMonitor:
    def __init__(self, journal, settings, machine_id=MACHINE_ID):
        self.journal, self.settings, self.machine_id = journal, settings, machine_id
        saved = dict(journal.entries("bin_state")).get(machine_id, {})
        self.full = saved.get("full", False)
        self.readings = 0

    def observe(self, distance, now=None):
        valid = (not isinstance(distance, bool) and isinstance(distance, (int, float))
                 and math.isfinite(distance) and 2 <= distance <= 400)
        qualifies = valid and (distance >= self.settings.clear_distance_cm if self.full
                               else distance <= self.settings.full_distance_cm)
        self.readings = self.readings + 1 if qualifies else 0
        if self.readings < self.settings.confirm_readings:
            return
        full = not self.full
        state = json.dumps({"full": full})
        # Commit the latch and queued alert together. A restart cannot lose or
        # repeat this full-bin episode; network retries run on another worker.
        with closing(self.journal.connect()) as db, db:
            db.execute("INSERT OR REPLACE INTO journal VALUES ('bin_state', ?, ?)",
                       (self.machine_id, state))
            if full:
                event_id = "bin_full_" + uuid.uuid4().hex
                event = {"machineId": self.machine_id, "distanceCm": distance,
                         "detectedAt": time.time() if now is None else now}
                db.execute("INSERT INTO journal VALUES ('bin_alert', ?, ?)",
                           (event_id, json.dumps(event, allow_nan=False)))
        self.full, self.readings = full, 0


class BinMonitoring:
    def bin_monitor_worker(self):
        settings = self.bin_settings
        monitor = BinFullMonitor(self.journal, settings)
        try:
            while not self.shutdown_event.is_set():
                try:
                    if self.bin_sensor is None:
                        sensor = BinUltrasonicSensor(settings.trig_gpio, settings.echo_gpio)
                        sensor.open()
                        self.bin_sensor = sensor
                        log(f"Bin ultrasonic ready on TRIG={settings.trig_gpio}, ECHO={settings.echo_gpio}.")
                    monitor.observe(self.bin_sensor.distance_cm())
                except Exception as error:
                    monitor.readings = 0
                    log("Bin sensor check will retry:", error)
                    if self.bin_sensor is not None:
                        try:
                            self.bin_sensor.close()
                        except Exception as close_error:
                            log("Could not close bin sensor:", close_error)
                        self.bin_sensor = None
                    self.shutdown_event.wait(5)
                self.shutdown_event.wait(settings.poll_seconds)
        finally:
            if self.bin_sensor is not None:
                self.bin_sensor.close()

    def sync_bin_alerts(self):
        from firebase_admin import firestore

        for event_id, event in self.journal.entries("bin_alert"):
            if self.shutdown_event.is_set():
                return
            if self.db is None:
                raise RuntimeError("Firebase unavailable; bin alert saved locally.")
            alert_ref = self.db.collection("machine_alerts").document(event_id)
            receipt_ref = self.db.collection("machine_sensor_events").document(event_id)

            @firestore.transactional
            def publish(tx):
                # A permanent receipt also prevents a retry recreating an alert
                # that the owner has already resolved/deleted.
                if receipt_ref.get(transaction=tx, timeout=5, retry=None).exists:
                    return
                tx.set(alert_ref, {
                    "machineId": event["machineId"], "alertType": "bin_full", "status": "unread",
                    "message": "The recycling bin is full. Please empty the bin.",
                    "distanceCm": event["distanceCm"],
                    "createdAt": datetime.fromtimestamp(event["detectedAt"], timezone.utc),
                })
                tx.set(receipt_ref, {"machineId": event["machineId"], "createdAt": firestore.SERVER_TIMESTAMP})

            publish(self.db.transaction())
            self.journal.delete("bin_alert", event_id)
