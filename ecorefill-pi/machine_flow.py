"""Launch the EcoRefill Pi controller: python3 machine_flow.py.

Implementation and debugging notes: machine/ and DEBUGGING.md.
Importing this entry point does not initialize hardware or start workers.
"""

from machine.diagnostics import configure_logging
from machine.runtime import MachineRuntime


def main():
    configure_logging()
    MachineRuntime().run()


if __name__ == "__main__":
    main()
