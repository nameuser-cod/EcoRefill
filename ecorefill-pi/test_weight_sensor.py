"""Protocol and calibration checks without GPIO hardware."""

import unittest
from unittest.mock import Mock, patch

from check_weight import HX711, calibration_factor


class WeightSensorTests(unittest.TestCase):
    def read_word(self, word, final_level=1):
        gpio = Mock()
        bits = [(word >> bit) & 1 for bit in range(23, -1, -1)]
        gpio.gpio_read.side_effect = [0, *bits, final_level]
        sensor = HX711(gpio, 0)
        with patch("check_weight.time.monotonic_ns", return_value=0):
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
        with patch("check_weight.time.monotonic", side_effect=[0, 3]):
            with self.assertRaises(TimeoutError):
                HX711(gpio, 0).read_raw()
        gpio.gpio_write.assert_not_called()

    def test_long_clock_pulse_is_rejected_and_clock_lowered(self):
        gpio = Mock()
        with patch("check_weight.time.monotonic_ns", side_effect=[0, 61000]):
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


if __name__ == "__main__":
    unittest.main()
