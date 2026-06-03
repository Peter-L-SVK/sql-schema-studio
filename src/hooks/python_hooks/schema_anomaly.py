# ----------------------------------------------------------------------
# SQL Schema Studio 0.7 - Schema Anomaly Hook (GPLv3)
# Copyright (C) 2026 Peter Leukanič
# License: GNU GPL v3+ <https://www.gnu.org/licenses/gpl-3.0.txt>
# This is free software with NO WARRANTY.
# Feel free to distribute and modify.
# ----------------------------------------------------------------------

"""Hook that detects poor schema design patterns."""

from src.hooks.base_plugin import BaseHook, HookContext, HookTrigger


class Plugin(BaseHook):
    """Schema anomaly detection hook."""

    def get_metadata(self):
        return {
            "name": "Schema Anomaly Detector",
            "version": "1.0.0",
            "author": "SQL Schema Studio",
            "description": "Detect poor schema design patterns",
            "triggers": [HookTrigger.SCHEMA_CHANGED.value],
        }

    async def execute(self, context: HookContext) -> dict:
        """Analyze schema for common anti-patterns."""
        return {
            "status": "ok",
            "message": "Schema analysis not yet implemented",
        }
