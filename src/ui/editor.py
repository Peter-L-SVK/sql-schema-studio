# ----------------------------------------------------------------------
# SQL Schema Studio 0.9 - SQL Editor with Search & Replace (GPLv3)
# Copyright (C) 2026 Peter Leukanič
# License: GNU GPL v3+ <https://www.gnu.org/licenses/gpl-3.0.txt>
# This is free software with NO WARRANTY.
# Feel free to distribute and modify.
# ----------------------------------------------------------------------

"""SQL Editor with syntax highlighting, line numbers, and search/replace."""

from __future__ import annotations
import gi
import re

gi.require_version("Gtk", "4.0")
gi.require_version("GtkSource", "5")
from gi.repository import Gtk, GtkSource, Gdk, Pango, GLib


class SQLEditor(Gtk.Box):
    """SQL editor panel with GtkSourceView and search/replace."""

    def __init__(self, window):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self._window = window
        self._search_highlight_tag = None
        self._current_search_text = ""
        self._search_debounce_id = 0

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

        # Set up search highlight tag
        buffer = self._view.get_buffer()
        self._search_highlight_tag = buffer.create_tag(
            "search_highlight",
            background="yellow",
            background_rgba=Gdk.RGBA(red=1.0, green=1.0, blue=0.0, alpha=0.5),
        )

        # Keyboard shortcuts
        key_controller = Gtk.EventControllerKey()
        key_controller.connect("key-pressed", self._on_key_pressed)
        self._view.add_controller(key_controller)

        scroll.set_child(self._view)
        self.append(scroll)

        # Search bar (hidden by default)
        self._search_revealer = Gtk.Revealer()
        self._search_revealer.set_transition_type(Gtk.RevealerTransitionType.SLIDE_DOWN)
        self._search_revealer.set_reveal_child(False)
        self._build_search_bar()
        self.append(self._search_revealer)

        # Load saved settings
        self._load_settings()

    def _setup_sql_language(self):
        """Configure SQL syntax highlighting"""
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

        # Ctrl+F = Find
        if keyval == Gdk.KEY_f and (state & Gdk.ModifierType.CONTROL_MASK):
            self._on_find()
            return True
        
        # Ctrl+H = Find & Replace
        if keyval == Gdk.KEY_h and (state & Gdk.ModifierType.CONTROL_MASK):
            self._on_find()
            GLib.idle_add(self._replace_entry.grab_focus)
            return True
        
        # Escape = Close search
        if keyval == Gdk.KEY_Escape and self._search_revealer.get_reveal_child():
            self._search_revealer.set_reveal_child(False)
            self._clear_search_highlights()
            self._view.grab_focus()
            return True

        # F3 = Find next
        if keyval == Gdk.KEY_F3:
            if state & Gdk.ModifierType.SHIFT_MASK:
                self._on_find_prev()
            else:
                self._on_find_next()
            return True

        return False

    def _load_settings(self):
        """Apply saved editor settings."""
        from src.utils.settings import Settings

        settings = Settings()
        editor = settings.get_section("editor")

        self._view.set_tab_width(editor.get("tab_width", 4))
        self._view.set_insert_spaces_instead_of_tabs(editor.get("spaces_instead_of_tabs", True))
        self._view.set_show_line_numbers(editor.get("show_line_numbers", True))
        self._view.set_highlight_current_line(editor.get("highlight_current_line", True))

        scheme_id = editor.get("color_scheme", "classic")
        manager = GtkSource.StyleSchemeManager.get_default()
        scheme = manager.get_scheme(scheme_id)
        if scheme:
            self._view.get_buffer().set_style_scheme(scheme)

        font_str = editor.get("font", "Monospace 12")
        font_desc = Pango.FontDescription.from_string(font_str)
        css = f"""
        textview {{
            font-family: {font_desc.get_family()};
            font-size: {font_desc.get_size() // Pango.SCALE}pt;
        }}
        """
        provider = Gtk.CssProvider()
        provider.load_from_data(css.encode())
        self._view.get_style_context().add_provider(
            provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

    # --- Search & Replace ---

    def _clear_search_highlights(self):
        """Clear all search highlight tags from the buffer."""
        buffer = self._view.get_buffer()
        start = buffer.get_start_iter()
        end = buffer.get_end_iter()
        buffer.remove_tag(self._search_highlight_tag, start, end)

    def _do_highlight(self, search_text):
        """Execute actual highlighting after debounce."""
        self._search_debounce_id = 0
        self._current_search_text = search_text
        self._highlight_all_matches(search_text)
        return False  # One-shot

    def _highlight_all_matches(self, search_text: str):
        """Highlight all occurrences with size and count limits."""
        self._clear_search_highlights()
    
        if not search_text or len(search_text) > 200:
            return

        buffer = self._view.get_buffer()
        start = buffer.get_start_iter()
        end = buffer.get_end_iter()
    
        # Skip highlighting for large files (>500KB)
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
            if match_count >= 5000:  # Max 5000 highlights
                break
            iter_start = buffer.get_iter_at_offset(match.start())
            iter_end = buffer.get_iter_at_offset(match.end())
            buffer.apply_tag(self._search_highlight_tag, iter_start, iter_end)
            match_count += 1

    def _on_find(self):
        """Open search bar."""
        self._search_revealer.set_reveal_child(True)
        self._search_entry.grab_focus()
        self._search_entry.select_region(0, -1)
        
        # If there's selected text in editor, use it as search term
        buffer = self._view.get_buffer()
        if buffer.get_has_selection():
            start, end = buffer.get_selection_bounds()
            selected = buffer.get_text(start, end, False)
            if selected and len(selected) < 100:
                self._search_entry.set_text(selected)
                self._search_entry.select_region(0, -1)
                self._highlight_all_matches(selected)

    def _on_find_next(self):
        """Find next occurrence."""
        search_text = self._search_entry.get_text()
        if not search_text:
            return
        self._search_text(search_text, forward=True)

    def _on_find_prev(self):
        """Find previous occurrence."""
        search_text = self._search_entry.get_text()
        if not search_text:
            return
        self._search_text(search_text, forward=False)

    def _on_search_changed(self, entry):
        """Highlight matches with debounce (300ms delay)."""
        if self._search_debounce_id:
            GLib.source_remove(self._search_debounce_id)
        self._search_debounce_id = GLib.timeout_add(300, self._do_highlight, entry.get_text())


    def _get_search_flags(self):
        """Get search flags for Gtk.TextSearchFlags."""
        flags = Gtk.TextSearchFlags.VISIBLE_ONLY | Gtk.TextSearchFlags.TEXT_ONLY
        if not self._case_check.get_active():
            flags |= Gtk.TextSearchFlags.CASE_INSENSITIVE
        return flags

    def _search_text(self, search_text: str, forward: bool = True):
        """Search for text in the buffer and select it."""
        if not search_text:
            return

        buffer = self._view.get_buffer()
        
        # Get current cursor position
        cursor_iter = buffer.get_iter_at_mark(buffer.get_insert())
        
        # For finding next when there's a selection, move past the current match
        if forward and buffer.get_has_selection():
            cursor_iter = buffer.get_iter_at_mark(buffer.get_selection_bound())
        
        # Search using GTK's built-in search (which is simpler)
        flags = self._get_search_flags()
        
        if forward:
            found = cursor_iter.forward_search(search_text, flags, None)
        else:
            found = cursor_iter.backward_search(search_text, flags, None)
        
        if found:
            match_start, match_end = found
            buffer.select_range(match_start, match_end)
            self._view.scroll_to_iter(match_start, 0.0, True, 0.0, 0.0)
        else:
            # Wrap around
            if forward:
                wrap_iter = buffer.get_start_iter()
                found = wrap_iter.forward_search(search_text, flags, None)
            else:
                wrap_iter = buffer.get_end_iter()
                found = wrap_iter.backward_search(search_text, flags, None)
            
            if found:
                match_start, match_end = found
                buffer.select_range(match_start, match_end)
                self._view.scroll_to_iter(match_start, 0.0, True, 0.0, 0.0)
                self._window.statusbar.set_message(f"Search wrapped: '{search_text}'")
            else:
                self._window.statusbar.set_message(f"Text '{search_text}' not found")

    def _on_replace(self):
        """Replace current selection with replacement text."""
        buffer = self._view.get_buffer()
        if buffer.get_has_selection():
            # Get the selected text
            start, end = buffer.get_selection_bounds()
            selected = buffer.get_text(start, end, False)
            search_text = self._search_entry.get_text()
            
            # Check if selected text matches search text
            if self._case_check.get_active():
                matches = selected == search_text
            else:
                matches = selected.lower() == search_text.lower()
            
            if matches:
                buffer.delete_selection(True, True)
                buffer.insert_at_cursor(self._replace_entry.get_text())
                # Re-highlight all matches
                self._highlight_all_matches(search_text)
                # Find next occurrence
                self._search_text(search_text, forward=True)

    def _on_replace_all(self):
        """Replace all occurrences."""
        buffer = self._view.get_buffer()
        search = self._search_entry.get_text()
        replace = self._replace_entry.get_text()

        if not search:
            return

        # Get all text
        start = buffer.get_start_iter()
        end = buffer.get_end_iter()
        text = buffer.get_text(start, end, False)
        
        # Build regex for replacement
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
            # Re-highlight if search bar is open
            if self._search_revealer.get_reveal_child():
                self._highlight_all_matches(search)
        else:
            self._window.statusbar.set_message(f"Text '{search}' not found")

    def _build_search_bar(self):
        """Build search and replace bar."""
        search_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        search_box.set_margin_start(6)
        search_box.set_margin_end(6)
        search_box.set_margin_top(4)
        search_box.set_margin_bottom(4)
        search_box.add_css_class("toolbar")

        # Search label
        search_label = Gtk.Label(label="Find:")
        search_box.append(search_label)

        # Search entry
        self._search_entry = Gtk.Entry()
        self._search_entry.set_placeholder_text("Search...")
        self._search_entry.set_hexpand(True)
        self._search_entry.connect("changed", self._on_search_changed)
        self._search_entry.connect("activate", lambda e: self._on_find_next())
        search_box.append(self._search_entry)

        # Navigation buttons
        btn_prev = Gtk.Button(label="◀")
        btn_prev.set_tooltip_text("Previous match (Shift+F3)")
        btn_prev.connect("clicked", lambda b: self._on_find_prev())
        search_box.append(btn_prev)

        btn_next = Gtk.Button(label="▶")
        btn_next.set_tooltip_text("Next match (F3 or Enter)")
        btn_next.connect("clicked", lambda b: self._on_find_next())
        search_box.append(btn_next)

        # Separator
        sep = Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)
        search_box.append(sep)

        # Replace label
        replace_label = Gtk.Label(label="Replace:")
        search_box.append(replace_label)

        # Replace entry
        self._replace_entry = Gtk.Entry()
        self._replace_entry.set_placeholder_text("Replace with...")
        self._replace_entry.set_hexpand(True)
        self._replace_entry.connect("activate", lambda e: self._on_replace())
        search_box.append(self._replace_entry)

        # Replace buttons
        btn_replace = Gtk.Button(label="Replace")
        btn_replace.set_tooltip_text("Replace current match")
        btn_replace.connect("clicked", lambda b: self._on_replace())
        search_box.append(btn_replace)

        btn_replace_all = Gtk.Button(label="Replace All")
        btn_replace_all.set_tooltip_text("Replace all occurrences")
        btn_replace_all.connect("clicked", lambda b: self._on_replace_all())
        search_box.append(btn_replace_all)

        # Separator
        sep2 = Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)
        search_box.append(sep2)

        # Case sensitive toggle (CASE_INSENSITIVE flag is the default)
        self._case_check = Gtk.CheckButton(label="Aa")
        self._case_check.set_tooltip_text("Case sensitive (unchecked = case insensitive)")
        self._case_check.connect("toggled", lambda b: self._on_search_changed(self._search_entry))
        search_box.append(self._case_check)

        # Whole word toggle - implemented via regex \b boundaries
        self._whole_word_check = Gtk.CheckButton(label="ab|")
        self._whole_word_check.set_tooltip_text("Match whole word only")
        self._whole_word_check.connect("toggled", lambda b: self._on_search_changed(self._search_entry))
        search_box.append(self._whole_word_check)

        # Close button
        btn_close = Gtk.Button(label="✕")
        btn_close.set_tooltip_text("Close search bar (Escape)")
        btn_close.connect("clicked", lambda b: self._search_revealer.set_reveal_child(False))
        search_box.append(btn_close)

        self._search_revealer.set_child(search_box)
