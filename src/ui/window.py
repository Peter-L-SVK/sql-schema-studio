# ----------------------------------------------------------------------
# SQL Schema Studio 0.8 - Main Application Window (GPLv3)
# Copyright (C) 2026 Peter Leukanič
# License: GNU GPL v3+ <https://www.gnu.org/licenses/gpl-3.0.txt>
# This is free software with NO WARRANTY.
# Feel free to distribute and modify.
# ----------------------------------------------------------------------

"""Main application window - layout only"""

from __future__ import annotations

from src.utils.logging import get_logger

logger = get_logger(__name__)

import os
import time
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("GtkSource", "5")
from gi.repository import GLib, Gtk

from src.config import DEFAULT_WINDOW_WIDTH, DEFAULT_WINDOW_HEIGHT, REFRESH_TRIGGER_COMMANDS
from src.core.query_history import QueryHistory
from src.ui.menubar import build_menubar
from src.ui.toolbar import Toolbar
from src.ui.editor import SQLEditor
from src.ui.results import ResultsPanel
from src.ui.browser import DatabaseBrowser
from src.ui.statusbar import StatusBar
from src.utils.gtk_helpers import run_async
from src.ui.dialogs.connection import ConnectionDialog
from src.ui.schema_designer import SchemaDesigner


class MainWindow(Gtk.ApplicationWindow):
    """SQL Schema Studio main window"""

    def __init__(self, application, db_connector, **kwargs):
        super().__init__(application=application, **kwargs)

        self.db_connector = db_connector
        self.set_title("SQL Schema Studio")
        self.set_default_size(DEFAULT_WINDOW_WIDTH, DEFAULT_WINDOW_HEIGHT)

        self.connect("close-request", self._on_close_request)

        self.menubar = build_menubar()
        self.toolbar = Toolbar(self)
        self.browser = DatabaseBrowser(self)
        self.editor = SQLEditor(self)
        self.results = ResultsPanel()
        self.statusbar = StatusBar()
        self._query_history = QueryHistory()
        self._current_file = None
        self._last_result = None

        self._build_layout()
        self._load_css()
        self._restore_window_state()

    def _build_layout(self):
        """Assemble the window layout"""
        main_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        # Menu bar
        main_vbox.append(self.menubar)

        # Toolbar
        main_vbox.append(self.toolbar)

        # Main content: browser | editor+results
        self._hpaned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        self._hpaned.set_wide_handle(True)
        self._hpaned.set_start_child(self.browser)

        right_vpaned = Gtk.Paned(orientation=Gtk.Orientation.VERTICAL)
        right_vpaned.set_wide_handle(True)
        right_vpaned.set_start_child(self.editor)
        right_vpaned.set_end_child(self.results)

        self._hpaned.set_end_child(right_vpaned)
        main_vbox.append(self._hpaned)

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

    def _on_map(self, widget):
        """Called when window is first shown."""
        self._restore_window_state()
        # Only run once
        self.disconnect_by_func(self._on_map)

    def _restore_window_state(self):
        """Restore window size and pane positions from settings."""
        from src.utils.settings import Settings

        settings = Settings()
        window = settings.get_section("window")

        width = window.get("width", 1200)
        height = window.get("height", 800)
        browser_width = window.get("browser_width", 220)

        def do_restore():
            self.set_default_size(width, height)
            if hasattr(self, "_hpaned"):
                self._hpaned.set_position(browser_width)
            return False

        GLib.idle_add(do_restore)

    def _save_window_state(self):
        """Save window size and pane positions to settings."""
        from src.utils.settings import Settings

        settings = Settings()

        width = self.get_allocated_width()
        height = self.get_allocated_height()
        if width > 0 and height > 0:
            settings.set("window", "width", width)
            settings.set("window", "height", height)

        if hasattr(self, "_hpaned"):
            browser_width = self._hpaned.get_position()
            if browser_width > 50:
                settings.set("window", "browser_width", browser_width)

        settings.save()

    # --- Action handlers ---
    def _on_close_request(self, window):
        """Handle window close — disconnect cleanly first"""
        self._save_window_state()

        if self.db_connector.is_connected:
            try:
                self.db_connector.disconnect()
                logger.info("Disconnected on window close")
            except Exception as e:
                logger.error(f"Disconnect on close error: {e}")
        return False

    def _on_connect_clicked(self):
        """Open connection dialog"""
        logger.info("Opening connection dialog")
        dialog = ConnectionDialog(
            self, db_connector=self.db_connector, on_connected=self._on_connected
        )
        dialog.present()

    def _on_connected(self):
        """Called when connection succeeds"""
        logger.info(f"Connected to {self.db_connector.active_profile_name}")
        if self.db_connector.is_connected:
            self.toolbar.set_status(True, self.db_connector.active_profile_name)
            self.statusbar.set_connection(f"Connected: {self.db_connector.active_profile_name}")
            self.browser.refresh()

    def _on_disconnect_clicked(self):
        """Close database connection"""
        logger.info("Disconnecting from database")
        try:
            self.db_connector.disconnect()
        except Exception as e:
            logger.error(f"Disconnect error: {e}")

        self.toolbar.set_status(False)
        self.statusbar.set_connection("No database connected")
        self.browser.clear()

    def _on_run_clicked(self):
        query = self.editor.get_selected_text()
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
                logger.error(f"Query execution failed: {e}")
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
                self._last_result = (columns, rows)  # Ulož pre export
                self.results.show_query_result(columns, rows, elapsed)
                self.statusbar.set_query_stats(len(rows), elapsed)
                self._query_history.add(
                    query=query, execution_time=elapsed, row_count=len(rows), success=True
                )

            self._refresh_browser_if_ddl(q)

        run_async(run, display)

    def _refresh_browser_if_ddl(self, query_upper):
        """Refresh browser if query is a DDL/DML statement."""
        if any(query_upper.startswith(c) for c in REFRESH_TRIGGER_COMMANDS):
            logger.info(f"Refreshing browser after: {query_upper[:60]}")
            self.browser.refresh()

    def _on_stop_clicked(self):
        logger.info("Query cancelled by user")
        self.statusbar.set_message("Query cancelled")

    def _on_designer_clicked(self):
        """Open schema designer in the main content area."""
        logger.info("Opening schema designer")
        # For now, show in results panel — later make it a tab
        self._designer = SchemaDesigner(self)
        # Replace results panel temporarily, or make a dialog
        dialog = Gtk.Window(transient_for=self, modal=False, title="Schema Designer")
        dialog.set_default_size(800, 600)
        dialog.set_child(self._designer)
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

    def _on_file_open(self):
        """Open a .sql file into the editor."""
        dialog = Gtk.FileDialog()
        dialog.set_title("Open SQL File")

        filter_sql = Gtk.FileFilter()
        filter_sql.set_name("SQL Files (*.sql, *.psql)")
        filter_sql.add_pattern("*.sql")
        filter_sql.add_pattern("*.psql")

        filter_all = Gtk.FileFilter()
        filter_all.set_name("All Files")
        filter_all.add_pattern("*")

        from gi.repository import Gio

        filter_store = Gio.ListStore.new(Gtk.FileFilter)
        filter_store.append(filter_sql)
        filter_store.append(filter_all)

        dialog.set_filters(filter_store)
        dialog.open(self, None, self._on_file_open_response)

    def _on_file_open_response(self, dialog, result):
        """Handle file open response."""
        try:
            file = dialog.open_finish(result)
            if file:
                path = file.get_path()
                with open(path, "r") as f:
                    content = f.read()
                self.editor.set_text(content)
                self._current_file = path
                self.statusbar.set_connection(f"Opened: {os.path.basename(path)}")
                logger.info(f"Opened file: {path}")
        except Exception as e:
            logger.error(f"Failed to open file: {e}")

    def _on_file_save(self):
        """Save current editor content to file."""
        if hasattr(self, "_current_file") and self._current_file:
            self._save_to_file(self._current_file)
        else:
            self._on_file_save_as()

    def _on_file_save_as(self):
        """Save editor content to a new file."""
        dialog = Gtk.FileDialog()
        dialog.set_title("Save SQL File")
        dialog.set_initial_name("query.sql")

        filter_sql = Gtk.FileFilter()
        filter_sql.set_name("SQL Files (*.sql)")
        filter_sql.add_pattern("*.sql")

        from gi.repository import Gio

        filter_store = Gio.ListStore.new(Gtk.FileFilter)
        filter_store.append(filter_sql)
        dialog.set_filters(filter_store)

        dialog.save(self, None, self._on_file_save_response)

    def _on_file_save_response(self, dialog, result):
        """Handle file save response."""
        try:
            file = dialog.save_finish(result)
            if file:
                path = file.get_path()
                self._save_to_file(path)
                self._current_file = path
        except Exception as e:
            logger.error(f"Failed to save file: {e}")

    def _save_to_file(self, path):
        """Write editor content to file."""
        content = self.editor.get_text()
        with open(path, "w") as f:
            f.write(content)
        self.statusbar.set_connection(f"Saved: {os.path.basename(path)}")
        logger.info(f"Saved file: {path}")

    def _on_export_csv(self):
        """Export last query results to CSV."""
        self._export_results("csv")

    def _on_export_json(self):
        """Export last query results to JSON."""
        self._export_results("json")

    def _export_results(self, format_type):
        """Export results to file."""
        if not self._last_result:
            logger.warning("No results to export")
            return

        columns, rows = self._last_result

        dialog = Gtk.FileDialog()
        dialog.set_title(f"Export as {format_type.upper()}")
        dialog.set_initial_name(f"query_results.{format_type}")

        filter_f = Gtk.FileFilter()
        if format_type == "csv":
            filter_f.set_name("CSV Files (*.csv)")
            filter_f.add_pattern("*.csv")
        else:
            filter_f.set_name("JSON Files (*.json)")
            filter_f.add_pattern("*.json")

        from gi.repository import Gio

        filter_store = Gio.ListStore.new(Gtk.FileFilter)
        filter_store.append(filter_f)
        dialog.set_filters(filter_store)

        dialog.save(
            self, None, lambda d, r: self._on_export_response(d, r, columns, rows, format_type)
        )

    def _on_export_response(self, dialog, result, columns, rows, format_type):
        """Handle export file save."""
        try:
            file = dialog.save_finish(result)
            if file:
                path = file.get_path()

                if format_type == "csv":
                    import csv

                    with open(path, "w", newline="") as f:
                        writer = csv.writer(f)
                        writer.writerow(columns)
                        writer.writerows(rows)
                else:
                    import json

                    data = [dict(zip(columns, row)) for row in rows]
                    with open(path, "w") as f:
                        json.dump(data, f, indent=2, default=str)

                self.statusbar.set_connection(f"Exported: {os.path.basename(path)}")
                logger.info(f"Exported {len(rows)} rows to {path}")
        except Exception as e:
            logger.error(f"Export failed: {e}")

    def _on_import_csv(self):
        """Import CSV file into a table."""
        self._import_file("csv")

    def _on_import_json(self):
        """Import JSON file into a table."""
        self._import_file("json")

    def _import_file(self, format_type):
        """Import data from file into a table."""
        if not self.db_connector.is_connected:
            logger.warning("Not connected to database")
            return

        dialog = Gtk.FileDialog()
        dialog.set_title(f"Import {format_type.upper()} File")

        filter_f = Gtk.FileFilter()
        if format_type == "csv":
            filter_f.set_name("CSV Files (*.csv)")
            filter_f.add_pattern("*.csv")
        else:
            filter_f.set_name("JSON Files (*.json)")
            filter_f.add_pattern("*.json")

        from gi.repository import Gio

        filter_store = Gio.ListStore.new(Gtk.FileFilter)
        filter_store.append(filter_f)
        dialog.set_filters(filter_store)

        dialog.open(self, None, lambda d, r: self._on_import_response(d, r, format_type))

    def _on_import_response(self, dialog, result, format_type):
        """Handle import file selection and start the import."""
        try:
            file = dialog.open_finish(result)
            if not file:
                return

            path = file.get_path()

            if format_type == "csv":
                import csv

                with open(path, "r", newline="") as f:
                    reader = csv.reader(f)
                    headers = next(reader, None)
                    if not headers:
                        return
                    columns = [h.strip() for h in headers]
                    rows = [row for row in reader]
            else:
                import json

                with open(path, "r") as f:
                    data = json.load(f)
                if not data:
                    return
                columns = list(data[0].keys())
                rows = [[row.get(c, "") for c in columns] for row in data]

            if not columns or not rows:
                return

            # Show preview dialog
            self._show_import_preview(path, columns, rows, format_type)

        except Exception as e:
            logger.error(f"Import failed: {e}")

    def _show_import_preview(self, path, columns, rows, format_type):
        """Show preview dialog before importing."""
        from src.utils.gtk_helpers import set_margin

        table_name = os.path.splitext(os.path.basename(path))[0]

        dialog = Gtk.Window(
            transient_for=self,
            modal=True,
            title="Import Preview",
            default_width=500,
            default_height=400,
        )

        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        set_margin(main_box, 12)

        # Info
        info = Gtk.Label(
            label=f"File: {os.path.basename(path)}\n"
            f"Columns: {len(columns)}\n"
            f"Rows: {len(rows)}\n"
            f"Format: {format_type.upper()}"
        )
        info.set_halign(Gtk.Align.START)
        main_box.append(info)

        # Table name
        name_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        name_box.append(Gtk.Label(label="Table name:"))
        name_entry = Gtk.Entry()
        name_entry.set_text(table_name)
        name_entry.set_hexpand(True)
        name_box.append(name_entry)
        main_box.append(name_box)

        # Preview columns
        preview_label = Gtk.Label(label="Columns detected:", halign=Gtk.Align.START)
        main_box.append(preview_label)

        preview_text = Gtk.TextView()
        preview_text.set_editable(False)
        preview_text.set_monospace(True)
        buffer = preview_text.get_buffer()
        buffer.set_text(", ".join(columns[:10]) + ("..." if len(columns) > 10 else ""))

        scroll = Gtk.ScrolledWindow()
        scroll.set_min_content_height(60)
        scroll.set_child(preview_text)
        main_box.append(scroll)

        # Buttons
        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        button_box.set_halign(Gtk.Align.END)

        btn_cancel = Gtk.Button(label="Cancel")
        btn_cancel.connect("clicked", lambda b: dialog.close())
        button_box.append(btn_cancel)

        btn_import = Gtk.Button(label="Import")
        btn_import.add_css_class("suggested-action")

        def do_import(b):
            name = name_entry.get_text().strip()
            if not name:
                return
            dialog.close()
            self._execute_import(name, columns, rows)

        btn_import.connect("clicked", do_import)
        button_box.append(btn_import)

        main_box.append(button_box)
        dialog.set_child(main_box)
        dialog.present()

    def _execute_import(self, table_name, columns, rows):
        """Create table and insert data."""
        try:
            # Create table
            col_defs = [f'"{c}" TEXT' for c in columns]
            create_sql = f'CREATE TABLE IF NOT EXISTS "{table_name}" ({", ".join(col_defs)})'
            self.db_connector.execute_sync(create_sql)

            # Insert data in batches
            placeholders = ", ".join(["%s"] * len(columns))
            insert_sql = f'INSERT INTO "{table_name}" ({", ".join(f"\"{c}\"" for c in columns)}) VALUES ({placeholders})'

            batch_size = 100
            for i in range(0, len(rows), batch_size):
                batch = rows[i: i + batch_size]  # fmt: skip
                for row in batch:
                    self.db_connector.execute_sync(insert_sql, tuple(row))

            self.browser.refresh()
            self.statusbar.set_connection(f"Imported {len(rows)} rows into {table_name}")
            logger.info(f"Imported {len(rows)} rows into {table_name}")

        except Exception as e:
            logger.error(f"Import execution failed: {e}")
