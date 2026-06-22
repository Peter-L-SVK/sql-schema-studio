# ----------------------------------------------------------------------
# SQL Schema Studio 0.9 - Editor Tab (GPLv3)
# Copyright (C) 2026 Peter Leukanič
# License: GNU GPL v3+ <https://www.gnu.org/licenses/gpl-3.0.txt>
# This is free software with NO WARRANTY.
# Feel free to distribute and modify.
# ----------------------------------------------------------------------

"""Single editor tab with GtkSourceView and autocomplete."""

from __future__ import annotations
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("GtkSource", "5")
from gi.repository import Gtk, GtkSource, Gdk, GLib

from src.ui.editor.keywords import SQL_KEYWORDS


class EditorTab(Gtk.Box):
    """Single editor tab with GtkSourceView and custom Popover autocomplete."""

    _autocomplete_enabled = True

    @classmethod
    def set_autocomplete_enabled(cls, enabled: bool):
        """Enable or disable autocomplete globally for all EditorTab instances."""
        cls._autocomplete_enabled = enabled

    def __init__(self, parent_editor, title: str = "Query", content: str = ""):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self._parent_editor = parent_editor
        self._window = parent_editor._window
        self._title = title
        self._search_highlight_tag = None

        self._completion_popover: Gtk.Popover | None = None
        self._completion_list: Gtk.ListBox | None = None
        self._completion_matches: list[str] = []
        self._selected_index: int = -1
        self._completing: bool = False
        self._popover_debounce_id: int = 0
        self._prev_text_length: int = 0

        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)

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

        if content:
            self._view.get_buffer().set_text(content)

        self._setup_sql_language()
        self._setup_autocomplete()

        key_controller = Gtk.EventControllerKey()
        key_controller.connect("key-pressed", self._on_key_pressed)
        self._view.add_controller(key_controller)

        scroll.set_child(self._view)
        self.append(scroll)

        self._modified: bool = False
        self._original_title: str = title

        buffer = self._view.get_buffer()
        buffer.connect("modified-changed", self._on_modified_changed)

    def _setup_sql_language(self):
        manager = GtkSource.LanguageManager.get_default()
        lang = manager.get_language("sql")
        if not lang:
            for lang_id in manager.get_language_ids():
                if "sql" in lang_id.lower():
                    lang = manager.get_language(lang_id)
                    break
        if lang:
            buffer = self._view.get_buffer()
            buffer.set_language(lang)
            scheme_manager = GtkSource.StyleSchemeManager.get_default()
            for scheme_id in ["classic", "tango", "oblivion", "cobalt"]:
                scheme = scheme_manager.get_scheme(scheme_id)
                if scheme:
                    buffer.set_style_scheme(scheme)
                    break

    def _setup_autocomplete(self):
        self._build_completion_popover()
        buffer = self._view.get_buffer()
        buffer.connect("changed", self._on_buffer_changed)

    def _build_completion_popover(self):
        self._completion_popover = Gtk.Popover()
        self._completion_popover.set_autohide(True)
        self._completion_popover.set_has_arrow(False)
        self._completion_popover.set_parent(self._view)
        self._completion_popover.add_css_class("completion-popover")

        self._completion_list = Gtk.ListBox()
        self._completion_list.add_css_class("completion-list")
        self._completion_list.connect("row-activated", self._on_completion_activated)
        self._completion_popover.set_child(self._completion_list)

    def _get_word_at_cursor(self) -> tuple[str, Gtk.TextIter, Gtk.TextIter]:
        buffer = self._view.get_buffer()
        cursor = buffer.get_iter_at_mark(buffer.get_insert())
        end = cursor.copy()

        start = cursor.copy()
        while not start.starts_line():
            prev = start.copy()
            if not prev.backward_char():
                break
            ch = prev.get_char()
            if ch in " \t\n\r()[]{},;.=<>!+-*/%|&^~@#:;\"'`":
                break
            start = prev

        word = buffer.get_text(start, end, False)

        expanded_start = start.copy()
        for _ in range(3):
            while not expanded_start.starts_line():
                prev = expanded_start.copy()
                if not prev.backward_char():
                    break
                ch = prev.get_char()
                if ch not in " \t\n\r":
                    expanded_start = prev
                    break
                expanded_start = prev
            else:
                break

            prev_word_start = expanded_start.copy()
            while not prev_word_start.starts_line():
                prev = prev_word_start.copy()
                if not prev.backward_char():
                    break
                ch = prev.get_char()
                if ch in " \t\n\r()[]{},;.=<>!+-*/%|&^~@#:;\"'`":
                    break
                prev_word_start = prev

            candidate = buffer.get_text(prev_word_start, end, False)
            candidate_upper = candidate.upper()

            if any(kw.startswith(candidate_upper) for kw in SQL_KEYWORDS):
                start = prev_word_start
                word = candidate

        return word, start, end

    def _on_buffer_changed(self, buffer):
        if self._completing:
            return

        current_len = buffer.get_char_count()

        if current_len < self._prev_text_length:
            self._hide_completion()
            self._prev_text_length = current_len
            if self._popover_debounce_id:
                GLib.source_remove(self._popover_debounce_id)
                self._popover_debounce_id = 0
            return

        self._prev_text_length = current_len

        if self._popover_debounce_id:
            GLib.source_remove(self._popover_debounce_id)
        self._popover_debounce_id = GLib.timeout_add(300, self._do_update_popover, buffer)

    def _do_update_popover(self, buffer):
        self._popover_debounce_id = 0
        word, start, end = self._get_word_at_cursor()

        if len(word) < 3:
            self._hide_completion()
            return False

        word_upper = word.upper()

        matches = [kw for kw in SQL_KEYWORDS if kw.startswith(word_upper)]

        if not matches:
            self._hide_completion()
            return False

        exact = [m for m in matches if m.upper() == word_upper]
        starts = [m for m in matches if m.upper() != word_upper]
        matches = exact + sorted(starts)

        if len(matches) > 15:
            matches = matches[:15]

        self._completion_matches = matches
        self._selected_index = -1
        self._populate_completion_list(matches)
        self._show_completion_at_iter(start)
        return False

    def _populate_completion_list(self, matches: list[str]):
        if self._completion_list is None:
            return
        self._completion_list.remove_all()
        for i, kw in enumerate(matches):
            row = Gtk.ListBoxRow()
            lbl = Gtk.Label(label=kw)
            lbl.set_xalign(0.0)
            lbl.set_margin_start(8)
            lbl.set_margin_end(8)
            lbl.set_margin_top(3)
            lbl.set_margin_bottom(3)
            row.set_child(lbl)
            self._completion_list.append(row)

    def _show_completion_at_iter(self, text_iter: Gtk.TextIter):
        if self._completion_popover is None:
            return
        rect = self._view.get_iter_location(text_iter)
        wx, wy = self._view.buffer_to_window_coords(Gtk.TextWindowType.WIDGET, rect.x, rect.y)
        point = Gdk.Rectangle()
        point.x = wx
        point.y = wy
        point.width = max(rect.width, 4)
        point.height = rect.height
        self._completion_popover.set_pointing_to(point)
        self._completion_popover.popup()

    def _hide_completion(self):
        if self._completion_popover is not None and self._completion_popover.is_visible():
            self._completion_popover.popdown()

    def _apply_completion(self, keyword: str):
        buffer = self._view.get_buffer()
        word, start, end = self._get_word_at_cursor()
        self._completing = True
        buffer.begin_user_action()
        buffer.delete(start, end)
        buffer.insert(start, keyword)
        buffer.end_user_action()
        self._completing = False
        self._hide_completion()
        self._view.grab_focus()

    def _on_completion_activated(self, listbox, row):
        if self._completion_matches is None:
            return
        idx = row.get_index()
        if 0 <= idx < len(self._completion_matches):
            self._apply_completion(self._completion_matches[idx])

    def _select_next_in_popover(self):
        if not self._completion_matches or self._completion_list is None:
            return
        self._selected_index += 1
        if self._selected_index >= len(self._completion_matches):
            self._selected_index = 0
        row = self._completion_list.get_row_at_index(self._selected_index)
        if row:
            self._completion_list.select_row(row)
            row.grab_focus()

    def _select_prev_in_popover(self):
        if not self._completion_matches or self._completion_list is None:
            return
        self._selected_index -= 1
        if self._selected_index < 0:
            self._selected_index = len(self._completion_matches) - 1
        row = self._completion_list.get_row_at_index(self._selected_index)
        if row:
            self._completion_list.select_row(row)
            row.grab_focus()

    def _on_key_pressed(self, controller, keyval, keycode, state):
        if self._completion_popover and self._completion_popover.is_visible():
            if keyval in (Gdk.KEY_Down, Gdk.KEY_KP_Down):
                self._select_next_in_popover()
                return True
            if keyval in (Gdk.KEY_Up, Gdk.KEY_KP_Up):
                self._select_prev_in_popover()
                return True
            if keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter, Gdk.KEY_Tab):
                if 0 <= self._selected_index < len(self._completion_matches):
                    self._apply_completion(self._completion_matches[self._selected_index])
                elif self._completion_matches:
                    self._apply_completion(self._completion_matches[0])
                return True
            if keyval == Gdk.KEY_Escape:
                self._hide_completion()
                return True

        if keyval == Gdk.KEY_F5:
            self._window._on_run_clicked()
            return True
        if keyval == Gdk.KEY_Return and (state & Gdk.ModifierType.CONTROL_MASK):
            self._window._on_run_clicked()
            return True
        if keyval == Gdk.KEY_f and (state & Gdk.ModifierType.CONTROL_MASK):
            self._parent_editor._on_find()
            return True
        if keyval == Gdk.KEY_h and (state & Gdk.ModifierType.CONTROL_MASK):
            self._parent_editor._on_find()
            GLib.idle_add(self._parent_editor._replace_entry.grab_focus)
            return True
        if keyval == Gdk.KEY_Escape and self._parent_editor._search_revealer.get_reveal_child():
            self._parent_editor._search_revealer.set_reveal_child(False)
            self._parent_editor._clear_search_highlights()
            self._view.grab_focus()
            return True
        if keyval == Gdk.KEY_F3:
            if state & Gdk.ModifierType.SHIFT_MASK:
                self._parent_editor._on_find_prev()
            else:
                self._parent_editor._on_find_next()
            return True
        if keyval == Gdk.KEY_t and (state & Gdk.ModifierType.CONTROL_MASK):
            self._parent_editor.add_tab()
            return True

        return False

    def get_text(self) -> str:
        buffer = self._view.get_buffer()
        start = buffer.get_start_iter()
        end = buffer.get_end_iter()
        return str(buffer.get_text(start, end, False))

    def set_text(self, text: str):
        buffer = self._view.get_buffer()
        buffer.set_text(text)
        buffer.set_modified(False)

    def get_selected_text(self) -> str:
        buffer = self._view.get_buffer()
        if buffer.get_has_selection():
            start, end = buffer.get_selection_bounds()
            return str(buffer.get_text(start, end, False))
        return self.get_text()

    def _on_modified_changed(self, buffer):
        self._modified = buffer.get_modified()
        if self._modified:
            self._parent_editor.rename_tab(self, f"• {self._original_title}")
        else:
            self._parent_editor.rename_tab(self, self._original_title)
