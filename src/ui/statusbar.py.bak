# ----------------------------------------------------------------------
# SQL Schema Studio 0.9 - Status Bar (GPLv3)
# Copyright (C) 2026 Peter Leukanič
# License: GNU GPL v3+ <https://www.gnu.org/licenses/gpl-3.0.txt>
# This is free software with NO WARRANTY.
# Feel free to distribute and modify.
# ----------------------------------------------------------------------

"""Status bar widget"""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk


class StatusBar(Gtk.Box):
    """Bottom status bar with connection info and query stats"""

    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        self.add_css_class("status-bar")

        self._connection_label = Gtk.Label(label="No database connected")
        self.append(self._connection_label)

        spacer = Gtk.Box()
        spacer.set_hexpand(True)
        self.append(spacer)

        self._rows_label = Gtk.Label(label="")
        self.append(self._rows_label)

        sep = Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)
        self.append(sep)

        self._time_label = Gtk.Label(label="")
        self.append(self._time_label)

        # Remember the last real connection message so we can restore it
        self._last_connection: str = "No database connected"

    def set_connection(self, text: str):
        self._last_connection = text
        self._connection_label.set_label(text)

    def set_query_stats(self, rows: int, elapsed: float):
        # Restore the connection message (previously stuck on "Running...")
        self._connection_label.set_label(self._last_connection)
        self._rows_label.set_label(f"{rows} rows")
        self._time_label.set_label(f"{elapsed:.3f}s")

    def set_message(self, text: str):
        self._connection_label.set_label(text)
        self._rows_label.set_label("")
        self._time_label.set_label("")
