"""Check pulse measurements without GPIO hardware."""

import unittest

from check_pwm_signal import EdgeCapture, measure_edges


def edges(width_us=1500, period_us=20000, count=30):
    return [edge for index in range(count) for edge in (
        (1, index * period_us * 1000),
        (0, (index * period_us + width_us) * 1000),
    )]


class PWMSignalTests(unittest.TestCase):
    def test_measures_each_requested_width_at_50_hz(self):
        for pulse in (1300, 1500, 1700):
            ok, message = measure_edges(edges(pulse), pulse)
            self.assertTrue(ok)
            self.assertIn(f"measured {pulse} us, 50.0 Hz", message)

    def test_missing_signal_or_only_one_edge_does_not_pass(self):
        for samples in ([], [(1, 0)], [(0, 10)], edges(count=4)):
            self.assertFalse(measure_edges(samples, 1500)[0])

    def test_wrong_width_or_frequency_does_not_pass(self):
        for samples in (edges(500), edges(period_us=10000), edges(period_us=40000)):
            self.assertFalse(measure_edges(samples, 1500)[0])

    def test_frequent_distorted_pulses_do_not_pass_on_median_alone(self):
        samples = edges()
        for index in range(0, 30, 3):
            level, timestamp = samples[2 * index + 1]
            samples[2 * index + 1] = (level, timestamp + 1_000_000)
        self.assertFalse(measure_edges(samples, 1500)[0])

    def test_timestamp_origin_and_partial_first_pulse_do_not_matter(self):
        samples = [(level, stamp + 1_000_000_000_000) for level, stamp in edges()]
        self.assertTrue(measure_edges(samples[1:], 1500)[0])

    def test_capture_is_bounded_and_ignores_watchdog_events(self):
        capture = EdgeCapture()
        capture.callback(0, 16, 2, 10)
        self.assertEqual(capture.snapshot(), [])
        for level, timestamp in edges(count=300):
            capture.callback(0, 16, level, timestamp)
        self.assertEqual(len(capture.snapshot()), 512)
        capture.clear()
        self.assertEqual(capture.snapshot(), [])


if __name__ == "__main__":
    unittest.main()
