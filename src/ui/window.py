# ----------------------------------------------------------------------
# SQL Schema Studio - Main Application Window (GPLv3)
# Copyright (C) 2026 Peter Leukanič
# License: GNU GPL v3+ <https://www.gnu.org/licenses/gpl-3.0.txt>
# This is free software with NO WARRANTY.
# Feel free to distribute and modify.
# ----------------------------------------------------------------------

"""Main application window - layout only"""

from __future__ import annotations

import time
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("GtkSource", "5")
from gi.repository import Gtk

from src.ui.menubar import build_menubar
from src.ui.toolbar import Toolbar
from src.ui.editor import SQLEditor
from src.ui.results import ResultsPanel
from src.ui.browser import DatabaseBrowser
from src.ui.statusbar import StatusBar
from src.utils.gtk_helpers import run_async


class MainWindow(Gtk.ApplicationWindow):
    """SQL Schema Studio main window"""

    def __init__(self, application, db_connector, **kwargs):
        super().__init__(application=application, **kwargs)

        self.db_connector = db_connector
        self.set_title("SQL Schema Studio")
        self.set_default_size(1200, 800)

        # Connect close request signal
        self.connect("close-request", self._on_close_request)

        # Create components
        self.menubar = build_menubar()
        self.toolbar = Toolbar(self)
        self.browser = DatabaseBrowser(self)
        self.editor = SQLEditor(self)
        self.results = ResultsPanel()
        self.statusbar = StatusBar()

        self._build_layout()
        self._load_css()

    def _build_layout(self):
        """Assemble the window layout"""
        main_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        # Menu bar
        main_vbox.append(self.menubar)

        # Toolbar
        main_vbox.append(self.toolbar)

        # Main content: browser | editor+results
        hpaned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        hpaned.set_wide_handle(True)

        hpaned.set_start_child(self.browser)

        right_vpaned = Gtk.Paned(orientation=Gtk.Orientation.VERTICAL)
        right_vpaned.set_wide_handle(True)
        right_vpaned.set_start_child(self.editor)
        right_vpaned.set_end_child(self.results)

        hpaned.set_end_child(right_vpaned)
        main_vbox.append(hpaned)

        # Status bar
        main_vbox.append(self.statusbar)

        self.set_child(main_vbox)

    def _load_css(self):
        """Load CSS styling"""
        import os

        css_provider = Gtk.CssProvider()
        css_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "resources",
            "ui",
            "style.css",
        )
        css_provider.load_from_path(css_path)
        Gtk.StyleContext.add_provider_for_display(
            self.get_display(), css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

    # --- Action handlers ---
    def _on_close_request(self, window):
        """Handle window close — disconnect cleanly first"""
        if self.db_connector.is_connected:
            try:
                self.db_connector.disconnect()
                print("Disconnected on window close")
            except Exception as e:
                print(f"Disconnect on close error: {e}")
        return False

    def _on_connect_clicked(self):
        """Open connection dialog"""
        from src.ui.dialogs.connection import ConnectionDialog

        dialog = ConnectionDialog(
            self, db_connector=self.db_connector, on_connected=self._on_connected
        )
        dialog.present()

    def _on_connected(self):
        """Called when connection succeeds"""
        if self.db_connector.is_connected:
            self.toolbar.set_status(True, self.db_connector.active_profile_name)
            self.statusbar.set_connection(f"Connected: {self.db_connector.active_profile_name}")
            self.browser.refresh()

    def _on_disconnect_clicked(self):
        """Close database connection"""
        try:
            self.db_connector.disconnect()
        except Exception as e:
            print(f"Disconnect error: {e}")
        self.toolbar.set_status(False)
        self.statusbar.set_connection("No database connected")
        self.browser.clear()

    def _on_run_clicked(self):
        """Execute SQL query"""
        query = self.editor.get_selected_text()
        if not query.strip():
            return

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

            if error:
                self.results.show_error(error, elapsed)
                self.statusbar.set_message(f"Error ({elapsed:.3f}s)")
                return

            if not result:
                self.results.show_text(f"Query executed.\nTime: {elapsed:.3f}s")
                self.statusbar.set_query_stats(0, elapsed)
            else:
                columns = list(result[0].keys())
                rows = [list(r.values()) for r in result]
                self.results.show_query_result(columns, rows, elapsed)
                self.statusbar.set_query_stats(len(rows), elapsed)

            # Refresh browser for DDL/DML
            q = query.strip().upper()
            if any(
                q.startswith(c)
                for c in ["CREATE", "ALTER", "DROP", "TRUNCATE", "INSERT", "UPDATE", "DELETE"]
            ):
                self.browser.refresh()

        run_async(run, display)

    def _on_stop_clicked(self):
        self.statusbar.set_message("Query cancelled")
