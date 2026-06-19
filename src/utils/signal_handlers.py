# ----------------------------------------------------------------------
# SQL Schema Studio 0.9 - Signal Handlers (GPLv3)
# Copyright (C) 2026 Peter Leukanič
# License: GNU GPL v3+ <https://www.gnu.org/licenses/gpl-3.0.txt>
# This is free software with NO WARRANTY.
# Feel free to distribute and modify.
# ----------------------------------------------------------------------

"""OS signal handlers and graceful shutdown"""

from __future__ import annotations

import sys
from typing import Any, NoReturn


def handle_sigint(signum: int, frame: Any) -> NoReturn:
    """Handle SIGINT (Ctrl+C) gracefully"""
    sys.stdout.write("\033[0m\n")
    sys.stdout.write("Program interrupted. Exiting gracefully...\n")
    sys.stdout.flush()
    sys.exit(128 + signum)
