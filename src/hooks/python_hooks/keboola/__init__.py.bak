# ----------------------------------------------------------------------
# SQL Schema Studio 0.9 - Keboola Package (GPLv3)
# Copyright (C) 2026 Peter Leukanič
# License: GNU GPL v3+ <https://www.gnu.org/licenses/gpl-3.0.txt>
# This is free software with NO WARRANTY.
# Feel free to distribute and modify.
# ----------------------------------------------------------------------

"""Keboola integration package — client, profiles, engines.

Pipeline is intentionally NOT re-exported here to avoid import cycles
and to keep this module lightweight. Import it explicitly when needed:

    from src.hooks.python_hooks.keboola.pipeline import TransformationPipeline
"""

from src.hooks.python_hooks.keboola.client import KeboolaClient, KeboolaError
from src.hooks.python_hooks.keboola.profiles import ProfileManager, KeboolaProfile
from src.hooks.python_hooks.keboola.engines import ENGINES, get_engine, list_engines

__all__ = [
    "KeboolaClient",
    "KeboolaError",
    "ProfileManager",
    "KeboolaProfile",
    "ENGINES",
    "get_engine",
    "list_engines",
]
