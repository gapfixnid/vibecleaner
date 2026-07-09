"""Central logging setup for vibecleaner."""

from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler

from ..storage.paths import get_user_data_dir

LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
DEFAULT_LOG_LEVEL = logging.INFO
LOG_FILE_NAME = "vibecleaner.log"

_configured = False


def configure_logging(level: int = DEFAULT_LOG_LEVEL) -> None:
    """Configure console and rotating file logging once per process."""
    global _configured
    if _configured:
        return

    log_dir = os.path.join(get_user_data_dir(), "logs")
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, LOG_FILE_NAME)

    formatter = logging.Formatter(LOG_FORMAT)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    file_handler = RotatingFileHandler(
        log_path,
        maxBytes=2 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)

    _configured = True