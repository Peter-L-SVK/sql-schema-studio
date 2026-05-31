# ----------------------------------------------------------------------
# SQL Schema Studio 0.6 - Package Root (GPLv3)
# Copyright (C) 2026 Peter Leukanič
# License: GNU GPL v3+ <https://www.gnu.org/licenses/gpl-3.0.txt>
# This is free software with NO WARRANTY.
# Feel free to distribute and modify.
# ----------------------------------------------------------------------

"""SQL Schema Studio — Intelligent PostgreSQL Management Platform."""

import logging
import sys

# Root logger — use INFO for release, DEBUG for development
_root_logger = logging.getLogger("sql_schema_studio")
_root_logger.setLevel(logging.DEBUG)

_handler = logging.StreamHandler(sys.stderr)
_handler.setFormatter(
    logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
)
_root_logger.addHandler(_handler)

# Silence noisy third-party loggers
logging.getLogger("psycopg").setLevel(logging.WARNING)
logging.getLogger("psycopg.pool").setLevel(logging.ERROR)
