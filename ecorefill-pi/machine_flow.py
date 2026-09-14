"""Launch the EcoRefill Pi controller: python3 machine_flow.py.

Implementation and debugging notes: machine/ and DEBUGGING.md.
Importing this entry point does not initialize hardware or start workers.
"""

from machine.diagnostics import configure_logging
from machine.runtime import MachineRuntime
import signal


def terminate(*_):
    raise SystemExit(0)


def main():
    configure_logging()
    # Route service-manager termination through run()'s hardware cleanup.
    signal.signal(signal.SIGTERM, terminate)
    MachineRuntime().run()


if __name__ == "__main__":
    main()
