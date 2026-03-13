"""
Logging configuration for the CLO3D AI Design Plugin.
"""

from __future__ import annotations

import logging
import sys

from config.settings import LOG_LEVEL


def setup_logging() -> None:
    """Configure root logger with a sensible format."""
    level = getattr(logging, LOG_LEVEL.upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)-7s] %(name)s — %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stdout,
    )
