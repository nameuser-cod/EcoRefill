"""Gallon calibration, missing echoes, separate GPIO ownership and publication."""

import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from machine.bin_monitor import BinSettings
from machine.runtime import MachineRuntime
from machine.ultrasonic import WaterLevelUltrasonicSensor
from machine.water_level import WaterLevelMonitor, WaterLevelSettings


class WaterLevelTests(unittest.TestCase):
    def setUp(self):
        self.settings = WaterLevelSettings(enabled=True)
        self.monitor = WaterLevelMonitor(self.settings)

    def confirm(self, distance):
        result = None
        for _ in range(self.settings.confirm_readings):
            result = self.monitor.observe(distance, now=100)
        return result

    def test_requested_mapping_and_empty_clamp(self):
        for distance, percent in ((20, 100), (21, 85), (22, 80), (23, 75),
                                  (24, 70), (28, 50), (33, 25), (38, 0), (50, 0)):
            with self.subTest(distance=distance):
                reading = self.confirm(distance)
                self.assertEqual(reading["waterLevel"], percent)
                self.assertEqual(reading["waterDistanceCm"], distance)
                self.assertEqual(reading["waterLevelUpdatedAt"].timestamp(), 100)

    def test_no_echo_requires_confirmation_and_is_explicitly_assumed_full(self):
        self.assertIsNone(self.monitor.observe(None))
        self.assertIsNone(self.monitor.observe(None))
        reading = self.monitor.observe(None)
        self.assertEqual(reading["waterLevel"], 100)
        self.assertIsNone(reading["waterDistanceCm"])
        self.assertEqual(reading["waterLevelStatus"], "no_echo_assumed_full")
        reading = self.confirm(10)
        self.assertEqual(reading["waterLevel"], 100)
        self.assertEqual(reading["waterLevelStatus"], "blind_zone_assumed_full")

    def test_single_missed_echo_does_not_replace_a_measured_level_with_full(self):
        self.assertEqual(self.confirm(28)["waterLevel"], 50)
        self.assertIsNone(self.monitor.observe(None))
        self.assertIsNone(self.monitor.observe(28))
        self.assertIsNone(self.monitor.observe(None))
        self.assertIsNone(self.monitor.observe(None))
        self.assertIsNone(self.monitor.observe(28))

    def test_median_suppresses_one_distance_outlier(self):
        self.monitor.observe(28)
        self.monitor.observe(45)
        self.assertEqual(self.monitor.observe(28)["waterLevel"], 50)

    def test_invalid_readings_are_not_interpreted_as_full(self):
        for invalid in (True, "21", float("nan"), float("inf"), 0, -1, 601):
            with self.subTest(distance=invalid):
                self.monitor.observe(None)
                self.monitor.observe(None)
                result = self.monitor.observe(invalid)
                self.assertIsNone(result["waterLevel"])
                self.assertEqual(result["waterLevelStatus"], "invalid")
                self.assertIsNone(self.monitor.observe(None))

    def test_custom_empty_endpoint_and_fractional_distances(self):
        monitor = WaterLevelMonitor(WaterLevelSettings(empty_distance_cm=55))
        self.assertEqual(monitor.percentage(21), 85)
        self.assertEqual(monitor.percentage(38), 42)
        self.assertEqual(monitor.percentage(55), 0)
        self.assertEqual(self.monitor.percentage(21.5), 82)

    def test_configuration_rejects_invalid_calibration_and_pin_conflicts(self):
        for values in ({"enabled": "true"}, {"trig_gpio": 23}, {"echo_gpio": 17},
                       {"trig_gpio": 5}, {"echo_gpio": 12}, {"trig_gpio": True},
                       {"first_distance_cm": 20}, {"empty_distance_cm": 21},
                       {"first_percent": 100}, {"first_percent": float("nan")},
                       {"confirm_readings": 1}, {"confirm_readings": 2.5}, {"poll_seconds": 0}):
            with self.subTest(values=values), self.assertRaises(ValueError):
                WaterLevelSettings(**values)
        with self.assertRaisesRegex(ValueError, "bin sensor"):
            self.settings.validate_bin_pins(BinSettings(trig_gpio=12))
        self.settings.validate_bin_pins(BinSettings(enabled=False, trig_gpio=12))

    def test_config_loads_explicit_file_and_missing_explicit_file_fails(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "level.json"
            path.write_text(json.dumps({"enabled": True, "empty_distance_cm": 55}))
            self.assertEqual(WaterLevelSettings.from_file(path).empty_distance_cm, 55)
            with patch.dict("os.environ", {"ECOREFILL_WATER_LEVEL_CONFIG": str(path)}):
                self.assertTrue(WaterLevelSettings.from_file().enabled)
            with self.assertRaises(FileNotFoundError):
                WaterLevelSettings.from_file(Path(directory) / "missing.json")


class WaterLevelRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.machine = MachineRuntime()
        self.machine.water_level_settings = WaterLevelSettings(enabled=True)
        self.addCleanup(self.machine.close)

    def run_worker(self, cycles):
        with patch.object(self.machine.shutdown_event, "is_set", side_effect=[False] * cycles + [True]), \
             patch.object(self.machine.shutdown_event, "wait"):
            self.machine.water_level_worker()

    def test_confirmed_reading_is_published_by_heartbeat_not_sensor_worker(self):
        self.machine.db = Mock()
        with patch("machine.water_level.WaterLevelUltrasonicSensor") as sensor:
            sensor.return_value.distance_cm.return_value = 21
            self.run_worker(3)
            sensor.assert_called_once_with(12, 13)
        self.machine.db.collection.assert_not_called()
        timestamp = object()
        with patch.dict(sys.modules, {
            "firebase_admin": SimpleNamespace(firestore=SimpleNamespace(SERVER_TIMESTAMP=timestamp)),
        }), patch.object(self.machine.shutdown_event, "is_set", side_effect=[False, True]), \
             patch.object(self.machine.shutdown_event, "wait"):
            self.machine.machine_presence_worker()
        fields = self.machine.db.collection.return_value.document.return_value.update.call_args.args[0]
        self.assertEqual(fields["waterLevel"], 85)
        self.assertEqual(fields["waterDistanceCm"], 21)
        self.assertEqual(fields["waterLevelStatus"], "measured")
        self.assertIs(fields["lastHeartbeatAt"], timestamp)

    def test_offline_readings_continue_and_no_echo_replaces_previous_percentage(self):
        with patch("machine.water_level.WaterLevelUltrasonicSensor") as sensor:
            sensor.return_value.distance_cm.side_effect = [28, 28, 28, None, None, None]
            self.run_worker(6)
        fields = self.machine.get_water_level_fields()
        self.assertEqual(fields["waterLevel"], 100)
        self.assertEqual(fields["waterLevelStatus"], "no_echo_assumed_full")

    def test_gpio_failure_is_unavailable_and_releases_sensor_for_retry(self):
        with patch("machine.water_level.WaterLevelUltrasonicSensor") as sensor, \
             self.assertLogs("ecorefill.machine", level="ERROR"):
            sensor.return_value.distance_cm.side_effect = OSError("GPIO failed")
            self.run_worker(1)
        self.assertIsNone(self.machine.get_water_level_fields()["waterLevel"])
        self.assertEqual(self.machine.get_water_level_fields()["waterLevelStatus"], "unavailable")
        sensor.return_value.close.assert_called_once_with()
        self.assertIsNone(self.machine.water_level_sensor)

    def test_old_reading_expires_instead_of_being_republished_as_fresh(self):
        with patch("machine.water_level.time.monotonic", return_value=10):
            self.machine._save_water_level(WaterLevelMonitor.reading(85, 21, "measured", now=100))
        with patch("machine.water_level.time.monotonic", return_value=29):
            reading = self.machine.get_water_level_fields()
        self.assertIsNone(reading["waterLevel"])
        self.assertEqual(reading["waterLevelStatus"], "stale")
        self.assertEqual(reading["waterLevelUpdatedAt"].timestamp(), 100)

    def test_starting_and_disabled_monitor_do_not_invent_full_reading(self):
        self.assertIsNone(self.machine.get_water_level_fields()["waterLevel"])
        self.machine.water_level_settings = WaterLevelSettings(enabled=False)
        self.assertEqual(self.machine.get_water_level_fields(), {})

    def test_shutdown_joins_worker_and_releases_sensor_once(self):
        self.machine.water_level_sensor = Mock()
        self.machine.water_level_thread = Mock()
        self.machine.close()
        self.machine.close()
        self.machine.water_level_thread.join.assert_called_once_with(timeout=1)
        self.machine.water_level_sensor.close.assert_called_once_with()

    def test_gallon_sensor_claims_only_its_own_pins(self):
        sensor = WaterLevelUltrasonicSensor()
        gpio = Mock()
        with patch.dict(sys.modules, {"lgpio": gpio}), \
             patch("machine.ultrasonic.open_header", return_value=9):
            sensor.open()
        gpio.gpio_claim_output.assert_called_once_with(9, 12, 0)
        gpio.gpio_claim_alert.assert_called_once_with(9, 13, gpio.BOTH_EDGES)
        sensor.close()
        sensor.close()
        gpio.gpiochip_close.assert_called_once_with(9)


if __name__ == "__main__":
    unittest.main()
