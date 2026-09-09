"""Shared camera region for motion sensing and material inference."""

import math

from .config import DETECTION_REGION


def scan_region_bounds(frame):
    height, width = frame.shape[:2]
    if DETECTION_REGION is None:
        return 0, 0, width, height
    left, top, right, bottom = DETECTION_REGION
    if not all(math.isfinite(value) for value in DETECTION_REGION) or not (
        0 <= left < right <= 1 and 0 <= top < bottom <= 1
    ):
        raise ValueError("DETECTION_REGION must be ordered fractions between 0 and 1.")
    bounds = (round(left * width), round(top * height),
              round(right * width), round(bottom * height))
    if bounds[0] >= bounds[2] or bounds[1] >= bounds[3]:
        raise ValueError("DETECTION_REGION is too small for this camera frame.")
    return bounds
