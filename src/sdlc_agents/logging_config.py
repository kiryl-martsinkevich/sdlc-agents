"""Logging configuration for SDLC agents."""

import logging
import sys
from pathlib import Path

from rich.console import Console
from rich.logging import RichHandler

from sdlc_agents.config import settings


def setup_logging() -> logging.Logger:
    """Configure logging with rich output and file handler."""
    # Create logs directory
    log_path = Path(settings.log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    # Configure root logger
    logger = logging.getLogger("sdlc_agents")
    logger.setLevel(settings.log_level)

    # Remove existing handlers
    logger.handlers.clear()

    # Rich console handler for terminal output
    console_handler = RichHandler(
        console=Console(stderr=True),
        rich_tracebacks=True,
        tracebacks_show_locals=True,
    )
    console_handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(console_handler)

    # File handler for persistent logs
    file_handler = logging.FileHandler(log_path)
    file_handler.setFormatter(
        logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    logger.addHandler(file_handler)

    return logger


# Global logger instance
logger = setup_logging()
