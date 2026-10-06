"""Refund unused pump time in half-points; elapsed time is not measured volume."""

from decimal import Decimal, ROUND_FLOOR
import math

from .points import read_points


def timed_refund(points, timing):
    points = read_points(points)
    if timing.get("timingReliable") is not True:
        raise ValueError("Dispensing time is uncertain; owner review required.")
    elapsed = timing.get("pumpOnSeconds")
    if type(elapsed) not in (int, float) or not math.isfinite(elapsed) or elapsed < 0:
        raise ValueError("Invalid dispensing time; owner review required.")
    if timing.get("pumpStarted") is False and elapsed == 0:
        return points
    if timing.get("pumpStarted") is not True:
        raise ValueError("Pump start is uncertain; owner review required.")
    planned = timing.get("plannedPumpSeconds")
    if type(planned) not in (int, float) or not math.isfinite(planned) or planned <= 0:
        raise ValueError("Invalid planned dispensing time; owner review required.")
    # A started pump retains at least half a point, including sub-tick stops.
    fraction = min(Decimal(1), Decimal(str(elapsed)) / Decimal(str(planned)))
    units = (Decimal(str(points)) * 2 * (1 - fraction)).to_integral_value(rounding=ROUND_FLOOR)
    return min(points - 0.5, int(units) / 2) if points else 0
