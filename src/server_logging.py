"""Logging configuration and utilities."""

import logging
import sys
from pathlib import Path
from typing import Optional

from .config import get_settings


def setup_logging(log_level: Optional[str] = None, log_file: Optional[str] = None) -> None:
    """Setup application logging configuration.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Path to log file
    """
    settings = get_settings()

    level = getattr(logging, (log_level or settings.log_level).upper())
    file_path = log_file or settings.log_file

    # Create logs directory if it doesn't exist
    log_path = Path(file_path)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    # Configure logging
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s",
        handlers=[
            logging.FileHandler(file_path),
            logging.StreamHandler(sys.stdout),
        ],
    )

    # Set third-party loggers to WARNING to reduce noise
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance with the specified name.

    Args:
        name: Logger name (typically __name__)

    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)
