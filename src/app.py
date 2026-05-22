# ----------------------------------------------------------------------
# SQL Schema Studio - Application (GPLv3)
# Copyright (C) 2026 Peter Leukanič
# License: GNU GPL v3+ <https://www.gnu.org/licenses/gpl-3.0.txt>
# This is free software with NO WARRANTY.
# Feel free to distribute and modify.
# ----------------------------------------------------------------------

"""Gtk.Application subclass — lifecycle management"""

from __future__ import annotations

import logging

logging.getLogger("psycopg").setLevel(logging.WARNING)
logging.getLogger("psycopg.pool").setLevel(logging.ERROR)

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("GtkSource", "5")
from gi.repository import Gtk, Gio

from src.ui.window import MainWindow
from src.core.db_connector import DatabaseConnector
from src.actions import ActionHandler


class Application(Gtk.Application):
    """Main application class"""

    def __init__(self):
        super().__init__(
            application_id="com.sqlschemastudio.app", flags=Gio.ApplicationFlags.FLAGS_NONE
        )
        self.db_connector = DatabaseConnector()
        self._window = None
        self._actions = None

    def do_startup(self):
        Gtk.Application.do_startup(self)
        self._actions = ActionHandler(self, lambda: self._window)
        self._actions.register_all()

    def do_activate(self):
        if not self._window:
            self._window = MainWindow(application=self, db_connector=self.db_connector)
        self._window.present()

    def do_shutdown(self):
        """Clean up before exit"""
        if self.db_connector._active_profile:
            self.db_connector.disconnect()
        Gtk.Application.do_shutdown(self)
