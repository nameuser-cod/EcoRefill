"""Print gallon distance and estimated level without operating the pump or cloud."""

import argparse
import time

from machine.bin_monitor import BinSettings
from machine.ultrasonic import WaterLevelUltrasonicSensor
from machine.water_level import WaterLevelMonitor, WaterLevelSettings


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", help="Water-level JSON; defaults to water-level.local.json")
    args = parser.parse_args()
    settings = WaterLevelSettings.from_file(args.config)
    if not settings.enabled:
        parser.error("Enable water-level monitoring in the JSON config before checking its sensor.")
    settings.validate_bin_pins(BinSettings.from_file())
    monitor = WaterLevelMonitor(settings)
    sensor = WaterLevelUltrasonicSensor(settings.trig_gpio, settings.echo_gpio)
    try:
        sensor.open()
        print(f"Gallon sensor: TRIG={settings.trig_gpio}, ECHO={settings.echo_gpio}. "
              "No echo is assumed 100%; check wiring with a target beyond 20 cm first.")
        while True:
            distance = sensor.distance_cm()
            reading = monitor.observe(distance)
            raw = "NO ECHO" if distance is None else f"{distance:.1f} cm"
            result = "confirming" if reading is None else f"{reading['waterLevel']}% ({reading['waterLevelStatus']})"
            print(f"{raw} -> {result}", flush=True)
            time.sleep(settings.poll_seconds)
    except KeyboardInterrupt:
        pass
    finally:
        sensor.close()


if __name__ == "__main__":
    main()
