"""
Centralised logging setup for the Multi-Agent Procurement Management System.

Provides a factory function `get_logger(name)` that returns a Python logger
pre-configured with:
  - A rotating file handler writing to logs/execution.log
  - A console handler for real-time visibility during development
"""

import logging
import logging.handlers
from pathlib import Path

from src.config import LOG_FILE, LOG_FORMAT, LOG_DATE_FORMAT, LOG_LEVEL

# Track whether root logger has already been configured, so we do not add
# duplicate handlers on repeated imports or test runs.
_CONFIGURED: bool = False


def _configure_root_logger() -> None:
    """Configure the root procurement logger once."""
    global _CONFIGURED
    if _CONFIGURED:
        return

    root_logger = logging.getLogger("procurement")
    root_logger.setLevel(getattr(logging, LOG_LEVEL.upper(), logging.INFO))

    formatter = logging.Formatter(fmt=LOG_FORMAT, datefmt=LOG_DATE_FORMAT)

    # ── File handler (rotating, max 5 MB × 3 backups) ───────────────────────
    Path(LOG_FILE).parent.mkdir(parents=True, exist_ok=True)
    file_handler = logging.handlers.RotatingFileHandler(
        filename=str(LOG_FILE),
        maxBytes=5 * 1024 * 1024,  # 5 MB
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.DEBUG)

    # ── Console handler ──────────────────────────────────────────────────────
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(getattr(logging, LOG_LEVEL.upper(), logging.INFO))

    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    """
    Return a named child logger under the 'procurement' namespace.

    Args:
        name: Dot-separated module/component name, e.g. 'agents.coordinator'.

    Returns:
        A configured logging.Logger instance.
    """
    _configure_root_logger()
    return logging.getLogger(f"procurement.{name}")
