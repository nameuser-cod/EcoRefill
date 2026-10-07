"""Bin fullness confirmation, offline recovery, owner alerts and sensor GPIO."""

import copy
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from machine.bin_monitor import BinFullMonitor, BinSettings
from machine.journal import MachineJournal
from machine.runtime import MachineRuntime
from machine.ultrasonic import BinUltrasonicSensor
from machine.gpio_hardware import PiGPIOHardware
from tests.test_recycling_uploads import FakeFirestore


class BinMonitorTests(unittest.TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / "journal.sqlite3"
        self.journal = MachineJournal(self.path)
        self.monitor = BinFullMonitor(self.journal, BinSettings())

    def observe(self, *distances):
        for distance in distances:
            self.monitor.observe(distance, now=100)

    def test_falling_item_and_invalid_readings_never_confirm_full(self):
        for invalid in (None, float("nan"), float("inf"), -1, 0, 1, 401, True, "5"):
            self.observe(5, 5, invalid, 5, 30)
        self.assertFalse(self.monitor.full)
        self.assertEqual(self.journal.entries("bin_alert"), [])

    def test_confirmed_full_sends_one_alert_until_confirmed_empty(self):
        self.observe(10, 9, 8, 5, 5, 5)
        self.assertTrue(self.monitor.full)
        self.assertEqual(len(self.journal.entries("bin_alert")), 1)
        # Readings in the gap or missing echoes never clear the full latch.
        self.observe(15, 20, 20, None, 20, 20, 19)
        self.assertTrue(self.monitor.full)
        self.observe(20, 20, 20)
        self.assertFalse(self.monitor.full)
        self.observe(10, 10, 10)
        self.assertEqual(len(self.journal.entries("bin_alert")), 2)

    def test_restart_while_full_does_not_repeat_and_queue_survives(self):
        self.observe(5, 5, 5)
        saved = self.journal.entries("bin_alert")
        self.journal = MachineJournal(self.path)
        self.monitor = BinFullMonitor(self.journal, BinSettings())
        self.observe(5, 5, 5)
        self.assertEqual(self.journal.entries("bin_alert"), saved)
        self.assertTrue(self.monitor.full)

    def test_failed_local_commit_does_not_latch_full_or_lose_alert(self):
        self.observe(5, 5)
        with patch.object(self.journal, "connect", side_effect=OSError("disk unavailable")):
            with self.assertRaises(OSError):
                self.observe(5)
        self.assertFalse(self.monitor.full)
        self.observe(5)
        self.assertTrue(self.monitor.full)
        self.assertEqual(len(self.journal.entries("bin_alert")), 1)

    def test_offline_sync_and_lost_response_cannot_reopen_deleted_alert(self):
        machine = MachineRuntime()
        self.addCleanup(machine.close)
        machine.journal = self.journal
        self.observe(5, 5, 5)
        event_id, _ = self.journal.entries("bin_alert")[0]
        db = FakeFirestore()
        firestore = SimpleNamespace(transactional=db.transactional, SERVER_TIMESTAMP="server-time")
        with patch.dict(sys.modules, {"firebase_admin": SimpleNamespace(firestore=firestore)}):
            with self.assertRaisesRegex(RuntimeError, "Firebase unavailable"):
                machine.sync_bin_alerts()
            self.assertEqual(len(self.journal.entries("bin_alert")), 1)
            machine.db = db
            db.lose_response = True
            with self.assertRaises(TimeoutError):
                machine.sync_bin_alerts()
            alert = db.records[f"machine_alerts/{event_id}"]
            self.assertEqual(alert["alertType"], "bin_full")
            self.assertEqual(alert["machineId"], "machine_001")
            self.assertEqual(alert["status"], "unread")
            self.assertIn("empty the bin", alert["message"])
            self.assertEqual(alert["createdAt"].timestamp(), 100)
            # Owner resolves/deletes it before the Pi receives a commit acknowledgment.
            del db.records[f"machine_alerts/{event_id}"]
            before = copy.deepcopy(db.records)
            machine.sync_bin_alerts()
            self.assertEqual(db.records, before)
            self.assertEqual(self.journal.entries("bin_alert"), [])

    def test_bad_configuration_rejects_pin_conflicts_and_invalid_thresholds(self):
        for settings in ({"trig_gpio": 23}, {"echo_gpio": 17}, {"trig_gpio": 5},
                         {"echo_gpio": 16}, {"trig_gpio": True}, {"enabled": "false"},
                         {"full_distance_cm": 20}, {"clear_distance_cm": float("nan")},
                         {"full_distance_cm": 1}, {"confirm_readings": 1},
                         {"confirm_readings": 2.5}, {"poll_seconds": 0}):
            with self.subTest(settings=settings), self.assertRaises(ValueError):
                BinSettings(**settings)

    def test_sensor_failures_retry_without_generating_full_alerts(self):
        machine = MachineRuntime()
        self.addCleanup(machine.close)
        machine.journal = self.journal
        with patch("machine.bin_monitor.BinUltrasonicSensor") as sensor, \
             patch.object(machine.shutdown_event, "wait", side_effect=lambda _: machine.shutdown_event.set()), \
             self.assertLogs("ecorefill.machine", level="ERROR"):
            sensor.return_value.distance_cm.side_effect = OSError("disconnected")
            machine.bin_monitor_worker()
            sensor.return_value.close.assert_called_once_with()
        self.assertEqual(self.journal.entries("bin_alert"), [])


class BinHardwareTests(unittest.TestCase):
    def test_water_and_bin_sensors_share_a_quiet_interval(self):
        water, bin_sensor = PiGPIOHardware(), BinUltrasonicSensor()
        water.handle = bin_sensor.handle = 9
        water._measure_distance_cm = Mock(return_value=5)
        bin_sensor._measure_distance_cm = Mock(return_value=30)
        with patch("machine.ultrasonic._NEXT_PING_AT", 0), \
             patch("machine.ultrasonic.time.monotonic", side_effect=[10, 10.01, 10.02, 10.03]), \
             patch("machine.ultrasonic.time.sleep") as sleep:
            self.assertEqual(water.distance_cm(), 5)
            self.assertEqual(bin_sensor.distance_cm(), 30)
        sleep.assert_called_once()
        self.assertAlmostEqual(sleep.call_args.args[0], 0.05)

    def test_sensor_only_claims_bin_pins_and_releases_them(self):
        sensor = BinUltrasonicSensor()
        gpio = Mock()
        with patch.dict(sys.modules, {"lgpio": gpio}), \
             patch("machine.ultrasonic.open_header", return_value=9):
            sensor.open()
        gpio.gpio_claim_output.assert_called_once_with(9, 16, 0)
        gpio.gpio_claim_alert.assert_called_once_with(9, 20, gpio.BOTH_EDGES)
        sensor.close()
        sensor.close()
        gpio.gpio_write.assert_called_once_with(9, 16, 0)
        gpio.callback.return_value.cancel.assert_called_once_with()
        gpio.gpiochip_close.assert_called_once_with(9)
        self.assertIsNone(sensor.distance_cm())

    def test_partial_initialization_failure_releases_gpio(self):
        sensor = BinUltrasonicSensor()
        gpio = Mock()
        gpio.gpio_claim_alert.side_effect = OSError("pin busy")
        with patch.dict(sys.modules, {"lgpio": gpio}), \
             patch("machine.ultrasonic.open_header", return_value=9):
            with self.assertRaisesRegex(OSError, "pin busy"):
                sensor.open()
        gpio.gpiochip_close.assert_called_once_with(9)
        self.assertIsNone(sensor.handle)

    def test_bin_echo_uses_new_gpio_and_never_reuses_previous_reading(self):
        sensor = BinUltrasonicSensor()
        sensor.gpio = Mock()
        sensor.handle = 9
        sensor.gpio.gpio_read.return_value = 0

        def echo(*_):
            sensor._echo_edge(9, 20, 1, 1_000_100)
            sensor._echo_edge(9, 20, 0, 2_000_100)

        sensor.gpio.tx_pulse.side_effect = echo
        with patch("machine.ultrasonic.time.monotonic_ns", return_value=1_000_000):
            self.assertAlmostEqual(sensor.distance_cm(), 17.15)
        sensor.gpio.tx_pulse.assert_called_once_with(9, 16, 10, 10, 0, 1)
        sensor.gpio.tx_pulse.side_effect = None
        sensor.echo_done.wait = Mock(return_value=False)
        self.assertIsNone(sensor.distance_cm())


if __name__ == "__main__":
    unittest.main()
