# ----------------------------------------------------------------------
# SQL Schema Studio 0.2 - Toolbar (GPLv3)
# Copyright (C) 2026 Peter Leukanič
# License: GNU GPL v3+ <https://www.gnu.org/licenses/gpl-3.0.txt>
# This is free software with NO WARRANTY.
# Feel free to distribute and modify.
# ----------------------------------------------------------------------

"""Application toolbar"""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

from src.utils.logging import get_logger

logger = get_logger(__name__)


class Toolbar(Gtk.Box):
    """Main toolbar with common actions"""

    def __init__(self, window):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        self.add_css_class("toolbar")
        self._window = window

        # Connect button
        btn_connect = Gtk.Button(label="Connect")
        btn_connect.set_tooltip_text("New database connection")
        btn_connect.connect("clicked", lambda b: window._on_connect_clicked())
        self.append(btn_connect)

        # Disconnect button
        btn_disconnect = Gtk.Button(label="Disconnect")
        btn_disconnect.set_tooltip_text("Close connection")
        btn_disconnect.connect("clicked", lambda b: window._on_disconnect_clicked())
        self.append(btn_disconnect)

        self._add_separator()

        # Run button
        self._btn_run = Gtk.Button(label="Run")
        self._btn_run.set_tooltip_text("Execute query (F5)")
        self._btn_run.add_css_class("suggested-action")
        self._btn_run.connect("clicked", lambda b: window._on_run_clicked())
        self.append(self._btn_run)

        # Stop button
        btn_stop = Gtk.Button(label="Stop")
        btn_stop.set_tooltip_text("Cancel running query")
        btn_stop.add_css_class("destructive-action")
        btn_stop.connect("clicked", lambda b: window._on_stop_clicked())
        self.append(btn_stop)

        self._add_separator()

        # Designer button
        btn_designer = Gtk.Button(label="Designer")
        btn_designer.set_tooltip_text("Open schema designer")
        btn_designer.connect(
            "clicked", lambda b: logger.info("Schema designer clicked (not implemented)")
        )
        self.append(btn_designer)

        # AI Tools button
        btn_ai = Gtk.Button(label="AI Tools")
        btn_ai.set_tooltip_text("AI-powered analysis tools")
        btn_ai.connect("clicked", lambda b: logger.info("AI tools clicked (not implemented)"))
        self.append(btn_ai)

        # Hooks button
        btn_hooks = Gtk.Button(label="Hooks")
        btn_hooks.set_tooltip_text("Manage hooks and plugins")
        btn_hooks.connect(
            "clicked", lambda b: logger.info("Hook manager clicked (not implemented)")
        )
        self.append(btn_hooks)

        # Spacer
        spacer = Gtk.Box()
        spacer.set_hexpand(True)
        self.append(spacer)

        # Connection status
        self._status_label = Gtk.Label(label="● Disconnected")
        self._status_label.add_css_class("disconnected")
        self.append(self._status_label)

    def _add_separator(self):
        sep = Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)
        self.append(sep)

    def set_run_sensitive(self, sensitive):
        self._btn_run.set_sensitive(sensitive)

    def set_status(self, connected, text=""):
        self._status_label.remove_css_class("connected")
        self._status_label.remove_css_class("disconnected")
        if connected:
            self._status_label.add_css_class("connected")
            self._status_label.set_label(f"● {text}" if text else "● Connected")
        else:
            self._status_label.add_css_class("disconnected")
            self._status_label.set_label("● Disconnected")
