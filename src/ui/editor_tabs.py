# ----------------------------------------------------------------------
# SQL Schema Studio 0.9 - SQL Editor with Tabs (GPLv3)
# Copyright (C) 2026 Peter Leukanič
# License: GNU GPL v3+ <https://www.gnu.org/licenses/gpl-3.0.txt>
# This is free software with NO WARRANTY.
# Feel free to distribute and modify.
# ----------------------------------------------------------------------

"""SQL Editor with multiple tabs, syntax highlighting, and search/replace."""

from __future__ import annotations
import gi
import re

gi.require_version("Gtk", "4.0")
gi.require_version("GtkSource", "5")
from gi.repository import Gtk, GtkSource, Gdk, Pango, GLib


SQL_KEYWORDS = [
    # DML
    "SELECT", "FROM", "WHERE", "INSERT", "INTO", "VALUES",
    "UPDATE", "SET", "DELETE", "RETURNING",
    # DDL
    "CREATE", "TABLE", "DROP", "ALTER", "ADD", "COLUMN",
    "INDEX", "VIEW", "SEQUENCE", "SCHEMA", "DATABASE", "EXTENSION",
    # Joins
    "JOIN", "LEFT", "RIGHT", "INNER", "OUTER", "FULL", "CROSS", "NATURAL",
    # Filtering / ordering
    "ON", "AND", "OR", "NOT", "IN", "EXISTS", "BETWEEN", "LIKE", "ILIKE",
    "HAVING", "LIMIT", "OFFSET", "DISTINCT", "ALL", "AS",
    "UNION", "INTERSECT", "EXCEPT",
    # Multi-word phrases
    "GROUP BY", "ORDER BY", "ON CONFLICT", "DO NOTHING",
    "IF NOT EXISTS", "IF EXISTS", "OR REPLACE",
    "PRIMARY KEY", "FOREIGN KEY", "REFERENCES",
    "NOT NULL", "NO ACTION", "SET NULL",
    "IS NULL", "IS NOT NULL", "NULLS FIRST", "NULLS LAST",
    "PARTITION BY", "DO UPDATE",
    # Constraints
    "CONSTRAINT", "UNIQUE", "DEFAULT", "NULL", "CHECK",
    "CASCADE", "RESTRICT",
    # Transactions
    "BEGIN", "COMMIT", "ROLLBACK", "TRANSACTION", "SAVEPOINT",
    # Maintenance
    "GRANT", "REVOKE", "TRUNCATE", "EXPLAIN", "ANALYZE",
    "VACUUM", "REINDEX", "CLUSTER",
    # Types
    "INTEGER", "BIGINT", "SMALLINT", "TEXT", "VARCHAR", "CHAR",
    "BOOLEAN", "NUMERIC", "REAL", "FLOAT", "SERIAL", "BIGSERIAL",
    "TIMESTAMP", "TIMESTAMPTZ", "DATE", "TIME",
    "INTERVAL", "JSON", "JSONB", "UUID", "ARRAY", "BYTEA",
    "DOUBLE PRECISION",
    # Logic / values
    "TRUE", "FALSE", "CASE", "WHEN", "THEN", "ELSE", "END",
    "ASC", "DESC",
    # Window functions
    "OVER", "WINDOW", "ROWS", "RANGE",
    # Aggregate / scalar functions
    "COUNT", "SUM", "AVG", "MIN", "MAX",
    "COALESCE", "NULLIF", "CAST", "EXTRACT",
    "NOW", "CURRENT_TIMESTAMP", "CURRENT_DATE", "CURRENT_TIME",
    "GENERATE_SERIES", "UNNEST", "STRING_AGG", "ARRAY_AGG",
    "ROW_NUMBER", "RANK", "DENSE_RANK", "LAG", "LEAD",
    # PostgreSQL specific
    "COPY", "LISTEN", "NOTIFY", "LOCK", "INHERITS",
    "TABLESPACE", "OWNER", "TO", "PUBLIC",
    "MATERIALIZED", "TEMPORARY", "TEMP", "UNLOGGED",
    "CONCURRENTLY", "USING", "IMMUTABLE", "STABLE", "VOLATILE",
    "STRICT", "SECURITY", "DEFINER", "INVOKER",
    "SETOF", "COST", "ROWS", "RETURNS",
    "LANGUAGE", "FUNCTION", "TRIGGER", "PROCEDURE",
    "BEFORE", "AFTER", "INSTEAD", "OF", "FOR", "EACH", "ROW", "EXECUTE",
    "DECLARE", "CURSOR", "OPEN", "CLOSE", "FETCH", "RETURN",
    "NEXT", "RECORD", "TYPE", "DOMAIN", "ENUM",
    "GREATEST", "LEAST",
]


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

    def add_tab(self, title: str = None, content: str = "") -> EditorTab:
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
            self._tab_labels[idx].set_text(new_title)

    def get_active_tab(self) -> EditorTab | None:
        page_num = self._notebook.get_current_page()
        if 0 <= page_num < len(self._tabs):
            return self._tabs[page_num]
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
            pattern = r'\b' + re.escape(search_text) + r'\b'
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
        if hasattr(self, '_search_debounce_id') and self._search_debounce_id:
            GLib.source_remove(self._search_debounce_id)
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
                self._window.statusbar.set_message(f"Search wrapped: '{search_text}'")
            else:
                self._window.statusbar.set_message(f"Text '{search_text}' not found")

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
        if self._case_check.get_active():
            pattern = re.escape(search)
            count = text.count(search)
            new_text = text.replace(search, replace)
        else:
            pattern = re.escape(search)
            count = len(re.findall(pattern, text, re.IGNORECASE))
            new_text = re.sub(pattern, replace, text, flags=re.IGNORECASE)
        if count > 0:
            buffer.set_text(new_text)
            self._window.statusbar.set_message(f"Replaced {count} occurrences")
            if self._search_revealer.get_reveal_child():
                self._highlight_all_matches(search)
        else:
            self._window.statusbar.set_message(f"Text '{search}' not found")

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
        self._whole_word_check.connect("toggled", lambda b: self._on_search_changed(self._search_entry))
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


