"""Relay diagnostic regressions with no energized hardware."""

import unittest
from unittest.mock import Mock, call, patch

from check_relay import test_relay


class RelayDiagnosticTests(unittest.TestCase):
    def setUp(self):
        self.gpio = Mock()
        header = patch("check_relay.open_header", return_value=9)
        header.start()
        self.addCleanup(header.stop)
        sleep = patch("check_relay.time.sleep")
        self.sleep = sleep.start()
        self.addCleanup(sleep.stop)

    def test_three_bounded_pulses_start_and_finish_off(self):
        test_relay(self.gpio)
        self.gpio.gpio_claim_output.assert_called_once_with(9, 22, 1)
        self.assertEqual(self.gpio.gpio_write.call_args_list,
                         [call(9, 22, 0), call(9, 22, 1)] * 3 + [call(9, 22, 1)])
        self.assertEqual(self.sleep.call_args_list,
                         [call(2)] + [call(1), call(2)] * 3)
        self.gpio.gpiochip_close.assert_called_once_with(9)

    def test_interrupt_during_on_stops_and_releases(self):
        self.sleep.side_effect = [None, KeyboardInterrupt]
        with self.assertRaises(KeyboardInterrupt):
            test_relay(self.gpio)
        self.assertEqual(self.gpio.gpio_write.call_args_list,
                         [call(9, 22, 0), call(9, 22, 1)])
        self.gpio.gpiochip_close.assert_called_once_with(9)

    def test_busy_pin_is_never_written(self):
        self.gpio.gpio_claim_output.side_effect = OSError("GPIO busy")
        with self.assertRaisesRegex(OSError, "GPIO busy"):
            test_relay(self.gpio)
        self.gpio.gpio_write.assert_not_called()
        self.gpio.gpiochip_close.assert_called_once_with(9)

    def test_failed_off_write_still_closes_handle_and_reports_failure(self):
        self.sleep.side_effect = RuntimeError("test interrupted")
        self.gpio.gpio_write.side_effect = OSError("write failed")
        with self.assertRaisesRegex(OSError, "write failed"):
            test_relay(self.gpio)
        self.gpio.gpiochip_close.assert_called_once_with(9)


if __name__ == "__main__":
    unittest.main()
