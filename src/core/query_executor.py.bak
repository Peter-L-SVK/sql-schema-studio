# ----------------------------------------------------------------------
# SQL Schema Studio 0.9 - Query Executor (GPLv3)
# Copyright (C) 2026 Peter Leukanič
# License: GNU GPL v3+ <https://www.gnu.org/licenses/gpl-3.0.txt>
# This is free software with NO WARRANTY.
# Feel free to distribute and modify.
# ----------------------------------------------------------------------

"""Safe query execution with timeout and cancellation."""

import asyncio
import threading
from typing import Optional, List, Any
from dataclasses import dataclass
from datetime import datetime

from src.config import DEFAULT_QUERY_TIMEOUT
from src.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class QueryResult:
    """Result of a query execution."""

    success: bool
    columns: List[str]
    rows: List[List[Any]]
    row_count: int
    execution_time: float
    error: Optional[str] = None


class QueryExecutor:
    """Safe query execution manager."""

    def __init__(self, db_connector, timeout: int = DEFAULT_QUERY_TIMEOUT):
        self.db_connector = db_connector
        self.default_timeout = timeout
        self._running_queries: dict[int, asyncio.Task] = {}
        self._query_counter = 0
        self._counter_lock = threading.Lock()

    async def execute(self, query: str, timeout: int | None = None) -> QueryResult:
        """Execute query with timeout and cancellation support."""
        if timeout is None:
            timeout = self.default_timeout

        with self._counter_lock:
            query_id = self._query_counter
            self._query_counter += 1

        start_time = datetime.now()
        logger.debug(f"Query {query_id}: {query[:100]}...")
        task = None

        try:
            task = asyncio.create_task(self.db_connector.execute(query))
            self._running_queries[query_id] = task

            results = await asyncio.wait_for(task, timeout=timeout)
            execution_time = (datetime.now() - start_time).total_seconds()
            logger.debug(f"Query {query_id} completed in {execution_time:.3f}s")

            if results:
                columns = list(results[0].keys())
                rows = [list(r.values()) for r in results]
            else:
                columns = []
                rows = []

            return QueryResult(
                success=True,
                columns=columns,
                rows=rows,
                row_count=len(rows),
                execution_time=execution_time,
            )

        except asyncio.TimeoutError:
            logger.warning(f"Query {query_id} timed out after {timeout}s")
            if task and not task.done():
                task.cancel()
            return QueryResult(
                success=False,
                columns=[],
                rows=[],
                row_count=0,
                execution_time=timeout,
                error=f"Query timed out after {timeout}s",
            )
        except Exception as e:
            logger.error(f"Query {query_id} failed: {e}")
            return QueryResult(
                success=False,
                columns=[],
                rows=[],
                row_count=0,
                execution_time=(datetime.now() - start_time).total_seconds(),
                error=str(e),
            )
        finally:
            self._running_queries.pop(query_id, None)

    def cancel_query(self, query_id: int):
        """Cancel a running query."""
        logger.info(f"Cancelling query {query_id}")
        if query_id in self._running_queries:
            self._running_queries[query_id].cancel()
