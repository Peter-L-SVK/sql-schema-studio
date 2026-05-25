#!/usr/bin/env python3

# ----------------------------------------------------------------------
# SQL Schema Studio - Main Entry Point (GPLv3)
# Copyright (C) 2026 Peter Leukanič
# License: GNU GPL v3+ <https://www.gnu.org/licenses/gpl-3.0.txt>
# This is free software with NO WARRANTY.
# Feel free to distribute and modify.
# ----------------------------------------------------------------------

"""Application entry point"""

from __future__ import annotations

import logging
import sys
import signal

from src.app import Application
from src.utils.signal_handlers import handle_sigint
from src.utils.logging import configure_root_logger, get_logger


def main():
    configure_root_logger(logging.INFO)
    logger = get_logger(__name__)
    logger.info("Starting SQL Schema Studio...")
    signal.signal(signal.SIGINT, handle_sigint)
    app = Application()
    return app.run(sys.argv)


if __name__ == "__main__":
    sys.exit(main())
