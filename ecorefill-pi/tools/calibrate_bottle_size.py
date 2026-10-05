"""Build an observation config from a reference capture and measured bottle profiles."""

import argparse
import copy
import json
import math
from pathlib import Path


def positive(value):
    if isinstance(value, bool) or not isinstance(value, (float, int)):
        raise ValueError("Measurements must be numbers")
    if not math.isfinite(value) or value <= 0:
        raise ValueError("Measurements must be finite and positive")
    return value


def build_config(reference, width_mm, height_mm, profiles):
    """Calibration is specific to the reference's camera view and bottle position."""
    if not isinstance(reference, dict):
        raise ValueError("Reference metadata must be a JSON object")
    frame = reference.get("frame_size_px")
    if (not isinstance(frame, list) or len(frame) != 2
            or any(type(value) is not int or value < 3 for value in frame)):
        raise ValueError("Reference needs frame_size_px; collect a new capture with the updated controller")
    detection = reference.get("detection", {})
    if not isinstance(detection, dict) or detection.get("item") not in {"plastic_bottle", "pet_bottle"}:
        raise ValueError("Reference must be a recognized plastic bottle")
    box = detection.get("box")
    if not isinstance(box, list) or len(box) != 4:
        raise ValueError("Reference needs a four-coordinate detection box")
    x1, y1, x2, y2 = [positive(value) for value in box]
    if not (0 < x1 < x2 < frame[0] and 0 < y1 < y2 < frame[1]):
        raise ValueError("Reference must show the whole bottle inside the image")
    sx = positive(positive(width_mm) / (x2 - x1))
    sy = positive(positive(height_mm) / (y2 - y1))
    if not isinstance(profiles, list) or not profiles:
        raise ValueError("Provide at least one measured bottle profile")
    profiles = copy.deepcopy(profiles)
    names = set()
    for index, profile in enumerate(profiles):
        if not isinstance(profile, dict):
            raise ValueError("Each profile must be an object")
        name = profile.get("name")
        if not isinstance(name, str) or not name.strip() or name in names:
            raise ValueError("Profile names must be nonempty and unique")
        names.add(name)
        for axis in ("width_mm", "height_mm"):
            bounds = profile.get(axis)
            if not isinstance(bounds, list) or len(bounds) != 2:
                raise ValueError(f"{name}: {axis} needs [minimum, maximum]")
            low, high = [positive(value) for value in bounds]
            if low >= high:
                raise ValueError(f"{name}: {axis} minimum must be below maximum")
        for previous in profiles[:index]:
            if all(max(profile[axis][0], previous[axis][0])
                   <= min(profile[axis][1], previous[axis][1])
                   for axis in ("width_mm", "height_mm")):
                raise ValueError(f"Overlapping profiles: {previous['name']} and {name}; size cannot distinguish them")
    return {
        "mode": "observe",
        "capture_directory": None,
        "size": {
            "enabled": True,
            "materials": ["plastic_bottle", "pet_bottle"],
            "frame_size_px": frame,
            "inspection_region_px": [1, 1, frame[0] - 1, frame[1] - 1],
            "mm_per_pixel_x": sx,
            "mm_per_pixel_y": sy,
            "profiles": {"plastic_bottle": profiles, "pet_bottle": copy.deepcopy(profiles)},
        },
        "cleanliness": {"enabled": False},
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", type=Path, required=True, help="Uncropped-frame metadata JSON from a reference scan")
    parser.add_argument("--width-mm", type=float, required=True, help="Measured horizontal extent of the reference bottle")
    parser.add_argument("--height-mm", type=float, required=True, help="Measured vertical extent of the reference bottle")
    parser.add_argument("--profiles", type=Path, required=True, help="JSON list of measured size profiles")
    parser.add_argument("--output", type=Path, required=True, help="New config path; existing files are never overwritten")
    args = parser.parse_args()
    try:
        config = build_config(json.loads(args.reference.read_text()), args.width_mm,
                              args.height_mm, json.loads(args.profiles.read_text()))
        with args.output.open("x", encoding="utf-8") as target:
            json.dump(config, target, indent=2, allow_nan=False)
            target.write("\n")
    except (OSError, ValueError, TypeError) as error:
        parser.exit(1, f"Calibration failed: {error}\n")
    print(f"Created {args.output} in observe mode. Validate on other physical bottles before enforcing.")
    print("Set ECOREFILL_INSPECTION_CONFIG to this file's absolute path and restart the controller.")


if __name__ == "__main__":
    main()
