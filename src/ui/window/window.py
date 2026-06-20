# ----------------------------------------------------------------------
# SQL Schema Studio 0.9 - Main Application Window (GPLv3)
# Copyright (C) 2026 Peter Leukanič
# License: GNU GPL v3+ <https://www.gnu.org/licenses/gpl-3.0.txt>
# This is free software with NO WARRANTY.
# Feel free to distribute and modify.
# ----------------------------------------------------------------------

"""Main application window — layout and core functionality."""

from __future__ import annotations

import os
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("GtkSource", "5")
from gi.repository import GLib, Gtk

from src.config import DEFAULT_WINDOW_WIDTH, DEFAULT_WINDOW_HEIGHT
from src.core.query_history import QueryHistory
from src.ui.menubar import build_menubar
from src.ui.toolbar import Toolbar
from src.ui.editor import EditorTabs
from src.ui.results import ResultsPanel
from src.ui.browser import DatabaseBrowser
from src.ui.statusbar import StatusBar
from src.utils.logging import get_logger
from src.ui.window.actions import WindowActionsMixin
from src.ui.window.dialogs import WindowDialogsMixin

logger = get_logger(__name__)


class MainWindow(WindowActionsMixin, WindowDialogsMixin, Gtk.ApplicationWindow):
    """SQL Schema Studio main window"""

    def __init__(self, application, db_connector, **kwargs):
        super().__init__(application=application, **kwargs)

        self.db_connector = db_connector
        self.set_title("SQL Schema Studio")
        self.set_default_size(DEFAULT_WINDOW_WIDTH, DEFAULT_WINDOW_HEIGHT)

        self.connect("close-request", self._on_close_request)

        self.menubar = build_menubar()
        self.toolbar = Toolbar(self)
        self.browser = DatabaseBrowser(self)
        self.editor = EditorTabs(self)
        self.results = ResultsPanel()
        self.statusbar = StatusBar()
        self._query_history = QueryHistory()
        self._current_file = None
        self._last_result = None

        self._build_layout()
        self._load_css()
        self._restore_window_state()

    def _build_layout(self):
        """Assemble the window layout"""
        main_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        main_vbox.append(self.menubar)
        main_vbox.append(self.toolbar)

        self._hpaned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        self._hpaned.set_wide_handle(True)
        self._hpaned.set_start_child(self.browser)

        right_vpaned = Gtk.Paned(orientation=Gtk.Orientation.VERTICAL)
        right_vpaned.set_wide_handle(True)
        right_vpaned.set_start_child(self.editor)
        right_vpaned.set_end_child(self.results)

        self._hpaned.set_end_child(right_vpaned)
        main_vbox.append(self._hpaned)

        main_vbox.append(self.statusbar)
        self.set_child(main_vbox)

    def _load_css(self):
        """Load CSS styling"""
        css_provider = Gtk.CssProvider()
        css_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "resources",
            "ui",
            "style.css",
        )
        css_provider.load_from_path(css_path)
        Gtk.StyleContext.add_provider_for_display(
            self.get_display(), css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

    def _restore_window_state(self):
        """Restore window size and pane positions from settings."""
        from src.utils.settings import Settings

        settings = Settings()
        window = settings.get_section("window")
        width = window.get("width", 1200)
        height = window.get("height", 800)
        browser_width = window.get("browser_width", 220)

        def do_restore():
            self.set_default_size(width, height)
            if hasattr(self, "_hpaned"):
                self._hpaned.set_position(browser_width)
            return False

        GLib.idle_add(do_restore)

    def _save_window_state(self):
        """Save window size and pane positions to settings."""
        from src.utils.settings import Settings

        settings = Settings()
        width = self.get_allocated_width()
        height = self.get_allocated_height()
        if width > 0 and height > 0:
            settings.set("window", "width", width)
            settings.set("window", "height", height)
        if hasattr(self, "_hpaned"):
            browser_width = self._hpaned.get_position()
            if browser_width > 50:
                settings.set("window", "browser_width", browser_width)
        settings.save()

    def _on_close_request(self, window):
        """Handle window close — check for unsaved changes first."""
        self._save_window_state()
        if hasattr(self, "editor") and self.editor.has_unsaved_changes():
            unsaved = self.editor.get_unsaved_tabs()
            dialog = Gtk.AlertDialog()
            dialog.set_message(
                f"You have {len(unsaved)} tab(s) with unsaved changes:\n"
                + "\n".join(f"  • {t}" for t in unsaved)
                + "\n\nDo you want to save before closing?"
            )
            dialog.set_buttons(["Cancel", "Close without Saving", "Save and Close"])
            dialog.set_cancel_button(0)
            dialog.set_default_button(2)

            def on_response(dialog, result):
                response = dialog.choose_finish(result)
                if response == 0:
                    return
                elif response == 1:
                    self._do_close()
                elif response == 2:
                    self._save_all_tabs()
                    self._do_close()

            dialog.choose(self, None, on_response)
            return True

        self._do_close()
        return False

    def _do_close(self):
        """Actually close the window after checks."""
        self._save_window_state()
        if self.db_connector.is_connected:
            try:
                self.db_connector.disconnect()
                logger.info("Disconnected on window close")
            except Exception as e:
                logger.error(f"Disconnect on close error: {e}")
        self.get_application().quit()

    def _save_all_tabs(self):
        """Save all unsaved tabs."""
        for tab in self.editor._tabs:
            if tab._modified:
                idx = self.editor._tabs.index(tab)
                self.editor._notebook.set_current_page(idx)
                if hasattr(self, "_current_file") and self._current_file:
                    self._save_to_file(self._current_file)
                else:
                    self._on_file_save_as()

    def _on_new_tab(self):
        """Create a new editor tab."""
        self.editor.add_tab()

    def _on_close_tab(self):
        """Close the active editor tab."""
        tab = self.editor.get_active_tab()
        if tab:
            self.editor.close_tab(tab)
