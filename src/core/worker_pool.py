# ----------------------------------------------------------------------
# SQL Schema Studio 0.9 - Worker Pool (GPLv3)
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

# Spawn context prevents GTK re-import in child processes on Linux.
# Without this, fork() causes each worker to try to start a GTK main loop,
# which crashes silently and leaves only 1 core active.
_SPAWN_CTX = multiprocessing.get_context('spawn')


def _compute_path_worker(
    fk_data: dict,
    tables: list,
    header_height: float,
    row_height: float,
) -> list:
    """Compute an obstacle-avoiding path for a single FK relationship.

    Module-level function so ProcessPoolExecutor can pickle it.
    All inputs are plain dicts/lists — no GTK or Cairo objects.

    Args:
        fk_data: FK geometry — keys: from_table, to_table, from_col_index,
                 to_col_index, waypoints (list of (x, y) tuples), name.
        tables:  List of table geometry dicts — keys: name, x, y, w, h.
        header_height: SCHEMA_TABLE_HEADER_HEIGHT constant from config.
        row_height:    SCHEMA_TABLE_ROW_HEIGHT constant from config.

    Returns:
        List of (x, y) float tuples representing the routed path.
        Returns a straight two-point path on any error so the caller always
        gets a renderable result and never sees an empty path crash.
    """
    import math
    import sys
    import traceback

    table_map = {t["name"]: t for t in tables}
    src = table_map.get(fk_data["from_table"])
    tgt = table_map.get(fk_data["to_table"])

    def _straight(s, t):
        """Straight-line fallback between table midpoints."""
        return [
            (s["x"] + s["w"], s["y"] + s["h"] / 2),
            (t["x"],          t["y"] + t["h"] / 2),
        ]

    if not src or not tgt:
        return []

    try:
        # Source connection point — right edge at FK column row
        from_idx = fk_data.get("from_col_index")
        if from_idx is not None:
            y1 = src["y"] + header_height + from_idx * row_height + row_height / 2
        else:
            y1 = src["y"] + src["h"] / 2
        x1 = src["x"] + src["w"]

        # Target connection point — left edge at referenced column row
        to_idx = fk_data.get("to_col_index")
        if to_idx is not None:
            y2 = tgt["y"] + header_height + to_idx * row_height + row_height / 2
        else:
            y2 = tgt["y"] + tgt["h"] / 2
        x2 = tgt["x"]

        # Build initial path: start + user waypoints + end
        points = [(x1, y1)]
        for wx, wy in fk_data.get("waypoints", []):
            points.append((wx, wy))
        points.append((x2, y2))

        # Obstacles — all tables except the FK endpoints
        obstacles = [
            t for t in tables
            if t["name"] not in (fk_data["from_table"], fk_data["to_table"])
        ]

        def _intersects_rect(lx1, ly1, lx2, ly2, rx, ry, rw, rh, margin=10):
            """Cohen-Sutherland line-rectangle intersection test.
            
            Margin 10 matches the value used in _line_intersects_table
            in schema_designer.py for consistent collision detection.
            """
            rx -= margin; ry -= margin
            rw += margin * 2; rh += margin * 2
            if lx1 > rx + rw and lx2 > rx + rw: return False
            if lx1 < rx and lx2 < rx: return False
            if ly1 > ry + rh and ly2 > ry + rh: return False
            if ly1 < ry and ly2 < ry: return False
            dx = lx2 - lx1; dy = ly2 - ly1
            if dx == 0 and dy == 0: return False
            for t in ([((rx - lx1) / dx), ((rx + rw - lx1) / dx)] if dx else []) + \
                     ([((ry - ly1) / dy), ((ry + rh - ly1) / dy)] if dy else []):
                if 0 <= t <= 1:
                    px = lx1 + t * dx; py = ly1 + t * dy
                    if rx <= px <= rx + rw and ry <= py <= ry + rh:
                        return True
            return False

        def _detour(px1, py1, px2, py2, obs, margin=20):
            """Pick the table corner that minimises total detour length."""
            ox, oy, ow, oh = obs["x"], obs["y"], obs["w"], obs["h"]
            corners = [
                (ox - margin,      oy - margin),
                (ox + ow + margin, oy - margin),
                (ox + ow + margin, oy + oh + margin),
                (ox - margin,      oy + oh + margin),
            ]
            return min(corners, key=lambda c: (
                math.hypot(c[0] - px1, c[1] - py1) +
                math.hypot(c[0] - px2, c[1] - py2)
            ))

        # Iterative collision resolution — max 30 passes
        for _ in range(30):
            collision_found = False
            new_points = [points[0]]
            for i in range(len(points) - 1):
                sx1, sy1 = points[i]
                sx2, sy2 = points[i + 1]
                hit = next(
                    (o for o in obstacles
                     if _intersects_rect(sx1, sy1, sx2, sy2,
                                         o["x"], o["y"], o["w"], o["h"])),
                    None,
                )
                if hit:
                    new_points.append(_detour(sx1, sy1, sx2, sy2, hit))
                    collision_found = True
                new_points.append((sx2, sy2))

            # Remove consecutive near-duplicates
            deduped = [new_points[0]]
            for p in new_points[1:]:
                last = deduped[-1]
                if abs(p[0] - last[0]) > 2 or abs(p[1] - last[1]) > 2:
                    deduped.append(p)
            points = deduped
            if not collision_found:
                break

        return points

    except Exception as e:
        # Print full traceback to stderr so it's visible in terminal output
        print(
            f"Worker error for FK '{fk_data.get('name', 'unknown')}': {e}",
            file=sys.stderr,
        )
        traceback.print_exc(file=sys.stderr)
        return _straight(src, tgt)


class WorkerPool:
    """Process pool for CPU-heavy tasks. Bypasses the GIL."""

    def __init__(self, max_workers: int | None = None):
        self._max_workers = max_workers or CPU_COUNT
        self._pool: ProcessPoolExecutor | None = None
        logger.info(f"Worker pool ready: {self._max_workers} workers (spawn context)")

    @property
    def pool(self) -> ProcessPoolExecutor:
        """Lazy initialization of the process pool with spawn context."""
        if self._pool is None:
            self._pool = ProcessPoolExecutor(
                max_workers=self._max_workers,
                mp_context=_SPAWN_CTX  # Critical: prevents GTK re-import in workers
            )
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
