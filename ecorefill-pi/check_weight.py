"""Standalone HX711 diagnostic for Pi 5; no camera, Firebase, or motors."""

import argparse
import math
import sys

from weight_sensor import HX711, open_header


def calibration_factor(zero, loaded, grams, noise):
    if not math.isfinite(grams) or not 0 < grams < 1000:
        raise ValueError("Use a known mass greater than 0 and below 1000 grams.")
    if abs(loaded - zero) <= max(1, 10 * noise):
        raise ValueError(
            "Load change is too small compared with noise. Check mounting, "
            "let the platform settle, and retry."
        )
    return (loaded - zero) / grams


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--calibrate", action="store_true",
                        help="tare, measure a known mass, then display grams")
    args = parser.parse_args()
    try:
        import lgpio
    except ImportError:
        print("On the Pi run: sudo apt install python3-lgpio\n"
              "Then run this script with /usr/bin/python3.", file=sys.stderr)
        return 1

    handle = None
    clock_claimed = False
    try:
        handle = open_header(lgpio)
        lgpio.gpio_claim_input(handle, 5, lgpio.SET_PULL_UP)
        lgpio.gpio_claim_output(handle, 6, 0)
        clock_claimed = True
        sensor = HX711(lgpio, handle)
        sensor.reset()
        print("DT=GPIO5 (pin 29), SCK=GPIO6 (pin 31). Ctrl+C exits.", flush=True)
        zero, factor = 0, None
        if args.calibrate:
            input("Remove all items from the platform, let it settle, then press Enter: ")
            sensor.read_raw()  # Discard the conversion buffered before the prompt.
            zero, empty_noise = sensor.sample()
            print(f"Empty reading: {zero}; spread: {empty_noise} raw counts")
            grams = float(input("Enter the known calibration mass in grams (e.g. 100): "))
            if not math.isfinite(grams) or not 0 < grams < 1000:
                raise ValueError("Calibration mass must be greater than 0 and below 1000 g.")
            input("Place that mass on the platform, let it settle, then press Enter: ")
            sensor.read_raw()
            loaded, loaded_noise = sensor.sample()
            factor = calibration_factor(zero, loaded, grams, max(empty_noise, loaded_noise))
            print(f"Offset: {zero}; calibration factor: {factor:.8f} counts/gram")
            print("Save these numbers. Calibration is for this session only.")
            print("Remove the mass: the display should return close to 0 g.")
        else:
            print("RAW COUNTS, not grams. Place and remove a light object to check response.")
        while True:
            value, spread = sensor.sample(5)
            if factor is None:
                print(f"Raw: {value:12.0f}   spread: {spread}", flush=True)
            else:
                print(f"Weight: {(value - zero) / factor:9.1f} g", flush=True)
    except (KeyboardInterrupt, EOFError):
        print("\nStopped.")
        return 0
    except (lgpio.error, OSError, RuntimeError, ValueError) as error:
        print(f"Weight check failed: {error}", file=sys.stderr)
        return 1
    finally:
        if handle is not None:
            try:
                if clock_claimed:
                    lgpio.gpio_write(handle, 6, 0)
            finally:
                lgpio.gpiochip_close(handle)


if __name__ == "__main__":
    raise SystemExit(main())
