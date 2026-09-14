"""Direct Pi sorter/dispenser; one operation at a time, RESET can interrupt it."""

from dataclasses import dataclass, fields
import json
import math
import threading
import time


@dataclass(frozen=True)
class ControllerSettings:
    # Nominal angles use the original 500-2400 us range for 0-180 degrees.
    # Physical angles depend on the servo; calibrate with the linkage detached.
    gate_center_us: int = 1450
    gate_accept_us: int = 500
    gate_reject_us: int = 2400
    sort_center_us: int = 1450
    sort_bottle_us: int = 975  # 45 degrees.
    sort_can_us: int = 2400
    move_seconds: float = 0.7
    drop_seconds: float = 1.5
    water_250_seconds: float = 25.0
    water_500_seconds: float = 30.0
    water_1000_seconds: float = 45.0
    bottle_wait_seconds: float = 30.0
    trigger_distance_cm: float = 10.0
    remove_distance_cm: float = 14.0

    def __post_init__(self):
        for field in fields(self):
            value = getattr(self, field.name)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise ValueError(f"{field.name} must be a finite number.")
            if field.name.endswith("_us"):
                if not 500 <= value <= 2500:
                    raise ValueError(f"{field.name} must be between 500 and 2500.")
            elif not 0 < value <= 60:
                raise ValueError(f"{field.name} must be greater than 0 and at most 60.")
        if self.trigger_distance_cm >= self.remove_distance_cm:
            raise ValueError("Removal distance must exceed detection distance.")

    @classmethod
    def from_file(cls, path=None):
        if not path:
            return cls()
        with open(path, encoding="utf-8") as source:
            return cls(**json.load(source))


class OperationError(Exception):
    pass


class GPIOController:
    def __init__(self, hardware, settings=None, emit=None):
        self.hardware = hardware
        self.settings = settings or ControllerSettings()
        self.emit = emit or (lambda message: None)
        self.cancel = threading.Event()
        self.state_lock = threading.Lock()
        self.operation_lock = threading.Lock()
        self.reset_pending = False
        self.closed = False

    def open(self):
        self.hardware.open()
        try:
            self.hardware.all_off()
            self._center()
        except BaseException:
            self.close()
            raise

    def _center(self):
        self.hardware.servo("gate", self.settings.gate_center_us)
        self.hardware.servo("sort", self.settings.sort_center_us)

    def _check_cancel(self):
        if self.cancel.is_set():
            raise OperationError("CANCELLED")

    def _wait(self, seconds):
        if self.cancel.wait(seconds):
            raise OperationError("CANCELLED")

    def _distance(self):
        self._check_cancel()
        value = self.hardware.distance_cm()
        self._check_cancel()
        if value is None or not math.isfinite(value) or value <= 0:
            return None
        return value

    def _sort(self, command):
        s = self.settings
        if command in {"BOTTLE", "CAN"}:
            self.hardware.servo("sort", s.sort_bottle_us if command == "BOTTLE" else s.sort_can_us)
            self._wait(s.move_seconds)
            self.hardware.servo("gate", s.gate_accept_us)
        else:
            self.hardware.servo("gate", s.gate_reject_us)
        self._wait(s.drop_seconds)
        self.hardware.servo("gate", s.gate_center_us)
        self._wait(s.move_seconds)
        self.hardware.servo("sort", s.sort_center_us)
        self._wait(s.move_seconds)

    def _water(self, command, on_dispensing):
        s = self.settings
        duration = getattr(s, f"{command.lower()}_seconds")
        self.emit("WAITING FOR BOTTLE")
        deadline = time.monotonic() + s.bottle_wait_seconds
        close_readings = 0
        while time.monotonic() < deadline:
            distance = self._distance()
            close_readings = close_readings + 1 if distance is not None and distance <= s.trigger_distance_cm else 0
            if time.monotonic() >= deadline:
                break
            if close_readings >= 2:
                break
            self._wait(0.2)
        else:
            raise OperationError("NO_BOTTLE")
        if close_readings < 2 or time.monotonic() >= deadline:
            raise OperationError("NO_BOTTLE")

        # The callback may perform network work. Run it before energizing the
        # pump, then recheck the sensor so a slow callback cannot hide removal.
        self._check_cancel()
        if on_dispensing is not None:
            on_dispensing()
            distance = self._distance()
            if distance is None or distance > s.trigger_distance_cm:
                raise OperationError("NO_BOTTLE")
        self._check_cancel()
        self.emit(f"DISPENSING {command}")
        deadline = time.monotonic() + duration
        # Serialize the last cancellation check with RESET/close's pump-off.
        with self.state_lock:
            self._check_cancel()
            self.hardware.pump(True)
        far_readings = bad_readings = 0
        try:
            while time.monotonic() < deadline:
                distance = self._distance()
                if distance is not None and distance <= s.remove_distance_cm:
                    far_readings = bad_readings = 0
                else:
                    bad_readings += 1
                    far_readings = far_readings + 1 if distance is not None else 0
                    if far_readings >= 4:
                        raise OperationError("CONTAINER_REMOVED")
                    # Includes mixed far/no-echo runs, which must not keep
                    # resetting each other while there is no presence evidence.
                    if bad_readings >= 20:
                        raise OperationError("SENSOR_LOST")
                self._wait(max(0, min(0.1, deadline - time.monotonic())))
        finally:
            self.hardware.pump(False)

    def execute(self, command, on_dispensing=None):
        command = command.strip().upper()
        allowed = {"BOTTLE", "CAN", "REJECT", "RESET", "WATER_250", "WATER_500", "WATER_1000"}
        if command not in allowed:
            return False, f"INVALID_COMMAND: {command}"
        if command == "RESET":
            return self.reset()
        with self.state_lock:
            if self.closed:
                return False, f"ERROR {command} CLOSED"
            if self.reset_pending or not self.operation_lock.acquire(blocking=False):
                return False, f"ERROR {command} BUSY"
            self.cancel.clear()
        error = None
        try:
            self.hardware.all_off()
            if command.startswith("WATER_"):
                self._water(command, on_dispensing)
            else:
                self._sort(command)
            self._check_cancel()
        except OperationError as failure:
            error = str(failure)
        except Exception as failure:
            error = f"HARDWARE_FAILURE {failure}"
        finally:
            try:
                self.hardware.all_off()
            except Exception as failure:
                error = f"HARDWARE_FAILURE {failure}"
            self.operation_lock.release()
        response = f"ERROR {command} {error}" if error else f"OK {command}"
        self.emit(response)
        return (False, response) if error else (True, None)

    def reset(self):
        with self.state_lock:
            if self.closed:
                return False, "ERROR RESET CLOSED"
            if self.reset_pending:
                return False, "ERROR RESET BUSY"
            self.reset_pending = True
            self.cancel.set()
        try:
            self.hardware.all_off()
            with self.operation_lock:
                with self.state_lock:
                    if self.closed:
                        return False, "ERROR RESET CLOSED"
                    self.cancel.clear()
                self._center()
                self._wait(1)
            self.emit("OK RESET")
            return True, None
        except Exception as error:
            return False, f"ERROR RESET {error}"
        finally:
            with self.state_lock:
                self.reset_pending = False

    def close(self):
        with self.state_lock:
            if self.closed:
                return
            self.closed = True
            self.cancel.set()
        try:
            self.hardware.all_off()
        finally:
            with self.operation_lock:
                self.hardware.close()
