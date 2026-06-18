# ----------------------------------------------------------------------
# SQL Schema Studio 0.9 - Connection Dialog (GPLv3)
# Copyright (C) 2026 Peter Leukanič
# License: GNU GPL v3+ <https://www.gnu.org/licenses/gpl-3.0.txt>
# This is free software with NO WARRANTY.
# Feel free to distribute and modify.
# ----------------------------------------------------------------------

from __future__ import annotations

import gi
import os

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, GLib
from src.core.db_connector import ConnectionProfile
from src.utils.gtk_helpers import set_margin, make_labeled_field, make_button_box, run_async


class ConnectionDialog(Gtk.Dialog):
    """Database connection dialog with SSH tunnel support"""

    def __init__(self, parent, db_connector=None, on_connected=None):
        super().__init__(
            title="Connect to PostgreSQL", transient_for=parent, modal=True, use_header_bar=False
        )

        self.db_connector = db_connector
        self._on_connected = on_connected
        self.set_default_size(480, 520)
        self._connecting = False

        self._build_content()
        self._build_buttons()

    def _build_content(self):
        content = self.get_content_area()
        content.set_spacing(8)
        set_margin(content, 12)

        # Notebook for tabs
        self._notebook = Gtk.Notebook()
        self._notebook.set_vexpand(True)

        # --- Tab 1: Basic ---
        basic_tab = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        set_margin(basic_tab, 8)

        self._entry_name = Gtk.Entry()
        self._entry_name.set_text("Local PostgreSQL")
        basic_tab.append(make_labeled_field("Connection Name:", self._entry_name))

        self._entry_host = Gtk.Entry()
        self._entry_host.set_text("localhost")
        basic_tab.append(make_labeled_field("Host:", self._entry_host))

        self._entry_port = Gtk.Entry()
        self._entry_port.set_text("5432")
        basic_tab.append(make_labeled_field("Port:", self._entry_port))

        self._entry_db = Gtk.Entry()
        self._entry_db.set_text("postgres")
        basic_tab.append(make_labeled_field("Database:", self._entry_db))

        self._entry_user = Gtk.Entry()
        self._entry_user.set_text("postgres")
        basic_tab.append(make_labeled_field("Username:", self._entry_user))

        # Password with visibility toggle
        self._entry_pass = Gtk.PasswordEntry()
        self._entry_pass.set_show_peek_icon(True)
        self._entry_pass.connect("activate", lambda e: self._on_connect_clicked(self._btn_connect))
        basic_tab.append(make_labeled_field("Password:", self._entry_pass))

        self._combo_ssl = Gtk.ComboBoxText()
        for mode in ["prefer", "require", "disable", "allow", "verify-full"]:
            self._combo_ssl.append_text(mode)
        self._combo_ssl.set_active(0)
        basic_tab.append(make_labeled_field("SSL Mode:", self._combo_ssl))

        self._notebook.append_page(basic_tab, Gtk.Label(label="Basic"))

        # --- Tab 2: SSH ---
        ssh_tab = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        set_margin(ssh_tab, 8)

        self._cb_ssh = Gtk.CheckButton(label="Use SSH Tunnel")
        self._cb_ssh.connect("toggled", self._on_ssh_toggled)
        ssh_tab.append(self._cb_ssh)

        self._entry_ssh_host = Gtk.Entry()
        self._entry_ssh_host.set_placeholder_text("ssh.example.com")
        self._entry_ssh_host.set_sensitive(False)
        ssh_tab.append(make_labeled_field("SSH Host:", self._entry_ssh_host))

        self._entry_ssh_port = Gtk.Entry()
        self._entry_ssh_port.set_text("22")
        self._entry_ssh_port.set_sensitive(False)
        ssh_tab.append(make_labeled_field("SSH Port:", self._entry_ssh_port))

        self._entry_ssh_user = Gtk.Entry()
        self._entry_ssh_user.set_placeholder_text("user")
        self._entry_ssh_user.set_sensitive(False)
        ssh_tab.append(make_labeled_field("SSH Username:", self._entry_ssh_user))

        # Auth method
        self._combo_ssh_auth = Gtk.ComboBoxText()
        self._combo_ssh_auth.append_text("Password")
        self._combo_ssh_auth.append_text("SSH Key")
        self._combo_ssh_auth.append_text("SSH Agent")
        self._combo_ssh_auth.set_active(0)
        self._combo_ssh_auth.set_sensitive(False)
        self._combo_ssh_auth.connect("changed", self._on_ssh_auth_changed)
        ssh_tab.append(make_labeled_field("Authentication:", self._combo_ssh_auth))

        # Password (visible by default)
        self._ssh_password_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self._entry_ssh_pass = Gtk.PasswordEntry()
        self._entry_ssh_pass.set_show_peek_icon(True)
        self._entry_ssh_pass.set_sensitive(False)
        self._ssh_password_box.append(make_labeled_field("SSH Password:", self._entry_ssh_pass))
        ssh_tab.append(self._ssh_password_box)

        # Key file (hidden by default)
        self._ssh_key_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        key_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        self._entry_ssh_key = Gtk.Entry()
        self._entry_ssh_key.set_placeholder_text("~/.ssh/id_ed25519")
        self._entry_ssh_key.set_hexpand(True)
        self._entry_ssh_key.set_sensitive(False)
        key_row.append(self._entry_ssh_key)
        self._btn_browse_ssh = Gtk.Button(label="...")
        self._btn_browse_ssh.set_sensitive(False)
        self._btn_browse_ssh.connect("clicked", self._on_browse_ssh_key)
        key_row.append(self._btn_browse_ssh)
        self._ssh_key_box.append(make_labeled_field("SSH Key File:", key_row))
        self._ssh_key_box.set_visible(False)
        ssh_tab.append(self._ssh_key_box)

        # Remote target
        self._entry_ssh_remote_host = Gtk.Entry()
        self._entry_ssh_remote_host.set_text("localhost")
        self._entry_ssh_remote_host.set_sensitive(False)
        ssh_tab.append(make_labeled_field("Remote Host:", self._entry_ssh_remote_host))

        self._entry_ssh_remote_port = Gtk.Entry()
        self._entry_ssh_remote_port.set_text("5432")
        self._entry_ssh_remote_port.set_sensitive(False)
        ssh_tab.append(make_labeled_field("Remote Port:", self._entry_ssh_remote_port))

        self._notebook.append_page(ssh_tab, Gtk.Label(label="SSH"))

        content.append(self._notebook)

        # Save checkbox
        self._check_save = Gtk.CheckButton(label="Save this connection")
        self._check_save.set_active(True)
        content.append(self._check_save)

        # Test button
        btn_test = Gtk.Button(label="Test Connection")
        btn_test.connect("clicked", self._on_test_clicked)
        content.append(btn_test)

        # Status label
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
        set_margin(button_box, 8)
        self.get_content_area().append(button_box)

    # =====================================================================
    # SSH UI handlers
    # =====================================================================

    def _on_ssh_toggled(self, check):
        """Enable/disable SSH fields."""
        enabled = check.get_active()
        self._entry_ssh_host.set_sensitive(enabled)
        self._entry_ssh_port.set_sensitive(enabled)
        self._entry_ssh_user.set_sensitive(enabled)
        self._combo_ssh_auth.set_sensitive(enabled)
        self._entry_ssh_pass.set_sensitive(enabled and self._combo_ssh_auth.get_active() == 0)
        self._entry_ssh_key.set_sensitive(enabled and self._combo_ssh_auth.get_active() == 1)
        self._btn_browse_ssh.set_sensitive(enabled and self._combo_ssh_auth.get_active() == 1)
        self._entry_ssh_remote_host.set_sensitive(enabled)
        self._entry_ssh_remote_port.set_sensitive(enabled)

    def _on_ssh_auth_changed(self, combo):
        """Show/hide password vs key fields."""
        if not self._cb_ssh.get_active():
            return
        auth_type = combo.get_active()
        self._ssh_password_box.set_visible(auth_type == 0)
        self._ssh_key_box.set_visible(auth_type == 1)
        self._entry_ssh_pass.set_sensitive(auth_type == 0)
        self._entry_ssh_key.set_sensitive(auth_type == 1)
        self._btn_browse_ssh.set_sensitive(auth_type == 1)

    def _on_browse_ssh_key(self, button):
        """Open file dialog for SSH key."""
        dialog = Gtk.FileDialog()
        dialog.set_title("Select SSH Private Key")

        def on_open(dialog, result):
            try:
                file = dialog.open_finish(result)
                if file:
                    self._entry_ssh_key.set_text(file.get_path())
            except Exception:
                pass

        dialog.open(self, None, on_open)

    # =====================================================================
    # Connection logic
    # =====================================================================

    def _get_values(self) -> ConnectionProfile:
        return ConnectionProfile(
            name=self._entry_name.get_text(),
            host=self._entry_host.get_text(),
            port=int(self._entry_port.get_text() or "5432"),
            database=self._entry_db.get_text(),
            username=self._entry_user.get_text(),
            password=self._entry_pass.get_text(),
            ssl_mode=self._combo_ssl.get_active_text() or "prefer",
            use_ssh=self._cb_ssh.get_active(),
            ssh_host=self._entry_ssh_host.get_text(),
            ssh_port=int(self._entry_ssh_port.get_text() or "22"),
            ssh_user=self._entry_ssh_user.get_text(),
            ssh_password=self._entry_ssh_pass.get_text(),
            ssh_key_path=self._entry_ssh_key.get_text(),
            ssh_remote_host=self._entry_ssh_remote_host.get_text() or "localhost",
            ssh_remote_port=int(self._entry_ssh_remote_port.get_text() or "5432"),
        )

    def _set_busy(self, busy):
        self._connecting = busy
        self._btn_connect.set_sensitive(not busy)
        self._btn_cancel.set_sensitive(not busy)
        self._notebook.set_sensitive(not busy)
        self._check_save.set_sensitive(not busy)

    def _on_test_clicked(self, button):
        """Test the connection."""
        import psycopg

        profile = self._get_values()
        self._lbl_status.set_text("Testing connection...")
        self._set_busy(True)

        def test():
            try:
                # Build connection string (with SSH if enabled)
                if profile.use_ssh:
                    from src.core.ssh_tunnel import (
                        SSHTunnelConfig,
                        get_postgres_conn_string_with_ssh,
                    )

                    ssh_config = SSHTunnelConfig(
                        enabled=True,
                        ssh_host=profile.ssh_host,
                        ssh_port=profile.ssh_port,
                        ssh_user=profile.ssh_user,
                        ssh_password=profile.ssh_password,
                        ssh_key_path=profile.ssh_key_path,
                        remote_host=profile.ssh_remote_host,
                        remote_port=profile.ssh_remote_port,
                    )
                    db_config = {
                        "host": profile.host,
                        "port": profile.port,
                        "database": profile.database,
                        "username": profile.username,
                        "password": profile.password,
                    }
                    conn_string, tunnel, error = get_postgres_conn_string_with_ssh(
                        ssh_config, db_config
                    )
                    if error:
                        return False, f"SSH: {error}"
                else:
                    conn_string = (
                        f"host=127.0.0.1 port={local_port} "
                        f"port={profile.port} "
                        f"dbname={profile.database} "
                        f"user={profile.username} "
                        f"password={profile.password}"
                    )
                    tunnel = None

                conn = psycopg.connect(conn_string)
                conn.execute("SELECT 1")
                conn.close()
                if tunnel:
                    tunnel.stop()
                return True, "Connection successful!"
            except Exception as e:
                if tunnel:
                    tunnel.stop()
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
        """Connect to database."""
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
