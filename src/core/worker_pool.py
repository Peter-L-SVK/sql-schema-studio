# ----------------------------------------------------------------------
# SQL Schema Studio 0.5 - Worker Pool (GPLv3)
# Copyright (C) 2026 Peter Leukanič
# License: GNU GPL v3+ <https://www.gnu.org/licenses/gpl-3.0.txt>
# This is free software with NO WARRANTY.
# Feel free to distribute and modify.
# ----------------------------------------------------------------------

"""Multi-CPU worker pool using ProcessPoolExecutor for CPU-bound tasks."""

import multiprocessing
from concurrent.futures import ProcessPoolExecutor, Future
from typing import Callable, Any

from src.utils.logging import get_logger

logger = get_logger(__name__)

# Use N-1 cores so the UI stays responsive
CPU_COUNT = max(1, multiprocessing.cpu_count() - 1)


class WorkerPool:
    """Process pool for CPU-heavy tasks. Bypasses the GIL."""

    def __init__(self, max_workers: int | None = None):
        self._max_workers = max_workers or CPU_COUNT
        self._pool: ProcessPoolExecutor | None = None
        logger.info(f"Worker pool ready: {self._max_workers} workers")

    @property
    def pool(self) -> ProcessPoolExecutor:
        """Lazy initialization of the process pool."""
        if self._pool is None:
            self._pool = ProcessPoolExecutor(max_workers=self._max_workers)
        return self._pool

    def submit(self, func: Callable, *args, **kwargs) -> Future:
        """Submit a task to the process pool.

        Args:
            func: Function to execute (must be picklable)
            *args, **kwargs: Arguments for the function

        Returns:
            Future object with the result
        """
        return self.pool.submit(func, *args, **kwargs)

    def run_and_wait(self, func: Callable, *args, **kwargs) -> Any:
        """Submit a task and wait for the result.

        Args:
            func: Function to execute
            *args, **kwargs: Arguments

        Returns:
            Result of the function call
        """
        future = self.submit(func, *args, **kwargs)
        return future.result()

    def shutdown(self):
        """Shut down the process pool gracefully."""
        if self._pool:
            self._pool.shutdown(wait=False)
            self._pool = None
            logger.info("Worker pool shut down")


# Global singleton
_pool: WorkerPool | None = None


def get_pool() -> WorkerPool:
    """Get or create the global worker pool."""
    global _pool
    if _pool is None:
        _pool = WorkerPool()
    return _pool
