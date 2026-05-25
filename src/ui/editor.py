# ----------------------------------------------------------------------
# SQL Schema Studio 0.2 - SQL Editor (GPLv3)
# Copyright (C) 2026 Peter Leukanič
# License: GNU GPL v3+ <https://www.gnu.org/licenses/gpl-3.0.txt>
# This is free software with NO WARRANTY.
# Feel free to distribute and modify.
# ----------------------------------------------------------------------

"""SQL Editor with syntax highlighting and line numbers"""

from __future__ import annotations
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("GtkSource", "5")
from gi.repository import Gtk, GtkSource, Gdk


class SQLEditor(Gtk.Box):
    """SQL editor panel with GtkSourceView"""

    def __init__(self, window):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self._window = window

        # Header
        header = Gtk.Label(label="SQL Editor")
        header.add_css_class("panel-header")
        header.set_halign(Gtk.Align.START)
        self.append(header)

        # Scrolled window
        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)

        # SourceView
        self._view = GtkSource.View()
        self._view.set_monospace(True)
        self._view.set_wrap_mode(Gtk.WrapMode.WORD)
        self._view.set_auto_indent(True)
        self._view.set_indent_width(4)
        self._view.set_insert_spaces_instead_of_tabs(True)
        self._view.set_tab_width(4)
        self._view.set_show_line_numbers(True)
        self._view.set_highlight_current_line(True)
        self._view.set_smart_backspace(True)
        self._view.set_right_margin_position(80)
        self._view.set_show_right_margin(True)

        # SQL language setup
        self._setup_sql_language()

        # Keyboard shortcuts
        key_controller = Gtk.EventControllerKey()
        key_controller.connect("key-pressed", self._on_key_pressed)
        self._view.add_controller(key_controller)

        scroll.set_child(self._view)
        self.append(scroll)

    def _setup_sql_language(self):
        """Configure SQL syntax highlighting"""
        manager = GtkSource.LanguageManager.get_default()

        # Try to find SQL language
        lang = manager.get_language("sql")

        # Try alternative language IDs
        if not lang:
            for lang_id in manager.get_language_ids():
                if "sql" in lang_id.lower():
                    lang = manager.get_language(lang_id)
                    break

        if lang:
            buffer = self._view.get_buffer()
            buffer.set_language(lang)

            # Try a dark-friendly scheme first, then fall back
            scheme_manager = GtkSource.StyleSchemeManager.get_default()
            for scheme_id in ["classic", "tango", "oblivion", "cobalt"]:
                scheme = scheme_manager.get_scheme(scheme_id)
                if scheme:
                    buffer.set_style_scheme(scheme)
                    break

    def get_text(self) -> str:
        """Get all text from the editor"""
        buffer = self._view.get_buffer()
        start = buffer.get_start_iter()
        end = buffer.get_end_iter()
        return str(buffer.get_text(start, end, False))

    def get_selected_text(self) -> str:
        """Get selected text, or all text if no selection"""
        buffer = self._view.get_buffer()
        if buffer.get_has_selection():
            start, end = buffer.get_selection_bounds()
            return str(buffer.get_text(start, end, False))
        return self.get_text()

    def set_text(self, text: str):
        """Set editor content"""
        buffer = self._view.get_buffer()
        buffer.set_text(text)

    def _on_key_pressed(self, controller, keyval, keycode, state):
        """Handle keyboard shortcuts"""
        # F5 or Ctrl+Enter = Execute
        if keyval == Gdk.KEY_F5:
            self._window._on_run_clicked()
            return True
        if keyval == Gdk.KEY_Return and (state & Gdk.ModifierType.CONTROL_MASK):
            self._window._on_run_clicked()
            return True
        return False
