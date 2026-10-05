# ----------------------------------------------------------------------
# SQL Schema Studio 0.9 - Schema Cache (GPLv3)
# Copyright (C) 2026 Peter Leukanič
# License: GNU GPL v3+ <https://www.gnu.org/licenses/gpl-3.0.txt>
# This is free software with NO WARRANTY.
# Feel free to distribute and modify.
# ----------------------------------------------------------------------

"""In-memory cache for table structures with TTL and DDL invalidation.

Table columns rarely change between queries, but the browser re-fetches
them on every double-click. This cache avoids that round-trip.

Two invalidation mechanisms:
  1. Explicit — after a DDL statement (ALTER/DROP/CREATE OR REPLACE),
     the caller calls invalidate() or invalidate_all().
  2. TTL — every entry expires after `ttl_seconds` so a missed
     invalidation self-heals.

Both are combined: get() returns None if either TTL expired or the
entry was explicitly invalidated.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class _CacheEntry:
    data: Any
    timestamp: float


class SchemaCache:
    """Thread-safe cache for table structures.

    Keys are (schema, table) tuples. Values are arbitrary — typically
    the column list returned by information_schema.columns.
    """

    def __init__(self, ttl_seconds: int = 300):
        self._cache: dict[tuple[str, str], _CacheEntry] = {}
        self._ttl = ttl_seconds
        self._lock = threading.Lock()

    # ==================================================================
    # Read / write
    # ==================================================================

    def get(self, schema: str, table: str) -> Optional[Any]:
        """Return cached data or None if missing / expired."""
        key = (schema, table)
        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                return None
            if time.time() - entry.timestamp > self._ttl:
                del self._cache[key]
                return None
            return entry.data

    def put(self, schema: str, table: str, data: Any) -> None:
        """Store data for a table."""
        with self._lock:
            self._cache[(schema, table)] = _CacheEntry(
                data=data, timestamp=time.time()
            )

    # ==================================================================
    # Invalidation
    # ==================================================================

    def invalidate(self, schema: str, table: str) -> None:
        """Drop one table's entry."""
        with self._lock:
            self._cache.pop((schema, table), None)

    def invalidate_schema(self, schema: str) -> None:
        """Drop every entry under a schema."""
        with self._lock:
            for key in [k for k in self._cache if k[0] == schema]:
                del self._cache[key]

    def invalidate_all(self) -> None:
        """Drop everything."""
        with self._lock:
            self._cache.clear()

    # ==================================================================
    # Introspection (for status bar / debugging)
    # ==================================================================

    def size(self) -> int:
        """Number of live entries (after pruning expired ones)."""
        now = time.time()
        with self._lock:
            for key in [k for k, e in self._cache.items() if now - e.timestamp > self._ttl]:
                del self._cache[key]
            return len(self._cache)

    def clear(self) -> None:
        """Alias for invalidate_all()."""
        self.invalidate_all()
