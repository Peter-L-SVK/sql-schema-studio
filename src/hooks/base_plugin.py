# ----------------------------------------------------------------------
# SQL Schema Studio 0.7 - Plugin Base Classes (GPLv3)
# Copyright (C) 2026 Peter Leukanič
# License: GNU GPL v3+ <https://www.gnu.org/licenses/gpl-3.0.txt>
# This is free software with NO WARRANTY.
# Feel free to distribute and modify.
# ----------------------------------------------------------------------

"""
Abstract base plugin interface
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict


class HookTrigger(Enum):
    """Events that can trigger hooks"""

    QUERY_EXECUTED = "query.executed"
    SCHEMA_CHANGED = "schema.changed"
    CONNECTION_OPENED = "connection.opened"
    CONNECTION_CLOSED = "connection.closed"
    MIGRATION_APPLIED = "migration.applied"
    PERFORMANCE_THRESHOLD = "performance.threshold"
    SCHEDULED_INTERVAL = "scheduled.interval"
    APP_STARTUP = "application.startup"
    APP_SHUTDOWN = "application.shutdown"


@dataclass
class HookContext:
    """Context passed to hook execute method"""

    trigger: HookTrigger
    database: str
    connection_pool: Any
    data: Dict[str, Any] = field(default_factory=dict)
    logger: Any = None


class BaseHook(ABC):
    """Base class for all hooks (Python and Perl)"""

    @abstractmethod
    async def execute(self, context: HookContext) -> Dict[str, Any]:
        """Execute the hook logic"""
        pass

    @abstractmethod
    def get_metadata(self) -> Dict[str, str]:
        """Return hook name, version, author, description"""
        pass

    def validate(self) -> bool:
        """Pre-execution validation - override if needed"""
        return True

    def rollback(self, context: HookContext) -> None:
        """Optional rollback if hook fails - override if needed"""
        pass


class BasePlugin(ABC):
    """Base class for higher-level plugins"""

    @abstractmethod
    def initialize(self) -> bool:
        """Initialize the plugin"""
        pass

    @abstractmethod
    def shutdown(self):
        """Clean up plugin resources"""
        pass

    @abstractmethod
    def get_info(self) -> Dict[str, Any]:
        """Return plugin information"""
        pass
