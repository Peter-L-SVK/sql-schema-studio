# ----------------------------------------------------------------------
# SQL Schema Studio 0.6 - Logging Helpers (GPLv3)
# Copyright (C) 2026 Peter Leukanič
# License: GNU GPL v3+ <https://www.gnu.org/licenses/gpl-3.0.txt>
# This is free software with NO WARRANTY.
# Feel free to distribute and modify.
# ----------------------------------------------------------------------

"""Logging utility — get a logger for the calling module."""

import logging
import sys

_LOGGERS: dict[str, logging.Logger] = {}
_ROOT_CONFIGURED = False


def configure_root_logger(level: int = logging.INFO) -> None:
    """Configure the root sql_schema_studio logger."""
    global _ROOT_CONFIGURED
    if _ROOT_CONFIGURED:
        return

    root = logging.getLogger("sql_schema_studio")
    root.setLevel(level)

    # Console handler
    handler = logging.StreamHandler(sys.stderr)
    handler.setLevel(level)

    # Format: timestamp | level | logger_name | message
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )
    handler.setFormatter(formatter)
    root.addHandler(handler)

    _ROOT_CONFIGURED = True


def get_logger(name: str | None = None) -> logging.Logger:
    """Return a child logger of sql_schema_studio."""
    if name is None:
        name = "sql_schema_studio"
    if name not in _LOGGERS:
        _LOGGERS[name] = logging.getLogger(f"sql_schema_studio.{name}")
    return _LOGGERS[name]
