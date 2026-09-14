"""Direct-controller regressions; fake GPIO, PWM sysfs, clock, and sensor."""

from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
import tempfile
import threading
import time
import unittest
from unittest.mock import Mock, patch

from machine.gpio_controller import ControllerSettings, GPIOController
from machine.gpio_hardware import HardwareServo, PiGPIOHardware, find_pwm_chip
from machine.runtime import MachineRuntime


class ControllerTests(unittest.TestCase):
    def setUp(self):
        self.hardware = Mock()
        self.hardware.distance_cm.return_value = 5.0
        self.responses = []
        self.settings = ControllerSettings(water_250_seconds=0.5, bottle_wait_seconds=0.8)
        self.controller = GPIOController(self.hardware, self.settings, self.responses.append)
        self.now = 0.0
        self.clock = patch("machine.gpio_controller.time.monotonic", side_effect=lambda: self.now)
        self.clock.start()
        self.addCleanup(self.clock.stop)

        def advance(seconds):
            self.controller._check_cancel()
            self.now += seconds

        self.controller._wait = advance

    def run_water(self, readings=None, callback=None):
        if readings is not None:
            self.hardware.distance_cm.side_effect = readings
        return self.controller.execute("WATER_250", callback)

    def test_success_retains_timer_and_turns_pump_off_before_completion(self):
        self.controller.emit = lambda response: (
            self.assertEqual(self.hardware.pump.call_args.args, (False,))
            if response.startswith("OK") else None
        )
        self.assertEqual(self.run_water(), (True, None))
        self.assertEqual([c.args for c in self.hardware.pump.call_args_list], [(True,), (False,)])
        self.assertAlmostEqual(self.now, 0.7)  # two close readings + 0.5 s refill

    def test_original_water_durations_are_preserved(self):
        s = ControllerSettings()
        self.assertEqual((s.water_250_seconds, s.water_500_seconds, s.water_1000_seconds), (25, 30, 45))

    def test_each_water_command_selects_its_own_calibrated_duration(self):
        self.controller.settings = replace(self.settings, water_500_seconds=1, water_1000_seconds=1.5)
        for command, duration in (("WATER_250", 0.5), ("WATER_500", 1), ("WATER_1000", 1.5)):
            with self.subTest(command=command):
                start = self.now
                self.assertEqual(self.controller.execute(command), (True, None))
                self.assertAlmostEqual(self.now - start, duration + 0.2)

    def test_missing_echo_resets_initial_detection_count(self):
        self.hardware.distance_cm.side_effect = [5, None, 5, None, 5]
        self.assertEqual(self.run_water(), (False, "ERROR WATER_250 NO_BOTTLE"))
        self.hardware.pump.assert_not_called()

    def test_far_readings_stop_the_pump(self):
        self.assertEqual(self.run_water([5, 5, 20, 20, 20, 20]),
                         (False, "ERROR WATER_250 CONTAINER_REMOVED"))
        self.assertEqual(self.hardware.pump.call_args.args, (False,))

    def test_missing_and_alternating_bad_readings_cannot_run_forever(self):
        self.controller.settings = replace(self.settings, water_250_seconds=10)
        for bad in ([None] * 20, [None, 20] * 10):
            with self.subTest(bad=bad):
                self.assertEqual(self.run_water([5, 5] + bad),
                                 (False, "ERROR WATER_250 SENSOR_LOST"))
                self.assertEqual(self.hardware.pump.call_args.args, (False,))

    def test_short_dropout_recovers(self):
        self.assertEqual(self.run_water([5, 5, None, None, 5, 5, 5, 5]), (True, None))

    def test_sensor_exception_turns_off_and_does_not_retry(self):
        ok, error = self.run_water([5, 5, OSError("sensor unplugged")])
        self.assertFalse(ok)
        self.assertIn("HARDWARE_FAILURE", error)
        self.assertEqual([c.args for c in self.hardware.pump.call_args_list], [(True,), (False,)])

    def test_callback_runs_before_power_and_presence_is_rechecked(self):
        callback = Mock(side_effect=lambda: self.hardware.pump.assert_not_called())
        self.assertEqual(self.run_water([5, 5, 25], callback),
                         (False, "ERROR WATER_250 NO_BOTTLE"))
        callback.assert_called_once_with()
        self.hardware.pump.assert_not_called()

    def test_callback_failure_never_energizes_pump(self):
        ok, error = self.run_water(callback=Mock(side_effect=OSError("network unavailable")))
        self.assertFalse(ok)
        self.assertIn("network unavailable", error)
        self.hardware.pump.assert_not_called()

    def test_sort_sequence_and_final_settle(self):
        self.assertEqual(self.controller.execute(" bottle "), (True, None))
        self.assertEqual([c.args for c in self.hardware.servo.call_args_list], [
            ("sort", 1000), ("gate", 1000), ("gate", 1500), ("sort", 1500),
        ])
        self.assertAlmostEqual(self.now, 3.6)
        self.hardware.pump.assert_not_called()

    def test_can_and_reject_paths(self):
        for command, expected in (
            ("CAN", [("sort", 2000), ("gate", 1000), ("gate", 1500), ("sort", 1500)]),
            ("REJECT", [("gate", 2000), ("gate", 1500), ("sort", 1500)]),
        ):
            self.hardware.reset_mock()
            self.assertEqual(self.controller.execute(command), (True, None))
            self.assertEqual([c.args for c in self.hardware.servo.call_args_list], expected)

    def test_unknown_command_never_touches_hardware(self):
        self.assertFalse(self.controller.execute("RELAY_ON")[0])
        self.assertEqual(self.hardware.mock_calls, [])

    def test_servo_initialization_failure_closes_resources(self):
        self.hardware.servo.side_effect = OSError("PWM permissions")
        with self.assertRaisesRegex(OSError, "PWM permissions"):
            self.controller.open()
        self.hardware.close.assert_called_once()

    def test_shutdown_during_callback_prevents_pump_on(self):
        def cancelled_callback():
            self.controller.cancel.set()
        self.assertEqual(self.run_water(callback=cancelled_callback),
                         (False, "ERROR WATER_250 CANCELLED"))
        self.hardware.pump.assert_not_called()

    def test_settings_reject_unsafe_and_nonfinite_values(self):
        for changes in (
            {"gate_accept_us": 499}, {"gate_reject_us": 2501},
            {"water_250_seconds": 0}, {"water_500_seconds": 61},
            {"water_1000_seconds": float("nan")}, {"move_seconds": True},
            {"trigger_distance_cm": 15, "remove_distance_cm": 14},
        ):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                ControllerSettings(**changes)


