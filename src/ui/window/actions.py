# ----------------------------------------------------------------------
# SQL Schema Studio 0.9 - Window Actions (GPLv3)
# Copyright (C) 2026 Peter Leukanič
# License: GNU GPL v3+ <https://www.gnu.org/licenses/gpl-3.0.txt>
# This is free software with NO WARRANTY.
# Feel free to distribute and modify.
# ----------------------------------------------------------------------

"""Action handlers for the main window — connect, run, design, hooks, history."""

import time
from gi.repository import Gtk
from typing import Any

from src.config import REFRESH_TRIGGER_COMMANDS
from src.utils.gtk_helpers import run_async
from src.utils.logging import get_logger

logger = get_logger(__name__)


class WindowActionsMixin:
    """Mixin with all action handlers for MainWindow."""

    # Type annotations for attributes from MainWindow
    db_connector: Any
    toolbar: Any
    statusbar: Any
    browser: Any
    editor: Any
    results: Any
    _query_history: Any
    _last_result: tuple | None

    def _on_connect_clicked(self):
        logger.info("Opening connection dialog")
        from src.ui.dialogs.connection import ConnectionDialog

        dialog = ConnectionDialog(
            self, db_connector=self.db_connector, on_connected=self._on_connected
        )
        dialog.present()

    def _on_connected(self):
        logger.info(f"Connected to {self.db_connector.active_profile_name}")
        if self.db_connector.is_connected:
            self.toolbar.set_status(True, self.db_connector.active_profile_name)
            self.statusbar.set_connection(f"Connected: {self.db_connector.active_profile_name}")
            self.browser.refresh()

    def _on_disconnect_clicked(self):
        logger.info("Disconnecting from database")
        try:
            self.db_connector.disconnect()
        except Exception as e:
            logger.error(f"Disconnect error: {e}")
        self.toolbar.set_status(False)
        self.statusbar.set_connection("No database connected")
        self.browser.clear()

    def _on_run_clicked(self):
        query = self.editor.get_text()
        if not query.strip():
            return
        logger.info(f"Executing query ({len(query)} chars)")
        self.toolbar.set_run_sensitive(False)
        self.statusbar.set_message("Running...")
        start_time = time.time()

        def run():
            try:
                result = self.db_connector.execute_sync(query)
                elapsed = time.time() - start_time
                return result, elapsed, None
            except Exception as e:
                elapsed = time.time() - start_time
                return [], elapsed, str(e)

        def display(data):
            result, elapsed, error = data
            self.toolbar.set_run_sensitive(True)
            q = query.strip().upper()
            if error:
                self.results.show_error(error, elapsed)
                self.statusbar.set_message(f"Error ({elapsed:.3f}s)")
                self._query_history.add(
                    query=query, execution_time=elapsed, row_count=0, success=False
                )
                self._refresh_browser_if_ddl(q)
                return
            if not result:
                self.results.show_text(f"Query executed.\nTime: {elapsed:.3f}s")
                self.statusbar.set_query_stats(0, elapsed)
                self._query_history.add(
                    query=query, execution_time=elapsed, row_count=0, success=True
                )
            else:
                columns = list(result[0].keys())
                rows = [list(r.values()) for r in result]
                self._last_result = (columns, rows)
                self.results.show_query_result(columns, rows, elapsed)
                self.statusbar.set_query_stats(len(rows), elapsed)
                self._query_history.add(
                    query=query, execution_time=elapsed, row_count=len(rows), success=True
                )
            self._refresh_browser_if_ddl(q)

        run_async(run, display)

    def _refresh_browser_if_ddl(self, query_upper):
        if any(query_upper.startswith(c) for c in REFRESH_TRIGGER_COMMANDS):
            logger.info(f"Refreshing browser after: {query_upper[:60]}")
            self.browser.refresh()

    def _on_stop_clicked(self):
        logger.info("Query cancelled by user")
        self.statusbar.set_message("Query cancelled")

    def _on_designer_clicked(self):
        logger.info("Opening schema designer")
        from src.ui.schema_designer import SchemaDesigner

        self._designer = SchemaDesigner(self)
        dialog = Gtk.Window(transient_for=self, modal=False, title="Schema Designer")
        dialog.set_default_size(800, 600)
        dialog.set_child(self._designer)
        dialog.connect("close-request", lambda d: self._designer._on_close())
        dialog.present()

    def _on_hooks_clicked(self):
        from src.ui.dialogs.hook_manager import HookManagerDialog

        dialog = HookManagerDialog(self, db_connector=self.db_connector)
        dialog.present()

    def _on_query_history_clicked(self):
        from src.ui.dialogs.query_history_dialog import QueryHistoryDialog

        def on_select(query):
            self.editor.set_text(query)

        dialog = QueryHistoryDialog(self, self._query_history, on_select=on_select)
        dialog.present()
