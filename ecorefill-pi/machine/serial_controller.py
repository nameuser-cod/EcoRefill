"""ESP32 discovery, sorting commands, and water acknowledgements."""

import time
from .config import (
    SERIAL_BAUD_RATE,
    SERIAL_TIMEOUT,
    WATER_COMMANDS,
    WATER_COMMAND_TIMEOUT_SECONDS,
)
from .diagnostics import log


class SerialController:
    """Methods composed into MachineRuntime; shared resources live on that instance."""

    def find_esp32_port(self):
        from serial.tools import list_ports

        ports = list(list_ports.comports())

        keywords = [
            "cp210",
            "ch340",
            "ch910",
            "usb serial",
            "uart",
            "esp32",
        ]

        for port in ports:
            description = (port.description or "").lower()

            if any(keyword in description for keyword in keywords):
                return port.device

        for port in ports:
            if (
                port.device.startswith("/dev/ttyUSB")
                or port.device.startswith("/dev/ttyACM")
            ):
                return port.device

        return None

    def connect_to_esp32(self):
        import serial

        port = self.find_esp32_port()

        if port is None:
            log("ESP32 not detected. Detection will still work.")
            return None

        try:
            connection = serial.Serial(
                port=port,
                baudrate=SERIAL_BAUD_RATE,
                timeout=SERIAL_TIMEOUT,
            )
            time.sleep(2)
            connection.reset_input_buffer()
            connection.reset_output_buffer()
            log(f"ESP32 connected on {port}")
            return connection

        except serial.SerialException as error:
            log(f"ESP32 connection failed: {error}")
            return None

    def get_esp32_connection(self):
        """Return a live ESP32 serial connection, reconnecting when needed."""

        with self.esp32_connection_lock:
            if self.esp32 is not None:
                try:
                    if self.esp32.is_open:
                        return self.esp32
                except Exception:
                    pass

                try:
                    self.esp32.close()
                except Exception:
                    pass

                self.esp32 = None

            self.esp32 = self.connect_to_esp32()
            return self.esp32

    def mark_esp32_disconnected(self, connection=None):
        """Forget a failed serial connection so the next command reconnects."""

        with self.esp32_connection_lock:
            target = connection or self.esp32
            if target is not None:
                try:
                    target.close()
                except Exception:
                    pass

            if connection is None or connection is self.esp32:
                self.esp32 = None

    def send_to_esp32(self, command):
        import serial

        command = command.upper().strip()

        allowed_commands = {
            "BOTTLE",
            "CAN",
            "REJECT",
            "RESET",
            "WATER_250",
            "WATER_500",
            "WATER_1000",
        }

        if command not in allowed_commands:
            log(f"Blocked unknown ESP32 command: {command}")
            return False

        connection = self.get_esp32_connection()
        if connection is None:
            log(f"ESP32 unavailable. Skipping command: {command}")
            return False

        try:
            with self.serial_lock:
                # Sorting commands should be fire-and-forget. Waiting for
                # readline() here can pause recycling for the full serial timeout
                # if the ESP32 does not immediately send a reply.
                connection.write(f"{command}\n".encode("utf-8"))
                connection.flush()

            log(f"Sent to ESP32: {command}")
            return True

        except (serial.SerialException, OSError) as error:
            log(f"Serial error: {error}")
            self.mark_esp32_disconnected(connection)
            return False

    def run_water_command(self, command, on_dispensing=None):
        """
        Send a water command and wait for the ESP32's final response.

        Improvements:
        - Converts low-level PySerial disconnect errors into kiosk-friendly codes.
        - Automatically reconnects once if the ESP32 USB serial connection drops
          BEFORE dispensing starts.
        - Never retries a water command after DISPENSING has started, because doing
          so could dispense water twice.
        """
        import serial

        command = command.upper().strip()

        if command not in set(WATER_COMMANDS.values()):
            return False, f"INVALID_COMMAND: {command}"

        dispensing_response = f"DISPENSING {command}"
        completed_response = f"OK {command}"
        error_response = f"ERROR {command}"
        deadline = time.monotonic() + WATER_COMMAND_TIMEOUT_SECONDS

        # Only one automatic resend is allowed, and only before water starts.
        max_connection_attempts = 2
        attempt = 0
        dispensing_started = False

        while attempt < max_connection_attempts and time.monotonic() < deadline:
            attempt += 1

            connection = self.get_esp32_connection()

            if connection is None:
                if attempt < max_connection_attempts:
                    log("ESP32 unavailable. Retrying connection...")
                    time.sleep(1)
                    continue

                return False, "ESP32_DISCONNECTED"

            try:
                with self.serial_lock:
                    connection.reset_input_buffer()
                    connection.write(f"{command}\n".encode("utf-8"))
                    connection.flush()

                    log(
                        f"Water command sent to ESP32 "
                        f"(attempt {attempt}/{max_connection_attempts}): {command}"
                    )

                    while time.monotonic() < deadline:
                        try:
                            raw_response = connection.readline()
                        except (serial.SerialException, OSError) as read_error:
                            log("ESP32 serial read failed:", read_error)
                            raise

                        response = raw_response.decode(
                            "utf-8",
                            errors="ignore",
                        ).strip()

                        if not response:
                            continue

                        log(f"ESP32: {response}")
                        normalized_response = response.upper()

                        if normalized_response == dispensing_response:
                            if not dispensing_started:
                                dispensing_started = True

                                if on_dispensing is not None:
                                    try:
                                        on_dispensing()
                                    except Exception as error:
                                        log(
                                            "Could not mark refill as dispensing:",
                                            error,
                                        )

                            continue

                        if normalized_response == completed_response:
                            return True, None

                        if normalized_response.startswith(error_response):
                            # Preserve firmware error codes such as:
                            # ERROR WATER_500 NO_BOTTLE
                            # ERROR WATER_500 SENSOR_LOST
                            # ERROR WATER_500 CONTAINER_REMOVED
                            return False, response

            except (serial.SerialException, OSError) as error:
                log(
                    f"Water serial error on attempt {attempt}: "
                    f"{repr(error)}"
                )

                self.mark_esp32_disconnected(connection)

                # SAFETY: once dispensing has begun, never resend the command.
                # The ESP32 may still have completed the physical refill even
                # though the Pi lost the serial connection.
                if dispensing_started:
                    return False, "ESP32_DISCONNECTED_DURING_DISPENSING"

                if attempt < max_connection_attempts:
                    log(
                        "ESP32 disconnected before dispensing. "
                        "Waiting for USB serial to recover..."
                    )

                    # Give the ESP32 time to reboot and re-enumerate its USB port.
                    reconnect_deadline = time.monotonic() + 5

                    while time.monotonic() < reconnect_deadline:
                        time.sleep(0.5)

                        if self.get_esp32_connection() is not None:
                            log("ESP32 serial connection recovered.")
                            break

                    continue

                return False, "ESP32_DISCONNECTED"

        return False, "WATER_TIMEOUT"
