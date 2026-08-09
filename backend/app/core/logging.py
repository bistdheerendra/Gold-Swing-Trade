"""Structured application logging."""

import logging
import sys
from typing import Optional


def configure_logging(level: str = "INFO") -> None:
    root = logging.getLogger()
    if root.handlers:
        return

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S",
        )
    )
    root.addHandler(handler)
    root.setLevel(level.upper())


def get_logger(name: Optional[str] = None) -> logging.Logger:
    return logging.getLogger(name or "gold_swing_ai")
