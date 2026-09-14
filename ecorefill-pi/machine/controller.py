"""Route machine commands directly to the Raspberry Pi GPIO controller."""

from .config import WATER_COMMANDS
from .diagnostics import log


class ControllerCommands:
    """Methods composed into MachineRuntime; GPIOController owns serialization."""

    def send_command(self, command):
        command = command.strip().upper()
        if command not in {"BOTTLE", "CAN", "REJECT", "RESET", *WATER_COMMANDS.values()}:
            log(f"Blocked unknown GPIO command: {command}")
            return False
        if self.gpio_controller is None or self.shutdown_event.is_set():
            log(f"GPIO controller unavailable. Cannot run command: {command}")
            return False
        # Wait for sorting to finish before the camera rearms or points accrue.
        ok, error = self.gpio_controller.execute(command)
        if error:
            log("GPIO command failed:", error)
        return ok

    def run_water_command(self, command, on_dispensing=None):
        command = command.strip().upper()
        if command not in set(WATER_COMMANDS.values()):
            return False, f"INVALID_COMMAND: {command}"
        if self.gpio_controller is None or self.shutdown_event.is_set():
            return False, "GPIO_CONTROLLER_UNAVAILABLE"
        # Never automatically retry a physical refill.
        return self.gpio_controller.execute(command, on_dispensing=on_dispensing)
