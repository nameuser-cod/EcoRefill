"""Click the pump relay three times without initializing servos or sensors.

Stop the machine app and disconnect pump power before running this test.
"""

import signal
import time

from machine.gpio_hardware import RELAY1_GPIO, RELAY_OFF, RELAY_ON
from weight_sensor import open_header


def test_relay(gpio):
    handle = open_header(gpio)
    claimed = False
    try:
        # Claim with OFF immediately; never briefly drive active-low IN1 LOW.
        gpio.gpio_claim_output(handle, RELAY1_GPIO, RELAY_OFF)
        claimed = True
        print(f"GPIO{RELAY1_GPIO}: OFF (HIGH). Pump power must be disconnected.", flush=True)
        time.sleep(2)
        for cycle in range(1, 4):
            print(f"{cycle}/3: ON (LOW), 1 second", flush=True)
            gpio.gpio_write(handle, RELAY1_GPIO, RELAY_ON)
            time.sleep(1)
            gpio.gpio_write(handle, RELAY1_GPIO, RELAY_OFF)
            print(f"{cycle}/3: OFF (HIGH), 2 seconds", flush=True)
            time.sleep(2)
    finally:
        try:
            if claimed:
                gpio.gpio_write(handle, RELAY1_GPIO, RELAY_OFF)
        finally:
            gpio.gpiochip_close(handle)


def main():
    import lgpio

    def terminated(*_):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, terminated)
    try:
        test_relay(lgpio)
    except KeyboardInterrupt:
        print("Interrupted; requested relay OFF and released GPIO.")
        return 130
    print("Done. Confirm three ON/OFF clicks and that the relay is released.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
