# ----------------------------------------------------------------------
# SQL Schema Studio 0.9 - Editor Tabs Container (GPLv3)
# Copyright (C) 2026 Peter Leukanič
# License: GNU GPL v3+ <https://www.gnu.org/licenses/gpl-3.0.txt>
# This is free software with NO WARRANTY.
# Feel free to distribute and modify.
# ----------------------------------------------------------------------

"""Multi-tab SQL editor container with search/replace."""

from __future__ import annotations
import gi
import re
from typing import Optional, cast

gi.require_version("Gtk", "4.0")
gi.require_version("GtkSource", "5")
from gi.repository import Gtk, GtkSource, Gdk, Pango, GLib

from src.ui.editor.editor_tab import EditorTab


class EditorTabs(Gtk.Box):
    """SQL editor panel with tabs and search/replace."""

    def __init__(self, window):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.set_vexpand(True)
        self.set_hexpand(True)

        self._window = window
        self._tabs: list[EditorTab] = []
        self._tab_labels: list[Gtk.Label] = []
        self._active_tab_index = -1
        self._current_search_text = ""
        self._search_debounce_id = 0
        self._tab_counter = 0

        tab_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        tab_bar.add_css_class("tab-bar-container")

        self._notebook = Gtk.Notebook()
        self._notebook.set_scrollable(True)
        self._notebook.set_hexpand(True)
        self._notebook.set_vexpand(True)
        self._notebook.connect("switch-page", self._on_tab_switched)
        tab_bar.append(self._notebook)

        self._new_tab_btn = Gtk.Button.new_from_icon_name("list-add-symbolic")
        self._new_tab_btn.set_has_frame(False)
        self._new_tab_btn.set_tooltip_text("New tab (Ctrl+T)")
        self._new_tab_btn.add_css_class("new-tab-button")
        self._new_tab_btn.add_css_class("flat")
        self._new_tab_btn.connect("clicked", lambda b: self.add_tab())
        self._notebook.set_action_widget(self._new_tab_btn, Gtk.PackType.END)

        self.append(tab_bar)

        self._search_revealer = Gtk.Revealer()
        self._search_revealer.set_transition_type(Gtk.RevealerTransitionType.SLIDE_DOWN)
        self._search_revealer.set_reveal_child(False)
        self._build_search_bar()
        self.append(self._search_revealer)

        self.add_tab()
        self._load_settings()

    def _generate_tab_title(self) -> str:
        self._tab_counter += 1
        return f"Query {self._tab_counter}"

    def _apply_settings_to_tab(self, tab: EditorTab):
        from src.utils.settings import Settings

        settings = Settings()
        editor = settings.get_section("editor")
        scheme_id = editor.get("color_scheme", "classic")
        font_str = editor.get("font", "Monospace 12")

        view = tab._view
        buffer = view.get_buffer()
        view.set_tab_width(editor.get("tab_width", 4))
        view.set_insert_spaces_instead_of_tabs(editor.get("spaces_instead_of_tabs", True))
        view.set_show_line_numbers(editor.get("show_line_numbers", True))
        view.set_highlight_current_line(editor.get("highlight_current_line", True))

        manager = GtkSource.StyleSchemeManager.get_default()
        scheme = manager.get_scheme(scheme_id)
        if scheme:
            buffer.set_style_scheme(scheme)

        font_desc = Pango.FontDescription.from_string(font_str)
        css = f"""
        textview {{
            font-family: {font_desc.get_family()};
            font-size: {font_desc.get_size() // Pango.SCALE}pt;
        }}
        """
        provider = Gtk.CssProvider()
        provider.load_from_data(css.encode())
        view.get_style_context().add_provider(provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

    def _load_settings(self):
        for tab in self._tabs:
            self._apply_settings_to_tab(tab)

    def add_tab(self, title: Optional[str] = None, content: str = "") -> EditorTab:
        if title is None:
            title = self._generate_tab_title()
        else:
            self._tab_counter += 1

        tab = EditorTab(self, title, content)
        tab._search_highlight_tag = self._create_highlight_tag(tab._view.get_buffer())

        label_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=2)
        label = Gtk.Label(label=title)
        btn_close = Gtk.Button.new_from_icon_name("window-close-symbolic")
        btn_close.set_has_frame(False)
        btn_close.set_tooltip_text("Close tab")
        btn_close.add_css_class("tab-close-button")
        btn_close.connect("clicked", lambda b, t=tab: self.close_tab(t))
        label_box.append(label)
        label_box.append(btn_close)

        page_num = self._notebook.append_page(tab, label_box)
        self._notebook.set_tab_reorderable(tab, True)
        self._tabs.append(tab)
        self._tab_labels.append(label)
        self._active_tab_index = page_num
        self._notebook.set_current_page(page_num)
        tab._view.grab_focus()

        self._apply_settings_to_tab(tab)
        return tab

    def close_tab(self, tab: EditorTab):
        if len(self._tabs) <= 1:
            return
        idx = self._tabs.index(tab)
        self._notebook.remove_page(idx)
        self._tabs.remove(tab)
        self._tab_labels.pop(idx)
        if self._active_tab_index >= len(self._tabs):
            self._active_tab_index = len(self._tabs) - 1

    def rename_tab(self, tab: EditorTab, new_title: str):
        idx = self._tabs.index(tab)
        if 0 <= idx < len(self._tab_labels):
            if not new_title.startswith("• "):
                tab._original_title = new_title
            self._tab_labels[idx].set_text(new_title)

    def get_active_tab(self) -> EditorTab | None:
        page_num = self._notebook.get_current_page()
        if 0 <= page_num < len(self._tabs):
            return cast(EditorTab, self._tabs[page_num])
        return None

    def get_text(self) -> str:
        tab = self.get_active_tab()
        return tab.get_text() if tab else ""

    def set_text(self, text: str):
        tab = self.get_active_tab()
        if tab:
            tab.set_text(text)

    def get_selected_text(self) -> str:
        tab = self.get_active_tab()
        return tab.get_selected_text() if tab else ""

    def _on_tab_switched(self, notebook, page, page_num):
        self._active_tab_index = page_num
        self._clear_search_highlights()
        if self._search_revealer.get_reveal_child():
            search_text = self._search_entry.get_text()
            if search_text:
                self._highlight_all_matches(search_text)

    def _create_highlight_tag(self, buffer):
        return buffer.create_tag(
            "search_highlight",
            background="yellow",
            background_rgba=Gdk.RGBA(red=1.0, green=1.0, blue=0.0, alpha=0.5),
        )

    def _clear_search_highlights(self):
        tab = self.get_active_tab()
        if tab and tab._search_highlight_tag:
            buffer = tab._view.get_buffer()
            start = buffer.get_start_iter()
            end = buffer.get_end_iter()
            buffer.remove_tag(tab._search_highlight_tag, start, end)

    def _do_highlight(self, search_text):
        self._search_debounce_id = 0
        self._current_search_text = search_text
        self._highlight_all_matches(search_text)
        return False

    def _highlight_all_matches(self, search_text: str):
        tab = self.get_active_tab()
        if not tab or not tab._search_highlight_tag:
            return
        buffer = tab._view.get_buffer()
        self._clear_search_highlights()
        if not search_text or len(search_text) > 200:
            return
        start = buffer.get_start_iter()
        end = buffer.get_end_iter()
        if buffer.get_char_count() > 500_000:
            return
        flags = re.IGNORECASE if not self._case_check.get_active() else 0
        if self._whole_word_check.get_active():
            pattern = r"\b" + re.escape(search_text) + r"\b"
        else:
            pattern = re.escape(search_text)
        try:
            regex = re.compile(pattern, flags)
        except re.error:
            return
        text = buffer.get_text(start, end, False)
        match_count = 0
        for match in regex.finditer(text):
            if match_count >= 5000:
                break
            iter_start = buffer.get_iter_at_offset(match.start())
            iter_end = buffer.get_iter_at_offset(match.end())
            buffer.apply_tag(tab._search_highlight_tag, iter_start, iter_end)
            match_count += 1

    def _on_find(self):
        self._search_revealer.set_reveal_child(True)
        self._search_entry.grab_focus()
        self._search_entry.select_region(0, -1)
        tab = self.get_active_tab()
        if tab:
            selected = tab.get_selected_text()
            if selected and len(selected) < 100:
                self._search_entry.set_text(selected)
                self._search_entry.select_region(0, -1)
                self._highlight_all_matches(selected)

    def _on_find_next(self):
        search_text = self._search_entry.get_text()
        if not search_text:
            return
        self._search_text(search_text, forward=True)

    def _on_find_prev(self):
        search_text = self._search_entry.get_text()
        if not search_text:
            return
        self._search_text(search_text, forward=False)

    def _on_search_changed(self, entry):
        if self._search_debounce_id:
            GLib.source_remove(self._search_debounce_id)
            self._search_debounce_id = 0
        self._search_debounce_id = GLib.timeout_add(300, self._do_highlight, entry.get_text())

    def _get_search_flags(self):
        flags = Gtk.TextSearchFlags.VISIBLE_ONLY | Gtk.TextSearchFlags.TEXT_ONLY
        if not self._case_check.get_active():
            flags |= Gtk.TextSearchFlags.CASE_INSENSITIVE
        return flags

    def _search_text(self, search_text: str, forward: bool = True):
        tab = self.get_active_tab()
        if not tab or not search_text:
            return
        buffer = tab._view.get_buffer()
        cursor_iter = buffer.get_iter_at_mark(buffer.get_insert())
        if forward and buffer.get_has_selection():
            cursor_iter = buffer.get_iter_at_mark(buffer.get_selection_bound())

        flags = self._get_search_flags()

        # ── Whole-word: use regex to find the next/previous match ──
        if self._whole_word_check.get_active():
            pattern = r"\b" + re.escape(search_text) + r"\b"
            re_flags = re.IGNORECASE if not self._case_check.get_active() else 0
            try:
                regex = re.compile(pattern, re_flags)
            except re.error:
                return

            full_text = buffer.get_text(
                buffer.get_start_iter(), buffer.get_end_iter(), False
            )
            cursor_offset = cursor_iter.get_offset()

            if forward:
                m = regex.search(full_text, cursor_offset)
            else:
                # Search backwards from cursor — find last match before cursor
                m = None
                for match in regex.finditer(full_text):
                    if match.start() >= cursor_offset:
                        break
                    m = match

            if m:
                match_start = buffer.get_iter_at_offset(m.start())
                match_end = buffer.get_iter_at_offset(m.end())
                buffer.select_range(match_start, match_end)
                tab._view.scroll_to_iter(match_start, 0.0, True, 0.0, 0.0)
            else:
                # Wrap around
                if forward:
                    m = regex.search(full_text)
                else:
                    m = None
                    for match in regex.finditer(full_text):
                        m = match  # keep last match
                if m:
                    match_start = buffer.get_iter_at_offset(m.start())
                    match_end = buffer.get_iter_at_offset(m.end())
                    buffer.select_range(match_start, match_end)
                    tab._view.scroll_to_iter(match_start, 0.0, True, 0.0, 0.0)
            return

        # ── Partial match: use GTK's built-in search (unchanged) ──
        if forward:
            found = cursor_iter.forward_search(search_text, flags, None)
        else:
            found = cursor_iter.backward_search(search_text, flags, None)
        if found:
            match_start, match_end = found
            buffer.select_range(match_start, match_end)
            tab._view.scroll_to_iter(match_start, 0.0, True, 0.0, 0.0)
        else:
            if forward:
                wrap_iter = buffer.get_start_iter()
                found = wrap_iter.forward_search(search_text, flags, None)
            else:
                wrap_iter = buffer.get_end_iter()
                found = wrap_iter.backward_search(search_text, flags, None)
            if found:
                match_start, match_end = found
                buffer.select_range(match_start, match_end)
                tab._view.scroll_to_iter(match_start, 0.0, True, 0.0, 0.0)

    def _on_replace(self):
        tab = self.get_active_tab()
        if not tab:
            return
        buffer = tab._view.get_buffer()
        if buffer.get_has_selection():
            start, end = buffer.get_selection_bounds()
            selected = buffer.get_text(start, end, False)
            search_text = self._search_entry.get_text()
            if self._case_check.get_active():
                matches = selected == search_text
            else:
                matches = selected.lower() == search_text.lower()
            if matches:
                buffer.delete_selection(True, True)
                buffer.insert_at_cursor(self._replace_entry.get_text())
                self._highlight_all_matches(search_text)
                self._search_text(search_text, forward=True)

    def _on_replace_all(self):
        tab = self.get_active_tab()
        if not tab:
            return
        buffer = tab._view.get_buffer()
        search = self._search_entry.get_text()
        replace = self._replace_entry.get_text()
        if not search:
            return
        start = buffer.get_start_iter()
        end = buffer.get_end_iter()
        text = buffer.get_text(start, end, False)

        # Build pattern respecting whole-word and case
        if self._whole_word_check.get_active():
            pattern = r"\b" + re.escape(search) + r"\b"
        else:
            pattern = re.escape(search)

        if self._case_check.get_active():
            count = len(re.findall(pattern, text))
            new_text = re.sub(pattern, replace, text)
        else:
            count = len(re.findall(pattern, text, re.IGNORECASE))
            new_text = re.sub(
                pattern, replace, text, flags=re.IGNORECASE
            )
        if count > 0:
            buffer.set_text(new_text)
            self._window.statusbar.set_message(f"Replaced {count} occurrences")
            if self._search_revealer.get_reveal_child():
                self._highlight_all_matches(self._search_entry.get_text())

    def _build_search_bar(self):
        search_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        search_box.set_margin_start(6)
        search_box.set_margin_end(6)
        search_box.set_margin_top(4)
        search_box.set_margin_bottom(4)
        search_box.add_css_class("toolbar")

        search_label = Gtk.Label(label="Find:")
        search_box.append(search_label)

        self._search_entry = Gtk.Entry()
        self._search_entry.set_placeholder_text("Search...")
        self._search_entry.set_hexpand(True)
        self._search_entry.connect("changed", self._on_search_changed)
        self._search_entry.connect("activate", lambda e: self._on_find_next())
        search_box.append(self._search_entry)

        btn_prev = Gtk.Button(label="◀")
        btn_prev.set_tooltip_text("Previous match (Shift+F3)")
        btn_prev.connect("clicked", lambda b: self._on_find_prev())
        search_box.append(btn_prev)

        btn_next = Gtk.Button(label="▶")
        btn_next.set_tooltip_text("Next match (F3 or Enter)")
        btn_next.connect("clicked", lambda b: self._on_find_next())
        search_box.append(btn_next)

        sep = Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)
        search_box.append(sep)

        replace_label = Gtk.Label(label="Replace:")
        search_box.append(replace_label)

        self._replace_entry = Gtk.Entry()
        self._replace_entry.set_placeholder_text("Replace with...")
        self._replace_entry.set_hexpand(True)
        self._replace_entry.connect("activate", lambda e: self._on_replace())
        search_box.append(self._replace_entry)

        btn_replace = Gtk.Button(label="Replace")
        btn_replace.set_tooltip_text("Replace current match")
        btn_replace.connect("clicked", lambda b: self._on_replace())
        search_box.append(btn_replace)

        btn_replace_all = Gtk.Button(label="Replace All")
        btn_replace_all.set_tooltip_text("Replace all occurrences")
        btn_replace_all.connect("clicked", lambda b: self._on_replace_all())
        search_box.append(btn_replace_all)

        sep2 = Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)
        search_box.append(sep2)

        self._case_check = Gtk.CheckButton(label="Aa")
        self._case_check.set_tooltip_text("Case sensitive (unchecked = case insensitive)")
        self._case_check.connect("toggled", lambda b: self._on_search_changed(self._search_entry))
        search_box.append(self._case_check)

        self._whole_word_check = Gtk.CheckButton(label="ab|")
        self._whole_word_check.set_tooltip_text("Match whole word only")
        self._whole_word_check.connect(
            "toggled", lambda b: self._on_search_changed(self._search_entry)
        )
        search_box.append(self._whole_word_check)

        btn_close = Gtk.Button(label="✕")
        btn_close.set_tooltip_text("Close search bar (Escape)")
        btn_close.connect("clicked", lambda b: self._search_revealer.set_reveal_child(False))
        search_box.append(btn_close)

        self._search_revealer.set_child(search_box)

    def get_active_buffer(self):
        tab = self.get_active_tab()
        return tab._view.get_buffer() if tab else None

    def get_active_view(self):
        tab = self.get_active_tab()
        return tab._view if tab else None

    def has_unsaved_changes(self) -> bool:
        for tab in self._tabs:
            if tab._modified:
                return True
        return False

    def get_unsaved_tabs(self) -> list[str]:
        return [tab._title for tab in self._tabs if tab._modified]
