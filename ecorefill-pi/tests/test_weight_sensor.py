"""Protocol and calibration checks without GPIO hardware."""

import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from itertools import chain, cycle
from unittest.mock import Mock, patch

from tools.check_weight import calibration_factor, main as check_weight_main
from machine.weight_sensor import HX711, CalibratedScale, WeightReadingError


class WeightSensorTests(unittest.TestCase):
    def read_word(self, word, final_level=1):
        gpio = Mock()
        bits = [(word >> bit) & 1 for bit in range(23, -1, -1)]
        gpio.gpio_read.side_effect = [0, *bits, final_level]
        sensor = HX711(gpio, 0)
        with patch("machine.weight_sensor.time.monotonic_ns", return_value=0):
            result = sensor.read_raw()
        self.assertEqual(gpio.gpio_write.call_count, 50)
        self.assertEqual(gpio.gpio_write.call_args.args, (0, 6, 0))
        return result

    def test_signed_samples(self):
        self.assertEqual(self.read_word(123456), 123456)
        self.assertEqual(self.read_word(0xFFFFFF), -1)
        self.assertEqual(self.read_word(0xFFFF9C), -100)
        self.assertEqual(self.read_word(0), 0)

    def test_saturation_is_not_a_weight(self):
        for word in (0x800000, 0x7FFFFF):
            with self.assertRaisesRegex(RuntimeError, "saturated"):
                self.read_word(word)

    def test_stuck_low_is_not_zero_weight(self):
        with self.assertRaisesRegex(RuntimeError, "stayed low"):
            self.read_word(0, final_level=0)

    def test_stuck_high_times_out_without_clocking(self):
        gpio = Mock()
        gpio.gpio_read.return_value = 1
        with patch("machine.weight_sensor.time.monotonic", side_effect=[0, 3]):
            with self.assertRaises(TimeoutError):
                HX711(gpio, 0).read_raw()
        gpio.gpio_write.assert_not_called()

    def test_long_clock_pulse_is_rejected_and_clock_lowered(self):
        gpio = Mock()
        with patch("machine.weight_sensor.time.monotonic_ns", side_effect=[0, 61000]):
            with self.assertRaisesRegex(RuntimeError, "timing"):
                HX711(gpio, 0).pulse()
        self.assertEqual(gpio.gpio_write.call_args.args, (0, 6, 0))

    def test_calibration_handles_both_sensor_polarities(self):
        for loaded in (21000, -19000):
            factor = calibration_factor(1000, loaded, 100, 10)
            self.assertAlmostEqual((loaded - 1000) / factor, 100)

    def test_invalid_mass_and_insufficient_response(self):
        for grams in (0, -100, 1000, float("nan"), float("inf")):
            with self.assertRaises(ValueError):
                calibration_factor(1000, 21000, grams, 10)
        with self.assertRaisesRegex(ValueError, "too small"):
            calibration_factor(1000, 1050, 100, 10)

    def test_noisy_calibration_reference_is_rejected_for_both_polarities(self):
        for loaded in (-552469, -698875):
            with self.subTest(loaded=loaded):
                with self.assertRaisesRegex(ValueError, "22.643 g"):
                    calibration_factor(-625672, loaded, 500, 3315)

    def test_calibration_spread_boundary_and_invalid_tolerance(self):
        self.assertEqual(calibration_factor(1000, 101000, 500, 600), 200)
        with self.assertRaisesRegex(ValueError, "unstable"):
            calibration_factor(1000, 101000, 500, 600.001)
        for tolerance in (0, -1, float("nan"), float("inf")):
            with self.subTest(tolerance=tolerance):
                with self.assertRaisesRegex(ValueError, "maximum spread"):
                    calibration_factor(1000, 101000, 500, 10, tolerance)

    def test_calibration_diagnostic_does_not_print_coefficients_for_unstable_samples(self):
        gpio = Mock()
        gpio.error = RuntimeError
        stdout, stderr = StringIO(), StringIO()
        with patch.dict("sys.modules", {"lgpio": gpio}), \
             patch.dict("os.environ", {"HX711_MAX_SPREAD_G": "3.0"}), \
             patch("sys.argv", ["check_weight", "--calibrate"]), \
             patch("tools.check_weight.open_header", return_value=0), \
             patch("tools.check_weight.HX711") as factory, \
             patch("builtins.input", side_effect=["", "500", ""]), \
             redirect_stdout(stdout), redirect_stderr(stderr):
            factory.return_value.sample.side_effect = [(-625672, 3315), (-552469, 100)]
            result = check_weight_main()
        self.assertEqual(result, 1)
        self.assertIn("Calibration is unstable", stderr.getvalue())
        self.assertIn("22.643 g", stderr.getvalue())
        self.assertNotIn("Offset:", stdout.getvalue())
        self.assertNotIn("Save these numbers", stdout.getvalue())
        gpio.gpiochip_close.assert_called_once_with(0)


