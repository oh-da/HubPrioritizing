"""
Logging configuration for Hub Prioritization Framework.

Single Responsibility: Configure and manage logging.
"""

import logging
import sys
from pathlib import Path


def setup_logging(
    level: int = logging.INFO,
    log_file: Path | None = None,
    format_string: str | None = None
) -> None:
    """
    Configure logging for the application.

    Args:
        level: Logging level (e.g., logging.INFO, logging.DEBUG)
        log_file: Optional file path for log output
        format_string: Optional custom format string
    """
    if format_string is None:
        format_string = (
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )

    handlers = [logging.StreamHandler(sys.stdout)]

    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(log_file))

    logging.basicConfig(
        level=level,
        format=format_string,
        handlers=handlers
    )


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance.

    Args:
        name: Logger name (typically __name__)

    Returns:
        Logger instance
    """
    return logging.getLogger(name)
