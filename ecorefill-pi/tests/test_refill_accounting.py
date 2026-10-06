"""Financial boundaries for timed refunds, including rounding and unsafe data."""

import unittest

from machine.refill_accounting import timed_refund


class TimedRefundTests(unittest.TestCase):
    def test_proportional_refund_and_half_point_rounding(self):
        for elapsed, expected in ((0, 9.5), (0.01, 9.5), (1.25, 9.5), (1.251, 9),
                                  (12.5, 5), (24, 0), (25, 0), (26, 0)):
            with self.subTest(elapsed=elapsed):
                self.assertEqual(timed_refund(10, {
                    "pumpStarted": True, "pumpOnSeconds": elapsed,
                    "plannedPumpSeconds": 25, "timingReliable": True,
                }), expected)

    def test_unstarted_pump_refunds_full_cost_without_duration(self):
        self.assertEqual(timed_refund(10, {
            "pumpStarted": False, "pumpOnSeconds": 0, "timingReliable": True,
        }), 10)

    def test_invalid_or_uncertain_timing_requires_review(self):
        valid = {"pumpStarted": True, "pumpOnSeconds": 12.5,
                 "plannedPumpSeconds": 25, "timingReliable": True}
        for field, value in (("pumpOnSeconds", -1), ("pumpOnSeconds", float("nan")),
                             ("pumpOnSeconds", True), ("plannedPumpSeconds", 0),
                             ("plannedPumpSeconds", float("inf")), ("pumpStarted", False),
                             ("pumpStarted", None), ("timingReliable", False)):
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                timed_refund(10, {**valid, field: value})
        with self.assertRaises(ValueError):
            timed_refund(10, {})
