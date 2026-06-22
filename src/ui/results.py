# ----------------------------------------------------------------------
# SQL Schema Studio 0.9 - Results Panel (GPLv3)
# Copyright (C) 2026 Peter Leukanič
# License: GNU GPL v3+ <https://www.gnu.org/licenses/gpl-3.0.txt>
# This is free software with NO WARRANTY.
# Feel free to distribute and modify.
# ----------------------------------------------------------------------

"""Results viewer panel with tabs and terminal support."""

from __future__ import annotations

import logging
import os

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Vte", "3.91")
from gi.repository import Gtk, Vte, GLib, GtkSource

from src.config import RESULTS_ROW_LIMIT


class LogHandler(logging.Handler):
    """Custom logging handler that sends logs to the ResultsPanel Log tab."""

    def __init__(self, panel: "ResultsPanel"):
        super().__init__()
        self._panel = panel
        self.setFormatter(
            logging.Formatter(
                "%(asctime)s [%(levelname)s] %(name)s: %(message)s", datefmt="%H:%M:%S"
            )
        )

    def emit(self, record):
        """Emit a log record to the Log tab."""
        try:
            msg = self.format(record)
            GLib.idle_add(self._panel._log, msg)
        except Exception:
            pass


class ResultsPanel(Gtk.Box):
    """Query results display panel with Results, Log, and Terminal tabs."""

    # Terminal color themes
    TERMINAL_THEMES = {
        "dark": {
            "name": "Dark",
            "fg": "#D3D7CF",
            "bg": "#1E1E1E",
            "palette": [
                "#000000", "#CC0000", "#4E9A06", "#C4A000",
                "#3465A4", "#75507B", "#06989A", "#D3D7CF",
                "#555753", "#EF2929", "#8AE234", "#FCE94F",
                "#729FCF", "#AD7FA8", "#34E2E2", "#EEEEEC"
            ]
        },
        "light": {
            "name": "Light",
            "fg": "#000000",
            "bg": "#FFFFFF",
            "palette": [
                "#000000", "#CC0000", "#4E9A06", "#C4A000",
                "#3465A4", "#75507B", "#06989A", "#D3D7CF",
                "#555753", "#EF2929", "#8AE234", "#FCE94F",
                "#729FCF", "#AD7FA8", "#34E2E2", "#EEEEEC"
            ]
        },
        "tango-dark": {
            "name": "Tango Dark",
            "fg": "#EEEEEC",
            "bg": "#2E3436",
            "palette": [
                "#2E3436", "#CC0000", "#4E9A06", "#C4A000",
                "#3465A4", "#75507B", "#06989A", "#D3D7CF",
                "#555753", "#EF2929", "#8AE234", "#FCE94F",
                "#729FCF", "#AD7FA8", "#34E2E2", "#EEEEEC"
            ]
        },
        "tango-light": {
            "name": "Tango Light",
            "fg": "#2E3436",
            "bg": "#EEEEEC",
            "palette": [
                "#2E3436", "#CC0000", "#4E9A06", "#C4A000",
                "#3465A4", "#75507B", "#06989A", "#D3D7CF",
                "#555753", "#EF2929", "#8AE234", "#FCE94F",
                "#729FCF", "#AD7FA8", "#34E2E2", "#EEEEEC"
            ]
        },
        "solarized-dark": {
            "name": "Solarized Dark",
            "fg": "#839496",
            "bg": "#002B36",
            "palette": [
                "#073642", "#DC322F", "#859900", "#B58900",
                "#268BD2", "#D33682", "#2AA198", "#EEE8D5",
                "#002B36", "#CB4B16", "#586E75", "#657B83",
                "#839496", "#6C71C4", "#93A1A1", "#FDF6E3"
            ]
        },
        "solarized-light": {
            "name": "Solarized Light",
            "fg": "#657B83",
            "bg": "#FDF6E3",
            "palette": [
                "#073642", "#DC322F", "#859900", "#B58900",
                "#268BD2", "#D33682", "#2AA198", "#EEE8D5",
                "#002B36", "#CB4B16", "#586E75", "#657B83",
                "#839496", "#6C71C4", "#93A1A1", "#FDF6E3"
            ]
        },
        "monokai": {
            "name": "Monokai",
            "fg": "#F8F8F2",
            "bg": "#272822",
            "palette": [
                "#272822", "#F92672", "#A6E22E", "#FD971F",
                "#66D9EF", "#AE81FF", "#A1EFE4", "#F8F8F2",
                "#75715E", "#F92672", "#A6E22E", "#FD971F",
                "#66D9EF", "#AE81FF", "#A1EFE4", "#F9F8F5"
            ]
        },
        "nord": {
            "name": "Nord",
            "fg": "#D8DEE9",
            "bg": "#2E3440",
            "palette": [
                "#2E3440", "#BF616A", "#A3BE8C", "#EBCB8B",
                "#81A1C1", "#B48EAD", "#88C0D0", "#E5E9F0",
                "#4C566A", "#BF616A", "#A3BE8C", "#EBCB8B",
                "#81A1C1", "#B48EAD", "#8FBCBB", "#ECEFF4"
            ]
        }
    }

    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)

        # Tab bar
        self._tab_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        self._tab_bar.add_css_class("tab-bar-container")

        self._notebook = Gtk.Notebook()
        self._notebook.set_scrollable(True)
        self._notebook.set_hexpand(True)
        self._notebook.set_vexpand(True)
        self._tab_bar.append(self._notebook)

        self.append(self._tab_bar)

        # --- Tab 1: Results ---
        results_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        results_scroll = Gtk.ScrolledWindow()
        results_scroll.set_vexpand(True)

        self._result_view = Gtk.TextView()
        self._result_view.add_css_class("results-view")
        self._result_view.set_monospace(True)
        self._result_view.set_editable(False)
        results_scroll.set_child(self._result_view)
        results_box.append(results_scroll)

        self._notebook.append_page(results_box, Gtk.Label(label="Results"))

        # --- Tab 2: Log ---
        log_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        log_scroll = Gtk.ScrolledWindow()
        log_scroll.set_vexpand(True)

        self._log_view = Gtk.TextView()
        self._log_view.add_css_class("results-view")
        self._log_view.set_monospace(True)
        self._log_view.set_editable(False)

        from datetime import datetime

        log_buffer = self._log_view.get_buffer()
        log_buffer.set_text(
            f"[{datetime.now().strftime('%H:%M:%S')}] Session started\n"
            f"[{'='*40}]\n"
        )
        log_scroll.set_child(self._log_view)
        log_box.append(log_scroll)

        self._notebook.append_page(log_box, Gtk.Label(label="Log"))

        # --- Tab 3: Terminal ---
        self._terminal_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self._terminal = None
        self._notebook.append_page(self._terminal_box, Gtk.Label(label="Terminal"))

        self._notebook.connect("switch-page", self._on_notebook_switch)

        # Attach log handler to root logger
        self._log_handler = LogHandler(self)
        logging.getLogger().addHandler(self._log_handler)

        # Store current theme
        self._current_theme = "dark"

    def _on_notebook_switch(self, notebook, page, page_num):
        """Initialize terminal when user switches to its tab."""
        if page_num == 2 and self._terminal is None:
            self._init_terminal()

    def apply_terminal_scheme(self, theme_id: str = "dark"):
        """Apply a terminal color theme."""
        if self._terminal is None:
            # Store theme for later initialization
            self._current_theme = theme_id
            return

        from gi.repository import Gdk

        # Get the theme from TERMINAL_THEMES only
        theme = self.TERMINAL_THEMES.get(theme_id)
        if theme is None:
            theme = self.TERMINAL_THEMES["dark"]

        self._current_theme = theme_id

        fg = Gdk.RGBA()
        fg.parse(theme["fg"])

        bg = Gdk.RGBA()
        bg.parse(theme["bg"])

        palette = []
        for color_str in theme["palette"]:
            color = Gdk.RGBA()
            color.parse(color_str)
            palette.append(color)

        self._terminal.set_colors(fg, bg, palette)

    def _init_terminal(self):
        """Initialize the VTE terminal widget."""
        try:
            self._terminal = Vte.Terminal()
            self._terminal.set_vexpand(True)
            self._terminal.set_hexpand(True)
            self._terminal.set_scrollback_lines(10000)
            self._terminal.set_mouse_autohide(True)

            # Set monospace font using Pango
            from gi.repository import Pango

            font_desc = Pango.FontDescription.from_string("Monospace 10")
            self._terminal.set_font(font_desc)

            # Launch user's default shell
            shell = GLib.getenv("SHELL") or "/bin/bash"

            def on_spawn_finished(terminal, pid, error, *args):
                if error:
                    print(f"Terminal failed to start: {error}")

            self._terminal.spawn_async(
                Vte.PtyFlags.DEFAULT,  # pty_flags
                None,  # working_directory
                [shell],  # argv
                None,  # envv
                GLib.SpawnFlags.DEFAULT,  # spawn_flags
                None,  # child_setup
                None,  # child_setup_data
                -1,  # timeout
                None,  # cancellable
                on_spawn_finished,  # callback
                None,  # user_data
            )

            self._terminal_box.append(self._terminal)

            # Apply the current theme
            self.apply_terminal_scheme(self._current_theme)

        except Exception as e:
            label = Gtk.Label(label=f"Terminal not available: {e}")
            label.set_wrap(True)
            self._terminal_box.append(label)

    @classmethod
    def get_theme_names(cls):
        """Get list of (theme_id, display_name) tuples for all themes."""
        return [(theme_id, theme["name"]) for theme_id, theme in cls.TERMINAL_THEMES.items()]

    # =====================================================================
    # Public API
    # =====================================================================

    def show_text(self, text: str):
        """Display plain text in Results tab."""
        self._notebook.set_current_page(0)
        buffer = self._result_view.get_buffer()
        buffer.set_text(text)

    def show_error(self, message: str, elapsed: float):
        """Display error in Results tab."""
        self._notebook.set_current_page(0)
        buffer = self._result_view.get_buffer()
        buffer.set_text(f"ERROR: {message}\n\nTime: {elapsed:.3f}s")

    def show_query_result(self, columns, rows, elapsed, row_limit=RESULTS_ROW_LIMIT):
        """Display query results as formatted table in Results tab."""
        self._notebook.set_current_page(0)

        col_widths = []
        for i, col in enumerate(columns):
            max_width = len(str(col))
            for row in rows[:row_limit]:
                val = str(row[i]) if row[i] is not None else "NULL"
                max_width = max(max_width, min(len(val), 40))
            col_widths.append(max_width + 2)

        text = self._build_separator("┌", "┬", "┐", col_widths, "─")

        text += "│"
        for i, col in enumerate(columns):
            text += f" {col:<{col_widths[i]}} │"
        text += "\n"

        text += self._build_separator("├", "┼", "┤", col_widths, "─")

        for row in rows[:row_limit]:
            text += "│"
            for i, val in enumerate(row):
                val_str = str(val) if val is not None else "NULL"
                if len(val_str) > 40:
                    val_str = val_str[:37] + "..."
                text += f" {val_str:<{col_widths[i]}} │"
            text += "\n"

        text += self._build_separator("└", "┴", "┘", col_widths, "─")

        text += f"\n{len(rows)} row(s) returned"
        if len(rows) > row_limit:
            text += f" (showing first {row_limit})"
        text += f"\nTime: {elapsed:.3f}s"

        buffer = self._result_view.get_buffer()
        buffer.set_text(text)

    def _log(self, message: str):
        """Append message to Log tab with auto-scroll."""
        buffer = self._log_view.get_buffer()
        end = buffer.get_end_iter()
        buffer.insert(end, f"{message}\n")
        self._log_view.scroll_to_iter(end, 0.0, False, 0.0, 0.0)

    def _build_separator(self, left: str, mid: str, right: str, widths: list, char: str) -> str:
        """Build a table separator line."""
        parts = [char * (w + 2) for w in widths]
        return left + mid.join(parts) + right + "\n"

    @property
    def terminal(self):
        """Get the terminal widget, or None if not initialized."""
        return self._terminal
