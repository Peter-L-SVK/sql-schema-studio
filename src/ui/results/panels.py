# ----------------------------------------------------------------------
# SQL Schema Studio 0.9.5 - Results Panel (GPLv3)
# Copyright (C) 2026 Peter Leukanič
# License: GNU GPL v3+ <https://www.gnu.org/licenses/gpl-3.0.txt>
# This is free software with NO WARRANTY.
# Feel free to distribute and modify.
# ----------------------------------------------------------------------

"""Results viewer panel with Results, Log, and Terminal tabs."""

from __future__ import annotations

import logging

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Vte", "3.91")
from gi.repository import Gtk, Vte, GLib

from src.config import RESULTS_ROW_LIMIT
from src.ui.results.terminal_themes import TERMINAL_THEMES, get_terminal_theme_names


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
        except Exception as e:
            # Write to stderr so we don't lose the failure silently
            import sys
            print(f"LogHandler.emit failed: {e}", file=sys.stderr)

class ResultsPanel(Gtk.Box):
    """Query results display panel with Results, Log, and Terminal tabs."""

    TERMINAL_THEMES = TERMINAL_THEMES

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
            f"[{datetime.now().strftime('%H:%M:%S')}] Session started\n" f"[{'='*40}]\n"
        )
        log_scroll.set_child(self._log_view)
        log_box.append(log_scroll)

        self._notebook.append_page(log_box, Gtk.Label(label="Log"))

        # --- Tab 3: Terminal ---
        self._terminal_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self._terminal = None
        self._notebook.append_page(self._terminal_box, Gtk.Label(label="Terminal"))

        self._notebook.connect("switch-page", self._on_notebook_switch)

        # Attach log handler to the application logger (not root).
        # The sql_schema_studio logger is already set to DEBUG in src/__init__.py,
        # so INFO/DEBUG messages from our own modules land in the Log tab.
        # Attaching to root would also capture noise from third-party libraries
        # (google.protobuf, paramiko, ...), which we don't want.
        self._log_handler = LogHandler(self)
        self._log_handler.setLevel(logging.DEBUG)

        app_logger = logging.getLogger("sql_schema_studio")
        app_logger.setLevel(logging.DEBUG)
        app_logger.addHandler(self._log_handler)

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
        return get_terminal_theme_names()

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
        """Display query results as a fixed-width table in the Results tab.

        Every cell is padded to the column's max content width (capped at
        40 chars). The `│` separators therefore line up perfectly under a
        monospace font, matching the row above and below.
        """
        self._notebook.set_current_page(0)

        # --- 1. Compute column widths (no padding included) ---
        #    Cap at 40 chars so a single huge value doesn't blow the layout.
        MAX_CELL = 40
        col_widths: list[int] = []
        for i, col in enumerate(columns):
            width = len(str(col))
            for row in rows[:row_limit]:
                val = str(row[i]) if row[i] is not None else "NULL"
                width = max(width, min(len(val), MAX_CELL))
            col_widths.append(width)

        # --- 2. Build a single row with consistent padding ---
        def make_row(values) -> str:
            cells = []
            for i, val in enumerate(values):
                val_str = str(val) if val is not None else "NULL"
                if len(val_str) > MAX_CELL:
                    val_str = val_str[: MAX_CELL - 3] + "..."
                # 1 space of padding on each side, plus the content left-justified
                cells.append(f" {val_str:<{col_widths[i]}} ")
            return "│" + "│".join(cells) + "│"

        # --- 3. Build a separator row that matches column widths ---
        def make_sep(left: str, mid: str, right: str) -> str:
            parts = ["─" * (w + 2) for w in col_widths]  # +2 for padding
            return left + mid.join(parts) + right

        # --- 4. Assemble the table ---
        lines: list[str] = []
        lines.append(make_sep("┌", "┬", "┐"))
        lines.append(make_row(columns))
        lines.append(make_sep("├", "┼", "┤"))

        for row in rows[:row_limit]:
            lines.append(make_row(row))

        lines.append(make_sep("└", "┴", "┘"))

        # --- 5. Footer ---
        lines.append("")
        lines.append(f"{len(rows)} row(s) returned")
        if len(rows) > row_limit:
            lines.append(f"(showing first {row_limit})")
        lines.append(f"Time: {elapsed:.3f}s")

        text = "\n".join(lines)

        buffer = self._result_view.get_buffer()
        buffer.set_text(text)

    def _log(self, message: str):
        """Append message to Log tab with auto-scroll.

        Called from LogHandler.emit via GLib.idle_add, so this always runs
        on the GTK main thread.
        """
        try:
            buffer = self._log_view.get_buffer()
            end = buffer.get_end_iter()
            buffer.insert(end, f"{message}\n")
            self._log_view.scroll_to_iter(end, 0.0, False, 0.0, 0.0)
        except Exception as e:
            # Never let a logging failure crash the app
            print(f"LogHandler write failed: {e}", file=sys.stderr)
        return False  # one-shot idle callback

    # =====================================================================
    # Table structure formatting (used by browser when showing columns)
    # =====================================================================

    @staticmethod
    def format_data_type(
        data_type: str,
        length: int | None = None,
        precision: int | None = None,
        scale: int | None = None,
    ) -> str:
        """Return a compact, PostgreSQL-style type string.

        Examples:
            integer, NULL, NULL        → "integer"
            character varying, 50      → "varchar(50)"
            numeric, NULL, 10, 2       → "numeric(10,2)"
            timestamp without time zone→ "timestamp"
        """
        # Shorten common verbose PostgreSQL type names
        short = {
            "character varying": "varchar",
            "character": "char",
            "timestamp without time zone": "timestamp",
            "timestamp with time zone": "timestamptz",
            "time without time zone": "time",
            "time with time zone": "timetz",
            "double precision": "double",
            "boolean": "boolean",
            "integer": "integer",
            "bigint": "bigint",
            "smallint": "smallint",
        }
        base = short.get(data_type, data_type)

        if length is not None:
            return f"{base}({length})"
        if precision is not None:
            if scale:
                return f"{base}({precision},{scale})"
            return f"{base}({precision})"
        return base
