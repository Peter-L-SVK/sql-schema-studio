# ----------------------------------------------------------------------
# SQL Schema Studio 0.9 - Schema Designer Worker Bridge (GPLv3)
# Copyright (C) 2026 Peter Leukanič
# License: GNU GPL v3+ <https://www.gnu.org/licenses/gpl-3.0.txt>
# This is free software with NO WARRANTY.
# Feel free to distribute and modify.
# ----------------------------------------------------------------------

"""Bridge between the schema designer and the multi-core worker pool
for asynchronous path computation."""

import logging

from gi.repository import GLib

from src.config import SCHEMA_TABLE_HEADER_HEIGHT, SCHEMA_TABLE_ROW_HEIGHT

logger = logging.getLogger(__name__)


class WorkerBridgeMixin:
    """Mixin providing async path computation via ProcessPoolExecutor."""

    # Expected from the main class:
    # self._relationships, self._table_index, self._canvas,
    # self._path_serial, self._path_pending, self._path_debounce_id

    # =====================================================================
    # Path invalidation
    # =====================================================================

    def _invalidate_all_paths(self):
        """Clear all cached paths and schedule async recomputation with debounce."""
        for fk in self._relationships:
            fk._cached_path = []
        if self._path_debounce_id:
            GLib.source_remove(self._path_debounce_id)
        self._path_debounce_id = GLib.timeout_add(150, self._schedule_path_computation)

    # =====================================================================
    # Async scheduling
    # =====================================================================

    def _schedule_path_computation(self):
        """Offload path computation for all dirty FKs to the worker pool."""
        self._path_debounce_id = 0

        if self._path_pending:
            return False

        dirty = [fk for fk in self._relationships if not fk._cached_path]
        if not dirty:
            return False

        self._path_pending = True
        self._path_serial += 1
        current_serial = self._path_serial

        tables_data = [
            {
                "name": name,
                "x": t.x,
                "y": t.y,
                "w": t.get_size()[0],
                "h": t.get_size()[1],
            }
            for name, t in self._table_index.items()
        ]

        try:
            from src.core.worker_pool import get_pool, _compute_path_worker

            pool = get_pool()
        except Exception as e:
            logger.warning(f"Worker pool unavailable: {e}")
            self._path_pending = False
            return False

        for fk in dirty:
            fk_data = {
                "from_table": fk.from_table,
                "to_table": fk.to_table,
                "from_col_index": fk.from_col_index,
                "to_col_index": fk.to_col_index,
                "waypoints": list(fk.waypoints),
                "name": fk.name,
            }
            future = pool.submit(
                _compute_path_worker,
                fk_data,
                tables_data,
                SCHEMA_TABLE_HEADER_HEIGHT,
                SCHEMA_TABLE_ROW_HEIGHT,
            )
            future.add_done_callback(
                lambda f, _fk=fk, serial=current_serial: GLib.idle_add(
                    self._on_path_ready, _fk, f, serial
                )
            )

        GLib.timeout_add(2000, self._check_path_completion, current_serial)
        return False

    def _check_path_completion(self, serial):
        """Safety-net timer: unblock and restart pool if paths are done or timed out."""
        if serial != self._path_serial:
            return False
        self._path_pending = False
        self._restart_pool()
        self._canvas.queue_draw()
        return False

    def _on_path_ready(self, fk, future, serial):
        """Write a computed path back to the FK. Always called on the GTK main thread."""
        if serial != self._path_serial:
            return

        src = self._table_index.get(fk.from_table)
        tgt = self._table_index.get(fk.to_table)

        def _straight_line():
            if src and tgt:
                src_w, src_h = src.get_size()
                tgt_w, tgt_h = tgt.get_size()
                fk._cached_path = [
                    (src.x + src_w, src.y + src_h / 2),
                    (tgt.x, tgt.y + tgt_h / 2),
                ]

        try:
            path = future.result(timeout=0.1)
            if path and len(path) >= 2:
                fk._cached_path = path
            else:
                _straight_line()
        except Exception as e:
            logger.error(f"Path computation failed for FK '{fk.name}': {e}")
            _straight_line()

        # Clean up future reference to prevent memory leaks
        try:
            future.cancel()
        except Exception:
            pass

        remaining = sum(1 for f in self._relationships if not f._cached_path)
        if remaining == 0:
            self._path_pending = False
            self._restart_pool()

        self._canvas.queue_draw()

    def _restart_pool(self):
        """Restart worker pool to free memory from completed workers."""
        try:
            from src.core.worker_pool import get_pool

            get_pool().restart()
        except Exception:
            pass

    def _shutdown_pool(self):
        """Shutdown worker pool completely (on designer close)."""
        try:
            from src.core.worker_pool import get_pool

            get_pool().shutdown()
        except Exception:
            pass
