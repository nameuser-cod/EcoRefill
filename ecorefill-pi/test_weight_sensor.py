"""Protocol and calibration checks without GPIO hardware."""

import unittest
from unittest.mock import Mock, patch

from check_weight import calibration_factor
from weight_sensor import HX711, CalibratedScale, WeightReadingError


class WeightSensorTests(unittest.TestCase):
    def read_word(self, word, final_level=1):
        gpio = Mock()
        bits = [(word >> bit) & 1 for bit in range(23, -1, -1)]
        gpio.gpio_read.side_effect = [0, *bits, final_level]
        sensor = HX711(gpio, 0)
        with patch("weight_sensor.time.monotonic_ns", return_value=0):
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
        with patch("weight_sensor.time.monotonic", side_effect=[0, 3]):
            with self.assertRaises(TimeoutError):
                HX711(gpio, 0).read_raw()
        gpio.gpio_write.assert_not_called()

    def test_long_clock_pulse_is_rejected_and_clock_lowered(self):
        gpio = Mock()
        with patch("weight_sensor.time.monotonic_ns", side_effect=[0, 61000]):
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


class CalibratedScaleTests(unittest.TestCase):
    def scale(self, readings, factor=414.59):
        scale = CalibratedScale(-639408, factor)
        scale.sensor = Mock()
        scale.sensor.read_raw.side_effect = readings
        return scale

    def test_fresh_window_discards_old_conversion_and_uses_saved_calibration(self):
        for factor in (414.59, -414.59):
            raw = -639408 + 40 * factor
            scale = self.scale([123456] + [raw] * 10, factor)
            reading = scale.read_weight()
            self.assertAlmostEqual(reading["grams"], 40)
            self.assertEqual(reading["spread_g"], 0)
            self.assertEqual(scale.offset, -639408)  # Never tare with an item present.

    def test_unstable_window_and_negative_weight_are_rejected(self):
        scale = self.scale([0] + [-639408 + g * 414.59 for g in range(20, 30)])
        with self.assertRaises(WeightReadingError) as caught:
            scale.read_weight()
        self.assertEqual(caught.exception.status, "unstable")
        scale = self.scale([-650000] * 11)
        with self.assertRaises(WeightReadingError) as caught:
            scale.read_weight()
        self.assertEqual(caught.exception.status, "invalid")

    def test_clock_failure_rejects_then_resets_before_next_measurement(self):
        raw = -639408 + 20 * 414.59
        scale = self.scale([RuntimeError("timing")] + [raw] * 11)
        with self.assertRaises(WeightReadingError):
            scale.read_weight()
        self.assertAlmostEqual(scale.read_weight()["grams"], 20)
        scale.sensor.reset.assert_called_once_with()

    def test_sample_window_has_overall_deadline(self):
        scale = self.scale([0] * 11)
        with patch("weight_sensor.time.monotonic", side_effect=[0, 0, 5]):
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
        scale = CalibratedScale(-639408, 414.59)
        with patch.dict(sys.modules, {"lgpio": gpio}), \
             patch("weight_sensor.open_header", return_value=0):
            with self.assertRaisesRegex(RuntimeError, "GPIO busy"):
                scale.open()
        gpio.gpiochip_close.assert_called_once_with(0)
        gpio.gpio_write.assert_not_called()
        scale.close()
        gpio.gpiochip_close.assert_called_once_with(0)


if __name__ == "__main__":
    unittest.main()
