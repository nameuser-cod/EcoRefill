"""Save an original camera frame and user-supplied material label, without GPIO.

This creates a material-evaluation CSV, not bounding-box training annotations.
Keep every view of the same physical container in the same dataset split.
"""

import argparse
import csv
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--expected", choices=("plastic_bottle", "aluminum_can", "reject"), required=True)
    parser.add_argument("--group", required=True, help="Physical container/session ID")
    args = parser.parse_args()
    if args.output.exists() or args.output.suffix.lower() not in {".jpg", ".png"}:
        parser.error("Choose a new .jpg or .png output file")
    if not args.group.strip():
        parser.error("--group cannot be empty")
    if args.manifest.exists():
        with args.manifest.open(newline="") as handle:
            if csv.DictReader(handle).fieldnames != ["image", "expected", "group"]:
                parser.error("Existing manifest must have image,expected,group columns")
    import cv2
    from machine.camera import CameraSupport

    cv2.setNumThreads(1)
    camera = CameraSupport().initialize_camera()
    try:
        frame = camera.capture_array("main")
    finally:
        camera.stop()
        camera.close()
    encoded, buffer = cv2.imencode(args.output.suffix, frame)
    if not encoded:
        raise RuntimeError("Unable to encode original camera image")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("xb") as handle:
        handle.write(buffer.tobytes())
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    write_header = not args.manifest.exists()
    with args.manifest.open("a", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["image", "expected", "group"])
        if write_header:
            writer.writeheader()
        writer.writerow({"image": str(args.output.resolve()), "expected": args.expected, "group": args.group})
    print(f"Saved {args.output} at {frame.shape[1]}x{frame.shape[0]} with user label {args.expected}.")


if __name__ == "__main__":
    main()
