# ----------------------------------------------------------------------
# SQL Schema Studio 0.9 - Menu Actions (GPLv3)
# Copyright (C) 2026 Peter Leukanič
# License: GNU GPL v3+ <https://www.gnu.org/licenses/gpl-3.0.txt>
# This is free software with NO WARRANTY.
# Feel free to distribute and modify.
# ----------------------------------------------------------------------

"""All menu and toolbar action handlers"""

from __future__ import annotations

from src.utils.logging import get_logger

logger = get_logger(__name__)

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("GtkSource", "5")
from gi.repository import Gio, GLib

from src.ui.dialogs.about import show_about


class ActionHandler:
    """Handles all application menu and toolbar actions"""

    def __init__(self, app, window_getter):
        """
        Args:
            app: Gtk.Application instance
            window_getter: callable that returns the current MainWindow (or None)
        """
        self._app = app
        self._get_window = window_getter

    @property
    def _window(self):
        return self._get_window()

    # --- Helpers ---

    def _get_editor_view(self):
        """Get the active editor view, or None."""
        if self._window and hasattr(self._window, "editor"):
            return self._window.editor.get_active_view()
        return None

    def _get_editor_buffer(self):
        """Get the active editor buffer, or None."""
        view = self._get_editor_view()
        return view.get_buffer() if view else None

    # --- Registration ---

    def register_all(self):
        """Register all actions with the application"""
        self._register_file_actions()
        self._register_edit_actions()
        self._register_view_actions()
        self._register_query_actions()
        self._register_tools_actions()
        self._register_help_actions()

    def _add_action(self, name, callback, accels=None):
        action = Gio.SimpleAction.new(name, None)
        action.connect("activate", callback)
        self._app.add_action(action)
        if accels:
            self._app.set_accels_for_action(f"app.{name}", accels)

    # --- File ---

    def _register_file_actions(self):
        self._add_action("new_connection", self._on_new_connection)
        self._add_action("new_tab", self._on_new_tab, ["<Ctrl>T"])
        self._add_action("close_tab", self._on_close_tab, ["<Ctrl>W"])
        self._add_action("open_schema", self._on_open_schema, ["<Ctrl>O"])
        self._add_action("save_schema", self._on_save_schema, ["<Ctrl>S"])
        self._add_action("save_schema_as", self._on_save_schema_as, ["<Ctrl><Shift>S"])
        self._add_action("export_csv", self._on_export_csv)
        self._add_action("export_json", self._on_export_json)
        self._add_action("import_csv", self._on_import_csv)
        self._add_action("import_json", self._on_import_json)
        self._add_action("quit", self._on_quit, ["<Ctrl>Q"])

    def _on_new_connection(self, action, param):
        if self._window:
            self._window._on_connect_clicked()

    def _on_new_tab(self, action, param):
        if self._window:
            self._window._on_new_tab()

    def _on_close_tab(self, action, param):
        if self._window:
            self._window._on_close_tab()

    def _on_open_schema(self, action, param):
        if self._window:
            self._window._on_file_open()

    def _on_save_schema(self, action, param):
        if self._window:
            self._window._on_file_save()

    def _on_save_schema_as(self, action, param):
        if self._window:
            self._window._on_file_save_as()

    def _on_export_csv(self, action, param):
        if self._window:
            self._window._on_export_csv()

    def _on_export_json(self, action, param):
        if self._window:
            self._window._on_export_json()

    def _on_import_csv(self, action, param):
        if self._window:
            self._window._on_import_csv()

    def _on_import_json(self, action, param):
        if self._window:
            self._window._on_import_json()

    def _on_quit(self, action, param):
        self._app.quit()

    # --- Edit ---

    def _register_edit_actions(self):
        self._add_action("undo", self._on_undo, ["<Ctrl>Z"])
        self._add_action("redo", self._on_redo, ["<Ctrl>Y"])
        self._add_action("cut", self._on_cut, ["<Ctrl>X"])
        self._add_action("copy", self._on_copy, ["<Ctrl>C"])
        self._add_action("paste", self._on_paste, ["<Ctrl>V"])
        self._add_action("preferences", self._on_preferences)
        self._add_action("find", self._on_find, ["<Ctrl>F"])
        self._add_action("find_next", self._on_find_next, ["F3"])
        self._add_action("find_prev", self._on_find_prev, ["<Shift>F3"])
        self._add_action("replace", self._on_replace_dialog, ["<Ctrl>H"])

    def _on_undo(self, action, param):
        buffer = self._get_editor_buffer()
        if buffer:
            buffer.undo()

    def _on_redo(self, action, param):
        buffer = self._get_editor_buffer()
        if buffer:
            buffer.redo()

    def _on_cut(self, action, param):
        view = self._get_editor_view()
        if view:
            view.emit("cut-clipboard")

    def _on_copy(self, action, param):
        if self._window:
            focused = self._window.get_focus()
            if focused and hasattr(focused, "emit"):
                focused.emit("copy-clipboard")

    def _on_paste(self, action, param):
        view = self._get_editor_view()
        if view:
            view.emit("paste-clipboard")

    def _on_find(self, action, param):
        if self._window and hasattr(self._window, 'editor'):
            self._window.editor._on_find()

    def _on_find_next(self, action, param):
        if self._window and hasattr(self._window, 'editor'):
            self._window.editor._on_find_next()

    def _on_find_prev(self, action, param):
        if self._window and hasattr(self._window, 'editor'):
            self._window.editor._on_find_prev()

    def _on_replace_dialog(self, action, param):
        if self._window and hasattr(self._window, 'editor'):
            self._window.editor._on_find()
            GLib.idle_add(self._window.editor._replace_entry.grab_focus)

    def _on_preferences(self, action, param):
        if self._window:
            from src.ui.dialogs.preferences import PreferencesDialog

            dialog = PreferencesDialog(
                self._window,
                editor=self._window.editor if hasattr(self._window, "editor") else None,
            )
            dialog.present()

    # --- View ---

    def _register_view_actions(self):
        self._add_action("view_browser", self._on_view_browser)
        self._add_action("view_editor", self._on_view_editor)
        self._add_action("view_results", self._on_view_results)
        self._add_action("view_hooks", self._on_view_hooks)
        self._add_action("view_analytics", self._on_view_analytics)
        self._add_action("query_history", self._on_query_history)

    def _on_view_browser(self, action, param):
        logger.info("Toggle browser visibility (not implemented)")

    def _on_view_editor(self, action, param):
        logger.info("Toggle editor visibility (not implemented)")

    def _on_view_results(self, action, param):
        logger.info("Toggle results visibility (not implemented)")

    def _on_view_hooks(self, action, param):
        if self._window:
            from src.ui.dialogs.hook_manager import HookManagerDialog

            dialog = HookManagerDialog(self._window, db_connector=self._window.db_connector)
            dialog.present()

    def _on_view_analytics(self, action, param):
        logger.info("Open analytics dashboard (not implemented)")

    # --- Query ---

    def _register_query_actions(self):
        self._add_action("query_execute", self._on_query_execute, ["F5"])
        self._add_action("query_execute_selection", self._on_query_execute_selection)
        self._add_action("query_format", self._on_query_format)
        self._add_action("query_explain", self._on_query_explain)

    def _on_query_execute(self, action, param):
        if self._window:
            self._window._on_run_clicked()

    def _on_query_execute_selection(self, action, param):
        if self._window:
            self._window._on_run_clicked()

    def _on_query_format(self, action, param):
        if self._window and hasattr(self._window, "editor"):
            import sqlparse

            query = self._window.editor.get_text()
            formatted = sqlparse.format(query, reindent=True, keyword_case="upper")
            self._window.editor.set_text(formatted)

    def _on_query_explain(self, action, param):
        if self._window and hasattr(self._window, "editor"):
            query = self._window.editor.get_selected_text()
            if query.strip():
                self._window.editor.set_text(f"EXPLAIN ANALYZE {query}")
                self._window._on_run_clicked()

    def _on_query_history(self, action, param):
        if self._window:
            self._window._on_query_history_clicked()

    # --- Tools ---

    def _register_tools_actions(self):
        self._add_action("tools_schema_designer", self._on_tools_schema_designer)
        self._add_action("tools_migration", self._on_tools_migration)
        self._add_action("tools_index_advisor", self._on_tools_index_advisor)
        self._add_action("tools_query_analyzer", self._on_tools_query_analyzer)

    def _on_tools_schema_designer(self, action, param):
        if self._window:
            self._window._on_designer_clicked()

    def _on_tools_migration(self, action, param):
        logger.info("Open migration generator (not implemented)")

    def _on_tools_index_advisor(self, action, param):
        if self._window and self._window.db_connector.is_connected:
            from src.analytics.index_advisor import IndexAdvisor

            advisor = IndexAdvisor()
            recommendations = advisor.analyze_all_tables(self._window.db_connector)

            # Show results in editor
            sql_lines = ["-- AI Index Advisor Recommendations\n"]
            for table, recs in recommendations.items():
                sql_lines.append(f"-- Table: {table}")
                for r in recs:
                    sql_lines.append(f"-- {r['reason']} [{r['priority']}]")
                    sql_lines.append(r["sql"])
                    sql_lines.append("")

            self._window.editor.set_text("\n".join(sql_lines))
            self._window.results.show_text(
                f"Found {sum(len(r) for r in recommendations.values())} index recommendations "
                f"across {len(recommendations)} tables.\n\n"
                f"Recommendations loaded in SQL editor — review and execute manually."
            )
        else:
            logger.warning("Not connected to database")

    def _on_tools_query_analyzer(self, action, param):
        logger.info("Open query analyzer (not implemented)")

    # --- Help ---

    def _register_help_actions(self):
        self._add_action("help_docs", self._on_help_docs)
        self._add_action("about", self._on_about)

    def _on_help_docs(self, action, param):
        logger.info("Open documentation (not implemented)")

    def _on_about(self, action, param):
        show_about(self._window)
