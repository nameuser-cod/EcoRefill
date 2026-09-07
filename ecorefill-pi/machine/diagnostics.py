"""Timestamped controller logs with thread, source location, and tracebacks."""

import logging
import os
import sys


def configure_logging():
    logging.basicConfig(
        level=os.getenv("ECOREFILL_LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s [%(threadName)s] %(filename)s:%(lineno)d %(message)s",
    )


def log(*parts):
    """Keep existing messages and include a traceback inside exception handlers."""
    error = sys.exc_info()[0] is not None
    logging.getLogger("ecorefill.machine").log(
        logging.ERROR if error else logging.INFO,
        " ".join(str(part) for part in parts),
        exc_info=error,
        stacklevel=2,
    )
