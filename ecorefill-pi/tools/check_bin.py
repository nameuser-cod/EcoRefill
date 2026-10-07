"""Read the center bin sensor without operating servos, pump or Firebase."""

import argparse
import time

from machine.bin_monitor import BinSettings
from machine.ultrasonic import BinUltrasonicSensor


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", help="Bin JSON settings, otherwise ECOREFILL_BIN_CONFIG or defaults")
    args = parser.parse_args()
    settings = BinSettings.from_file(args.config)
    sensor = BinUltrasonicSensor(settings.trig_gpio, settings.echo_gpio)
    try:
        sensor.open()
        print(f"Bin sensor: TRIG={settings.trig_gpio}, ECHO={settings.echo_gpio}; "
              f"full <= {settings.full_distance_cm:g} cm, clear >= {settings.clear_distance_cm:g} cm.")
        while True:
            distance = sensor.distance_cm()
            print("NO ECHO" if distance is None else f"Distance: {distance:.1f} cm", flush=True)
            time.sleep(settings.poll_seconds)
    except KeyboardInterrupt:
        pass
    finally:
        sensor.close()


if __name__ == "__main__":
    main()
