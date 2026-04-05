import logging
import sys

LOGGER_NAME = "opslens"
logger = logging.getLogger(LOGGER_NAME)


def configure_logging() -> None:
    if logger.handlers:
        return

    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    )
    handler.setFormatter(formatter)

    logger.setLevel(logging.INFO)
    logger.addHandler(handler)
    logger.propagate = False