# ======================================================================
# Single Editor Tab
# ======================================================================

class EditorTab(Gtk.Box):
    """Single editor tab with GtkSourceView and custom Popover autocomplete."""

    # Class-level setting shared across all tabs
    _autocomplete_enabled: bool = True

    @classmethod
    def set_autocomplete_enabled(cls, enabled: bool):
        """Enable or disable autocomplete for all tabs."""
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
        """Create the popover and its listbox – bez ScrolledWindow, nech sa veľkosť prispôsobí."""
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
        """Get the current word (possibly multi-word) at cursor position.
    
        For multi-word matches, looks back up to 3 words.
        Returns (word, start_iter, end_iter).
        """
        buffer = self._view.get_buffer()
        cursor = buffer.get_iter_at_mark(buffer.get_insert())
        end = cursor.copy()
    
        # Get current word
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
    
        # Try to expand to multi-word (up to 3 words back)
        expanded_start = start.copy()
        for _ in range(3):
            # Skip whitespace backwards
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
        
            # Get previous word
            prev_word_start = expanded_start.copy()
            while not prev_word_start.starts_line():
                prev = prev_word_start.copy()
                if not prev.backward_char():
                    break
                ch = prev.get_char()
                if ch in " \t\n\r()[]{},;.=<>!+-*/%|&^~@#:;\"'`":
                    break
                prev_word_start = prev
        
            # Check if this multi-word combination exists in keywords
            candidate = buffer.get_text(prev_word_start, end, False)
            candidate_upper = candidate.upper()
        
            # Only expand if it matches at least one keyword
            if any(kw.startswith(candidate_upper) for kw in SQL_KEYWORDS):
                start = prev_word_start
                word = candidate
    
        return word, start, end

    def _on_buffer_changed(self, buffer):
        if self._completing:
            return
        if not EditorTab._autocomplete_enabled:
            self._hide_completion()
            return
        if self._popover_debounce_id:
            GLib.source_remove(self._popover_debounce_id)
        self._popover_debounce_id = GLib.timeout_add(100, self._do_update_popover, buffer)

    def _do_update_popover(self, buffer):
        """Update completion popover with matching keywords."""
        self._popover_debounce_id = 0
        word, start, end = self._get_word_at_cursor()
    
        if len(word) < 2:
            self._hide_completion()
            return False
    
        word_upper = word.upper()
    
        # Find matches - exact and starts-with
        matches = [kw for kw in SQL_KEYWORDS if kw.startswith(word_upper)]
    
        # Also include case-insensitive matches
        if not matches:
            matches = [kw for kw in SQL_KEYWORDS 
                       if kw.upper().startswith(word_upper)]
    
        if not matches:
            self._hide_completion()
            return False
    
        # Sort: exact matches first, then alphabetically
        exact = [m for m in matches if m.upper() == word_upper]
        starts = [m for m in matches if m.upper() != word_upper]
        matches = exact + sorted(starts)
    
        self._completion_matches = matches
        self._selected_index = -1
        self._populate_completion_list(matches)
        self._show_completion_at_iter(start)
        return False

    def _populate_completion_list(self, matches: list[str]):
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
        rect = self._view.get_iter_location(text_iter)
        wx, wy = self._view.buffer_to_window_coords(
            Gtk.TextWindowType.WIDGET, rect.x, rect.y
        )
        point = Gdk.Rectangle()
        point.x = wx
        point.y = wy
        point.width = max(rect.width, 4)
        point.height = rect.height
        self._completion_popover.set_pointing_to(point)
        self._completion_popover.popup()

    def _hide_completion(self):
        if self._completion_popover and self._completion_popover.is_visible():
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
        idx = row.get_index()
        if 0 <= idx < len(self._completion_matches):
            self._apply_completion(self._completion_matches[idx])

    def _select_next_in_popover(self):
        if not self._completion_matches:
            return
        self._selected_index += 1
        if self._selected_index >= len(self._completion_matches):
            self._selected_index = 0
        row = self._completion_list.get_row_at_index(self._selected_index)
        if row:
            self._completion_list.select_row(row)
            row.grab_focus()

    def _select_prev_in_popover(self):
        if not self._completion_matches:
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

    def get_selected_text(self) -> str:
        buffer = self._view.get_buffer()
        if buffer.get_has_selection():
            start, end = buffer.get_selection_bounds()
            return str(buffer.get_text(start, end, False))
        return self.get_text()
