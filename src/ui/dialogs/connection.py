# ----------------------------------------------------------------------
# SQL Schema Studio 0.5 - Connection Dialog (GPLv3)
# Copyright (C) 2026 Peter Leukanič
# License: GNU GPL v3+ <https://www.gnu.org/licenses/gpl-3.0.txt>
# This is free software with NO WARRANTY.
# Feel free to distribute and modify.
# ----------------------------------------------------------------------

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk
from src.core.db_connector import ConnectionProfile
from src.utils.gtk_helpers import set_margin, make_labeled_field, make_button_box, run_async


class ConnectionDialog(Gtk.Dialog):
    """Database connection dialog"""

    def __init__(self, parent, db_connector=None, on_connected=None):
        super().__init__(
            title="Connect to PostgreSQL", transient_for=parent, modal=True, use_header_bar=False
        )

        self.db_connector = db_connector
        self._on_connected = on_connected
        self.set_default_size(450, 400)
        self._connecting = False

        self._build_content()
        self._build_buttons()

    def _build_content(self):
        content = self.get_content_area()
        content.set_spacing(12)
        set_margin(content, 16)

        self._entry_name = Gtk.Entry()
        self._entry_name.set_text("Local PostgreSQL")
        content.append(make_labeled_field("Connection Name:", self._entry_name))

        self._entry_host = Gtk.Entry()
        self._entry_host.set_text("localhost")
        content.append(make_labeled_field("Host:", self._entry_host))

        self._entry_port = Gtk.Entry()
        self._entry_port.set_text("5432")
        content.append(make_labeled_field("Port:", self._entry_port))

        self._entry_db = Gtk.Entry()
        self._entry_db.set_text("postgres")
        content.append(make_labeled_field("Database:", self._entry_db))

        self._entry_user = Gtk.Entry()
        self._entry_user.set_text("postgres")
        content.append(make_labeled_field("Username:", self._entry_user))

        # Password with visibility toggle
        self._entry_pass = Gtk.PasswordEntry()
        self._entry_pass.set_show_peek_icon(True)
        self._entry_pass.connect("activate", lambda e: self._on_connect_clicked(self._btn_connect))
        content.append(make_labeled_field("Password:", self._entry_pass))

        self._combo_ssl = Gtk.ComboBoxText()
        for mode in ["prefer", "require", "disable", "allow", "verify-full"]:
            self._combo_ssl.append_text(mode)
        self._combo_ssl.set_active(0)
        content.append(make_labeled_field("SSL Mode:", self._combo_ssl))

        self._check_save = Gtk.CheckButton(label="Save this connection")
        self._check_save.set_active(True)
        content.append(self._check_save)

        btn_test = Gtk.Button(label="Test Connection")
        btn_test.connect("clicked", self._on_test_clicked)
        content.append(btn_test)

        self._lbl_status = Gtk.Label()
        self._lbl_status.set_wrap(True)
        content.append(self._lbl_status)

    def _build_buttons(self):
        self._btn_connect = Gtk.Button(label="Connect")
        self._btn_connect.add_css_class("suggested-action")
        self._btn_connect.connect("clicked", self._on_connect_clicked)

        self._btn_cancel = Gtk.Button(label="Cancel")
        self._btn_cancel.connect("clicked", lambda b: self.close())

        button_box = make_button_box([self._btn_cancel, self._btn_connect])
        set_margin(button_box, 12)
        self.get_content_area().append(button_box)

    def _get_values(self) -> ConnectionProfile:
        return ConnectionProfile(
            name=self._entry_name.get_text(),
            host=self._entry_host.get_text(),
            port=int(self._entry_port.get_text() or "5432"),
            database=self._entry_db.get_text(),
            username=self._entry_user.get_text(),
            password=self._entry_pass.get_text(),
            ssl_mode=self._combo_ssl.get_active_text() or "prefer",
        )

    def _set_busy(self, busy):
        self._connecting = busy
        self._btn_connect.set_sensitive(not busy)
        self._btn_cancel.set_sensitive(not busy)
        self._entry_name.set_sensitive(not busy)
        self._entry_host.set_sensitive(not busy)
        self._entry_port.set_sensitive(not busy)
        self._entry_db.set_sensitive(not busy)
        self._entry_user.set_sensitive(not busy)
        self._entry_pass.set_sensitive(not busy)
        self._combo_ssl.set_sensitive(not busy)
        self._check_save.set_sensitive(not busy)

    def _on_test_clicked(self, button):
        """Test the connection"""
        import psycopg

        profile = self._get_values()
        self._lbl_status.set_text("Testing connection...")
        self._set_busy(True)

        def test():
            conn_string = (
                f"host={profile.host} "
                f"port={profile.port} "
                f"dbname={profile.database} "
                f"user={profile.username} "
                f"password={profile.password}"
            )
            try:
                conn = psycopg.connect(conn_string)
                conn.execute("SELECT 1")
                conn.close()
                return True, "Connection successful!"
            except Exception as e:
                return False, str(e)

        def on_done(result):
            self._set_busy(False)
            success, message = result
            if success:
                self._lbl_status.set_markup(f'<span foreground="green">✓ {message}</span>')
            else:
                self._lbl_status.set_markup(f'<span foreground="red">✗ {message}</span>')

        run_async(test, on_done)

    def _on_connect_clicked(self, button):
        """Connect to database"""
        profile = self._get_values()
        self._set_busy(True)
        self._lbl_status.set_text("Connecting...")

        def connect():
            try:
                success = self.db_connector.connect_sync(profile)
                return success, None
            except Exception as e:
                return False, str(e)

        def on_done(result):
            success, error = result

            if success:
                if self._check_save.get_active():
                    self.db_connector.add_profile(profile)
                if self._on_connected:
                    self._on_connected()
                self._set_busy(False)
                self.destroy()
            else:
                self._set_busy(False)
                msg = error or "Connection failed"
                self._lbl_status.set_markup(f'<span foreground="red">✗ {msg}</span>')

        run_async(connect, on_done)