class CalibratedScaleTests(unittest.TestCase):
    def scale(self, readings, factor=199.538):
        scale = CalibratedScale(-695343, factor)
        scale.sensor = Mock()
        scale.sensor.read_raw.side_effect = readings
        return scale

    def test_fresh_window_discards_old_conversion_and_uses_saved_calibration(self):
        for factor in (199.538, -199.538):
            raw = -695343 + 500 * factor
            scale = self.scale([123456] + [raw] * 10, factor)
            reading = scale.read_weight()
            self.assertAlmostEqual(reading["grams"], 500)
            self.assertEqual(reading["spread_g"], 0)
            self.assertEqual(scale.offset, -695343)  # Never tare with an item present.

    def test_transient_motion_can_settle_in_a_fresh_window(self):
        for factor in (199.538, -199.538):
            with self.subTest(factor=factor):
                moving = [-695343 + g * factor for g in (20, 29)] * 5
                settled = -695343 + 15 * factor
                scale = self.scale([123456] + moving + [settled] * 10, factor)
                reading = scale.read_weight()
                self.assertAlmostEqual(reading["grams"], 15)
                self.assertEqual(reading["spread_g"], 0)
                self.assertEqual(reading["samples"], 10)
                self.assertEqual(scale.sensor.read_raw.call_count, 21)
                self.assertEqual(scale.offset, -695343)

    def test_persistent_motion_rejects_with_spread_at_original_deadline(self):
        clock = [0.0]
        samples = chain([0], cycle([-695343 + g * 199.538 for g in range(20, 30)]))
        scale = self.scale([])

        def sample(**_kwargs):
            clock[0] += 0.125
            return next(samples)

        scale.sensor.read_raw.side_effect = sample
        with patch("machine.weight_sensor.time.monotonic", side_effect=lambda: clock[0]):
            with self.assertRaises(WeightReadingError) as caught:
                scale.read_weight()
        error = caught.exception
        self.assertEqual(error.status, "unstable")
        self.assertAlmostEqual(error.reading["spread_g"], 9)
        self.assertEqual(error.reading["samples"], 10)
        self.assertIn("spread=9.000 g", str(error))
        self.assertIn("allowed <= 3 g", str(error))
        self.assertEqual(clock[0], 4.0)
        self.assertEqual(scale.sensor.read_raw.call_count, 32)
        self.assertFalse(scale.needs_reset)

    def test_sensor_failure_after_motion_is_unavailable_and_requires_reset(self):
        moving = [-695343 + g * 199.538 for g in range(20, 30)]
        scale = self.scale([0] + moving + [TimeoutError("HX711 not ready")])
        with self.assertRaises(WeightReadingError) as caught:
            scale.read_weight()
        self.assertEqual(caught.exception.status, "unavailable")
        self.assertIn("HX711 not ready", str(caught.exception))
        self.assertTrue(scale.needs_reset)

    def test_zero_and_negative_weight_are_returned_for_upper_limit_check(self):
        for raw in (-700000, -695343):
            with self.subTest(raw=raw):
                scale = self.scale([raw] * 11)
                reading = scale.read_weight()
                grams = (raw + 695343) / 199.538
                self.assertAlmostEqual(reading["grams"], grams)
                self.assertEqual(reading["samples"], 10)
                self.assertEqual(reading["spread_g"], 0)

    def test_clock_failure_rejects_then_resets_before_next_measurement(self):
        raw = -695343 + 20 * 199.538
        scale = self.scale([RuntimeError("timing")] + [raw] * 11)
        with self.assertRaises(WeightReadingError):
            scale.read_weight()
        self.assertAlmostEqual(scale.read_weight()["grams"], 20)
        scale.sensor.reset.assert_called_once_with()

    def test_sample_window_has_overall_deadline(self):
        scale = self.scale([0] * 11)
        with patch("machine.weight_sensor.time.monotonic", side_effect=[0, 0, 5]):
            with self.assertRaises(WeightReadingError) as caught:
                scale.read_weight()
        self.assertEqual(caught.exception.status, "unavailable")
        self.assertEqual(scale.sensor.read_raw.call_count, 1)

    def test_invalid_calibration_fails_before_opening_gpio(self):
        for offset, factor in ((float("nan"), 1), (0, 0), (0, float("inf"))):
            with self.assertRaises(ValueError):
                CalibratedScale(offset, factor)

    def test_partial_gpio_claim_failure_releases_handle(self):
        import sys
        gpio = Mock()
        gpio.gpio_claim_output.side_effect = RuntimeError("GPIO busy")
        scale = CalibratedScale(-695343, 199.538)
        with patch.dict(sys.modules, {"lgpio": gpio}), \
             patch("machine.weight_sensor.open_header", return_value=0):
            with self.assertRaisesRegex(RuntimeError, "GPIO busy"):
                scale.open()
        gpio.gpiochip_close.assert_called_once_with(0)
        gpio.gpio_write.assert_not_called()
        scale.close()
        gpio.gpiochip_close.assert_called_once_with(0)


if __name__ == "__main__":
    unittest.main()
