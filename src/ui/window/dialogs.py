# ----------------------------------------------------------------------
# SQL Schema Studio 0.9 - Window Dialogs (GPLv3)
# Copyright (C) 2026 Peter Leukanič
# License: GNU GPL v3+ <https://www.gnu.org/licenses/gpl-3.0.txt>
# This is free software with NO WARRANTY.
# Feel free to distribute and modify.
# ----------------------------------------------------------------------

"""File, export, and import dialog handlers for MainWindow."""

import os
from gi.repository import Gtk
from typing import Any

from src.utils.gtk_helpers import set_margin
from src.utils.logging import get_logger

logger = get_logger(__name__)


class WindowDialogsMixin:
    """Mixin with file/export/import dialog handlers."""

    # Type annotations for attributes from MainWindow
    editor: Any
    statusbar: Any
    browser: Any
    db_connector: Any
    _last_result: tuple | None

    def _on_file_open(self):
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
        try:
            file = dialog.open_finish(result)
            if file:
                path = file.get_path()
                with open(path, "r") as f:
                    content = f.read()
                self.editor.set_text(content)
                tab = self.editor.get_active_tab()
                if tab:
                    tab.file_path = path
                    tab_name = os.path.basename(path)
                    self.editor.rename_tab(tab, tab_name)
                self.statusbar.set_connection(f"Opened: {os.path.basename(path)}")
                logger.info(f"Opened file: {path}")
        except Exception as e:
            logger.error(f"Failed to open file: {e}")

    def _on_file_save(self):
        tab = self.editor.get_active_tab()
        if tab and tab.file_path:
            self._save_to_file(tab.file_path)
        else:
            self._on_file_save_as()

    def _on_file_save_as(self):
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
        try:
            file = dialog.save_finish(result)
            if file:
                path = file.get_path()
                self._save_to_file(path)
        except Exception as e:
            logger.error(f"Failed to save file: {e}")

    def _save_to_file(self, path):
        content = self.editor.get_text()
        with open(path, "w") as f:
            f.write(content)
        tab = self.editor.get_active_tab()
        if tab:
            tab._view.get_buffer().set_modified(False)
            tab.file_path = path
        self.statusbar.set_connection(f"Saved: {os.path.basename(path)}")

    def _on_export_csv(self):
        self._export_results("csv")

    def _on_export_json(self):
        self._export_results("json")

    def _export_results(self, format_type):
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
        self._import_file("csv")

    def _on_import_json(self):
        self._import_file("json")

    def _import_file(self, format_type):
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
            self._show_import_preview(path, columns, rows, format_type)
        except Exception as e:
            logger.error(f"Import failed: {e}")

    def _show_import_preview(self, path, columns, rows, format_type):
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
        info = Gtk.Label(
            label=f"File: {os.path.basename(path)}\nColumns: {len(columns)}\nRows: {len(rows)}\nFormat: {format_type.upper()}"
        )
        info.set_halign(Gtk.Align.START)
        main_box.append(info)
        name_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        name_box.append(Gtk.Label(label="Table name:"))
        name_entry = Gtk.Entry()
        name_entry.set_text(table_name)
        name_entry.set_hexpand(True)
        name_box.append(name_entry)
        main_box.append(name_box)
        main_box.append(Gtk.Label(label="Columns detected:", halign=Gtk.Align.START))
        preview_text = Gtk.TextView()
        preview_text.set_editable(False)
        preview_text.set_monospace(True)
        buffer = preview_text.get_buffer()
        buffer.set_text(", ".join(columns[:10]) + ("..." if len(columns) > 10 else ""))
        scroll = Gtk.ScrolledWindow()
        scroll.set_min_content_height(60)
        scroll.set_child(preview_text)
        main_box.append(scroll)
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
        try:
            col_defs = [f'"{c}" TEXT' for c in columns]
            create_sql = f'CREATE TABLE IF NOT EXISTS "{table_name}" ({", ".join(col_defs)})'
            self.db_connector.execute_sync(create_sql)
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
