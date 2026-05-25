# ----------------------------------------------------------------------
# SQL Schema Studio 0.2 - Results Panel (GPLv3)
# Copyright (C) 2026 Peter Leukanič
# License: GNU GPL v3+ <https://www.gnu.org/licenses/gpl-3.0.txt>
# This is free software with NO WARRANTY.
# Feel free to distribute and modify.
# ----------------------------------------------------------------------

"""Results viewer panel"""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

from src.config import RESULTS_ROW_LIMIT


class ResultsPanel(Gtk.Box):
    """Query results display panel"""

    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)

        # Header
        header = Gtk.Label(label="Results")
        header.add_css_class("panel-header")
        header.set_halign(Gtk.Align.START)
        self.append(header)

        # Scrolled text view
        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)

        self._view = Gtk.TextView()
        self._view.add_css_class("results-view")
        self._view.set_monospace(True)
        self._view.set_editable(False)

        scroll.set_child(self._view)
        self.append(scroll)

    def show_text(self, text: str):
        """Display plain text"""
        buffer = self._view.get_buffer()
        buffer.set_text(text)

    def show_error(self, message: str, elapsed: float):
        """Display error message"""
        buffer = self._view.get_buffer()
        buffer.set_text(f"ERROR: {message}\n\nTime: {elapsed:.3f}s")

    def show_query_result(self, columns, rows, elapsed, row_limit=RESULTS_ROW_LIMIT):
        """Display query results as formatted table"""
        # Calculate column widths
        col_widths = []
        for i, col in enumerate(columns):
            max_width = len(str(col))
            for row in rows[:row_limit]:
                val = str(row[i]) if row[i] is not None else "NULL"
                max_width = max(max_width, min(len(val), 40))
            col_widths.append(max_width + 2)

        # Build table
        text = self._build_separator("┌", "┬", "┐", col_widths, "─")

        # Header
        text += "│"
        for i, col in enumerate(columns):
            text += f" {col:<{col_widths[i]}} │"
        text += "\n"

        text += self._build_separator("├", "┼", "┤", col_widths, "─")

        # Rows
        for row in rows[:row_limit]:
            text += "│"
            for i, val in enumerate(row):
                val_str = str(val) if val is not None else "NULL"
                if len(val_str) > 40:
                    val_str = val_str[:37] + "..."
                text += f" {val_str:<{col_widths[i]}} │"
            text += "\n"

        text += self._build_separator("└", "┴", "┘", col_widths, "─")

        # Summary
        text += f"\n{len(rows)} row(s) returned"
        if len(rows) > row_limit:
            text += f" (showing first {row_limit})"
        text += f"\nTime: {elapsed:.3f}s"

        buffer = self._view.get_buffer()
        buffer.set_text(text)

    def _build_separator(self, left: str, mid: str, right: str, widths: list, char: str) -> str:
        """Build a table separator line"""
        parts = [char * (w + 2) for w in widths]
        return left + mid.join(parts) + right + "\n"