class CancellationTests(unittest.TestCase):
    def test_reset_and_close_interrupt_active_water_and_busy_commands_are_rejected(self):
        for action in ("reset", "close"):
            with self.subTest(action=action):
                hardware = Mock()
                hardware.distance_cm.return_value = 5
                pumping = threading.Event()
                hardware.pump.side_effect = lambda on: pumping.set() if on else None
                controller = GPIOController(hardware)
                result = []
                worker = threading.Thread(target=lambda: result.append(controller.execute("WATER_250")))
                worker.start()
                try:
                    self.assertTrue(pumping.wait(2))
                    self.assertEqual(controller.execute("WATER_250"), (False, "ERROR WATER_250 BUSY"))
                    self.assertEqual(controller.execute("BOTTLE"), (False, "ERROR BOTTLE BUSY"))
                    started = time.monotonic()
                    getattr(controller, action)()
                    worker.join(timeout=2)
                    self.assertFalse(worker.is_alive())
                    self.assertLess(time.monotonic() - started, 1.5)
                    self.assertEqual(result, [(False, "ERROR WATER_250 CANCELLED")])
                    self.assertEqual(hardware.pump.call_args.args, (False,))
                finally:
                    controller.close()
                    worker.join(timeout=2)


class HardwareTests(unittest.TestCase):
    def test_pwm_selection_ignores_fan_and_gpiochip_number(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for chip, name in ((0, "pwm@9c000"), (7, "pwm@98000")):
                node = root / name
                node.mkdir()
                (node / "compatible").write_bytes(b"raspberrypi,rp1-pwm\0")
                device = root / f"pwmchip{chip}" / "device"
                device.mkdir(parents=True)
                (device / "of_node").symlink_to(node)
            self.assertEqual(find_pwm_chip(root), root / "pwmchip7")

    def test_servo_period_and_pulse_use_nanoseconds(self):
        with tempfile.TemporaryDirectory() as directory:
            chip = Path(directory)
            path = chip / "pwm2"
            path.mkdir()
            (path / "enable").write_text("0")
            servo = HardwareServo(chip, 2)
            servo.pulse(1500)
            self.assertEqual((path / "period").read_text(), "20000000")
            self.assertEqual((path / "duty_cycle").read_text(), "1500000")
            self.assertEqual((path / "enable").read_text(), "1")
            servo.close()
            self.assertEqual((path / "enable").read_text(), "0")

    def test_echo_uses_edge_timestamps_and_rejects_stale_events(self):
        hardware = PiGPIOHardware()
        hardware.gpio = Mock()
        hardware.handle = 1
        hardware.gpio.gpio_read.return_value = 0

        def pulse(*_):
            # Old queued events must not satisfy the current measurement.
            hardware._echo_edge(1, 24, 1, 10)
            hardware._echo_edge(1, 24, 0, 20)
            hardware._echo_edge(1, 24, 1, 1_000_100)
            hardware._echo_edge(1, 24, 0, 2_000_100)

        hardware.gpio.tx_pulse.side_effect = pulse
        with patch("machine.gpio_hardware.time.monotonic_ns", return_value=1_000_000):
            self.assertAlmostEqual(hardware.distance_cm(), 17.15)

    def test_missing_echo_never_reuses_previous_distance(self):
        hardware = PiGPIOHardware()
        hardware.gpio = Mock()
        hardware.handle = 1
        hardware.gpio.gpio_read.return_value = 0
        hardware.width_ns = 500_000
        hardware.echo_done.wait = Mock(return_value=False)
        self.assertIsNone(hardware.distance_cm())
        hardware.gpio.gpio_read.return_value = 1
        hardware.gpio.reset_mock()
        self.assertIsNone(hardware.distance_cm())
        hardware.gpio.tx_pulse.assert_not_called()

    def test_partial_gpio_start_failure_turns_claimed_relay_off(self):
        hardware = PiGPIOHardware()
        gpio = Mock()
        gpio.gpio_claim_output.side_effect = [0, OSError("second pin busy")]
        with patch.dict("sys.modules", {"lgpio": gpio}), \
             patch("machine.gpio_hardware.open_header", return_value=9):
            with self.assertRaisesRegex(OSError, "second pin busy"):
                hardware.open()
        gpio.gpio_write.assert_called_with(9, 22, 0)
        gpio.gpiochip_close.assert_called_once_with(9)
        self.assertIsNone(hardware.handle)

    def test_cleanup_attempts_other_resources_after_one_failure(self):
        hardware = PiGPIOHardware()
        hardware.gpio = Mock()
        hardware.handle = 9
        hardware.outputs = [22, 26]
        hardware.gpio.gpio_write.side_effect = [OSError("write failure"), None]
        hardware.callback = Mock()
        hardware.callback.cancel.side_effect = OSError("callback failure")
        servo = Mock()
        hardware.servos = {"gate": servo}
        with self.assertRaisesRegex(RuntimeError, "cleanup failed"):
            hardware.close()
        self.assertEqual(hardware.gpio.gpio_write.call_count, 2)
        servo.close.assert_called_once()
        hardware.gpio.gpiochip_close.assert_called_once_with(9)

    def test_cleanup_does_not_send_zero_length_trigger_pulse(self):
        # The Pi's lgpio rejects tx_pulse(..., 0, 0) with "bad PWM micros".
        # Trigger pulses are one-shot; gpiochip_close stops any pending output.
        hardware = PiGPIOHardware()
        hardware.gpio = Mock()
        hardware.gpio.tx_pulse.side_effect = RuntimeError("bad PWM micros")
        hardware.handle = 9
        hardware.outputs = [22, 26, 23]
        servo = Mock()
        hardware.servos = {"gate": servo}
        callback = hardware.callback = Mock()

        hardware.close()

        hardware.gpio.tx_pulse.assert_not_called()
        self.assertEqual([call.args for call in hardware.gpio.gpio_write.call_args_list],
                         [(9, 22, 0), (9, 26, 0), (9, 23, 0)])
        servo.close.assert_called_once()
        callback.cancel.assert_called_once()
        hardware.gpio.gpiochip_close.assert_called_once_with(9)
        hardware.close()  # Repeated cleanup remains harmless.
        hardware.gpio.gpiochip_close.assert_called_once()


class RoutingTests(unittest.TestCase):
    def setUp(self):
        self.machine = MachineRuntime()
        self.machine.controller_backend = "gpio"
        self.machine.gpio_controller = Mock()
        self.machine.gpio_controller.execute.return_value = (True, None)

    def test_gpio_commands_do_not_open_serial(self):
        with patch.object(self.machine, "get_esp32_connection") as serial:
            self.assertTrue(self.machine.send_to_esp32("can"))
            callback = Mock()
            self.assertEqual(self.machine.run_water_command("water_500", callback), (True, None))
            serial.assert_not_called()
            self.machine.gpio_controller.execute.assert_called_with("WATER_500", on_dispensing=callback)

    def test_failure_is_returned_without_retry(self):
        self.machine.gpio_controller.execute.return_value = (False, "ERROR WATER_250 SENSOR_LOST")
        self.assertEqual(self.machine.run_water_command("WATER_250"), (False, "ERROR WATER_250 SENSOR_LOST"))
        self.machine.gpio_controller.execute.assert_called_once()

    def test_shutdown_stops_gpio_before_camera_and_rejects_late_work(self):
        order = []
        self.machine.gpio_controller.close.side_effect = lambda: order.append("gpio")
        self.machine.picam2 = Mock()
        self.machine.picam2.stop.side_effect = lambda: order.append("camera")
        self.machine.close()
        self.assertEqual(order, ["gpio", "camera"])
        self.assertFalse(self.machine.send_to_esp32("BOTTLE"))
        self.assertEqual(self.machine.run_water_command("WATER_250"), (False, "GPIO_CONTROLLER_UNAVAILABLE"))
        self.machine.gpio_controller.execute.assert_not_called()

    def test_button_pin_conflict_is_rejected_before_hardware_open(self):
        with patch("machine.runtime.GREEN_BUTTON_GPIO", 22), \
             patch("machine.gpio_hardware.PiGPIOHardware") as factory:
            with self.assertRaisesRegex(ValueError, "button GPIO conflicts"):
                self.machine.initialize_controller()
            factory.assert_not_called()

    def test_failed_sort_does_not_award_or_record_success(self):
        machine = self.machine
        machine.wait_for_item_motion = Mock(return_value=object())
        machine.verify_item = Mock(return_value={
            "accepted": True, "category": "bottle", "item": "plastic_bottle",
            "points": 1, "confidence": 0.99,
        })
        machine.frame_to_base64_data_url = Mock(return_value="image")
        machine.save_local_session = Mock()
        machine.queue_recycling_upload = Mock()

        def failed_sort(*_):
            machine.shutdown_event.set()
            return False

        machine.sort_item = Mock(side_effect=failed_sort)
        with patch.dict("sys.modules", {
            "cv2": SimpleNamespace(imwrite=Mock()),
            "firebase_admin": SimpleNamespace(firestore=Mock()),
        }), self.assertLogs("ecorefill.machine", level="ERROR"):
            machine.machine_worker()
        self.assertEqual(machine.get_state()["phase"], "error")
        self.assertEqual(machine.get_state()["pointsEarned"], 0)
        self.assertEqual(machine.get_state()["itemCount"], 0)
        machine.save_local_session.assert_not_called()
        machine.queue_recycling_upload.assert_not_called()


if __name__ == "__main__":
    unittest.main()
