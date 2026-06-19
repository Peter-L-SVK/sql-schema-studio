# ----------------------------------------------------------------------
# SQL Schema Studio 0.8 - SSH Tunnel Support (GPLv3)
# Copyright (C) 2026 Peter Leukanič
# License: GNU GPL v3+ <https://www.gnu.org/licenses/gpl-3.0.txt>
# This is free software with NO WARRANTY.
# Feel free to distribute and modify.
# ----------------------------------------------------------------------

"""SSH tunnel support for remote PostgreSQL connections.

NOTE: This is a stub for v0.8.0. Full SSH tunnel implementation
is planned for v0.9.0 or later. Requires paramiko library.
"""

from src.utils.logging import get_logger

logger = get_logger(__name__)


class SSHTunnel:
    """Stub for SSH tunnel support."""

    def __init__(self, config=None):
        self.config = config

    def start(self):
        logger.warning("SSH tunnel support not yet implemented (planned for v0.9.0)")
        return False, None, "SSH tunnel support not yet implemented"


def get_postgres_conn_string_with_ssh(ssh_config, db_config):
    """Stub for SSH tunnel connection string."""
    logger.warning("SSH tunnel support not yet implemented")
    return "", None, "SSH tunnel support not yet implemented"
