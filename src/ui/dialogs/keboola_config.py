# ----------------------------------------------------------------------
# SQL Schema Studio 0.9 - Keboola Configuration Dialog (GPLv3)
# Copyright (C) 2026 Peter Leukanič
# License: GNU GPL v3+ <https://www.gnu.org/licenses/gpl-3.0.txt>
# This is free software with NO WARRANTY.
# Feel free to distribute and modify.
# ----------------------------------------------------------------------

"""Configuration dialog for Keboola integration."""

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, GLib

from src.utils.gtk_helpers import set_margin, make_labeled_field
from src.utils.logging import get_logger

logger = get_logger(__name__)


class KeboolaConfigDialog(Gtk.Window):
    """Configuration dialog for Keboola Normalizer Hook."""

    def __init__(self, parent, hook, on_saved=None):
        super().__init__(
            title="Keboola Normalizer Configuration",
            transient_for=parent,
            modal=True,
        )
        self._hook = hook
        self._on_saved = on_saved
        self.set_default_size(550, 550)
        self._build_ui()
        self._load_config()

    def _build_ui(self):
        """Build the dialog UI."""
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        set_margin(main_box, 16)

        # Scrollable content
        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)
        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        set_margin(content_box, 8)

        # ============================================================
        # Section: Connection
        # ============================================================
        conn_label = Gtk.Label(label="<b>Connection Settings</b>")
        conn_label.set_use_markup(True)
        conn_label.set_halign(Gtk.Align.START)
        content_box.append(conn_label)

        # API URL
        self._api_url_entry = Gtk.Entry()
        self._api_url_entry.set_placeholder_text("https://connection.keboola.com/")
        content_box.append(make_labeled_field("API URL:", self._api_url_entry))

        # API Token - používame Gtk.Entry s visibility=False
        self._token_entry = Gtk.Entry()
        self._token_entry.set_visibility(False)  # Skryje text
        self._token_entry.set_placeholder_text("Your Keboola API token")
        content_box.append(make_labeled_field("API Token:", self._token_entry))

        # ============================================================
        # Section: Storage
        # ============================================================
        storage_label = Gtk.Label(label="<b>Storage Settings</b>")
        storage_label.set_use_markup(True)
        storage_label.set_halign(Gtk.Align.START)
        storage_label.set_margin_top(12)
        content_box.append(storage_label)

        # Bucket
        self._bucket_entry = Gtk.Entry()
        self._bucket_entry.set_text("in.c-sql-schema-studio")
        content_box.append(make_labeled_field("Bucket:", self._bucket_entry))

        # Source table
        self._source_table_entry = Gtk.Entry()
        self._source_table_entry.set_text("raw_orders")
        content_box.append(make_labeled_field("Source Table:", self._source_table_entry))

        # Output table
        self._output_table_entry = Gtk.Entry()
        self._output_table_entry.set_text("normalized_orders")
        content_box.append(make_labeled_field("Output Table:", self._output_table_entry))

        # ============================================================
        # Section: Flow
        # ============================================================
        flow_label = Gtk.Label(label="<b>Flow Settings</b>")
        flow_label.set_use_markup(True)
        flow_label.set_halign(Gtk.Align.START)
        flow_label.set_margin_top(12)
        content_box.append(flow_label)

        # Flow ID
        self._flow_id_entry = Gtk.Entry()
        self._flow_id_entry.set_placeholder_text("e.g., 12345")
        content_box.append(make_labeled_field("Flow ID (optional):", self._flow_id_entry))

        # ============================================================
        # Section: Mode
        # ============================================================
        mode_label = Gtk.Label(label="<b>Operation Mode</b>")
        mode_label.set_use_markup(True)
        mode_label.set_halign(Gtk.Align.START)
        mode_label.set_margin_top(12)
        content_box.append(mode_label)

        self._local_mode_check = Gtk.CheckButton(label="Local mode only (skip Keboola upload)")
        self._local_mode_check.set_active(True)
        content_box.append(self._local_mode_check)

        self._auto_upload_check = Gtk.CheckButton(label="Auto-upload when hook runs")
        self._auto_upload_check.set_active(False)
        self._auto_upload_check.set_sensitive(False)
        self._local_mode_check.connect("toggled", self._on_local_mode_toggled)
        content_box.append(self._auto_upload_check)

        # ============================================================
        # Info box
        # ============================================================
        info_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        info_box.set_margin_top(12)
        info_box.set_margin_bottom(8)
        info_box.set_margin_start(4)
        info_box.set_margin_end(4)

        info_label = Gtk.Label()
        info_label.set_markup(
            '<span foreground="gray" size="small">'
            "💡 Get your API token from Keboola Connection → Settings → API tokens\n"
            "📦 Create a bucket in Storage first (e.g., in.c-sql-schema-studio)\n"
            "🔄 Flow ID is optional – used to trigger existing orchestrations"
            "</span>"
        )
        info_label.set_wrap(True)
        info_label.set_halign(Gtk.Align.START)
        info_box.append(info_label)
        content_box.append(info_box)

        scroll.set_child(content_box)
        main_box.append(scroll)

        # ============================================================
        # Buttons
        # ============================================================
        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        button_box.set_halign(Gtk.Align.END)
        button_box.set_margin_top(8)

        # Test connection button
        btn_test = Gtk.Button(label="Test Connection")
        btn_test.connect("clicked", self._on_test_connection)
        button_box.append(btn_test)

        # Cancel
        btn_cancel = Gtk.Button(label="Cancel")
        btn_cancel.connect("clicked", lambda b: self.close())
        button_box.append(btn_cancel)

        # Save
        self._btn_save = Gtk.Button(label="Save")
        self._btn_save.add_css_class("suggested-action")
        self._btn_save.connect("clicked", self._on_save)
        button_box.append(self._btn_save)

        main_box.append(button_box)

        # Status bar at bottom
        self._status_label = Gtk.Label()
        self._status_label.set_halign(Gtk.Align.START)
        self._status_label.set_margin_top(4)
        main_box.append(self._status_label)

        self.set_child(main_box)

    def _on_local_mode_toggled(self, check):
        """Enable/disable auto-upload based on local mode."""
        enabled = not check.get_active()
        self._auto_upload_check.set_sensitive(enabled)

    def _load_config(self):
        """Load configuration from hook."""
        config = self._hook._config if hasattr(self._hook, "_config") else {}

        self._api_url_entry.set_text(config.get("api_url", "https://connection.keboola.com/"))
        self._token_entry.set_text(config.get("token", ""))
        self._bucket_entry.set_text(config.get("bucket", "in.c-sql-schema-studio"))
        self._source_table_entry.set_text(config.get("source_table", "raw_orders"))
        self._output_table_entry.set_text(config.get("output_table", "normalized_orders"))
        self._flow_id_entry.set_text(config.get("flow_id", ""))
        self._local_mode_check.set_active(config.get("local_mode", True))
        self._auto_upload_check.set_active(config.get("auto_upload", False))
        self._auto_upload_check.set_sensitive(not config.get("local_mode", True))

    def _on_save(self, button):
        """Save configuration."""
        try:
            config = {
                "api_url": self._api_url_entry.get_text().strip(),
                "token": self._token_entry.get_text().strip(),
                "bucket": self._bucket_entry.get_text().strip(),
                "source_table": self._source_table_entry.get_text().strip(),
                "output_table": self._output_table_entry.get_text().strip(),
                "flow_id": self._flow_id_entry.get_text().strip(),
                "local_mode": self._local_mode_check.get_active(),
                "auto_upload": self._auto_upload_check.get_active(),
            }

            # Update hook config
            if hasattr(self._hook, "_config"):
                self._hook._config = config
                if hasattr(self._hook, "_save_config"):
                    self._hook._save_config()

            self._status_label.set_markup(
                '<span foreground="green">✓ Configuration saved successfully</span>'
            )
            logger.info("Keboola configuration saved")

            if self._on_saved:
                self._on_saved()

            # Close after short delay
            GLib.timeout_add(800, self.close)

        except Exception as e:
            self._status_label.set_markup(f'<span foreground="red">✗ Error: {str(e)}</span>')
            logger.error(f"Failed to save Keboola config: {e}")

    def _on_test_connection(self, button):
        """Test connection to Keboola."""
        token = self._token_entry.get_text().strip()
        api_url = self._api_url_entry.get_text().strip()

        if not token:
            self._status_label.set_markup('<span foreground="red">✗ Please enter API token</span>')
            return

        self._status_label.set_text("Testing connection...")
        button.set_sensitive(False)

        # Test in background
        GLib.idle_add(self._do_test_connection, token, api_url, button)

    def _do_test_connection(self, token, api_url, button):
        """Perform connection test (runs in main thread)."""
        try:
            from keboola.storage_client import Client

            client = Client(token, api_url)
            buckets = client.buckets.list()

            # Check if our bucket exists
            bucket_name = self._bucket_entry.get_text().strip()
            bucket_exists = any(b.get("id") == bucket_name for b in buckets)

            if bucket_exists:
                self._status_label.set_markup(
                    f'<span foreground="green">✓ Connected! Bucket "{bucket_name}" found</span>'
                )
            else:
                self._status_label.set_markup(
                    f'<span foreground="orange">⚠ Connected, but bucket "{bucket_name}" not found</span>'
                )

        except ImportError:
            self._status_label.set_markup(
                '<span foreground="red">✗ Keboola client not installed. Run: pip install keboola-storage-client</span>'
            )
        except Exception as e:
            self._status_label.set_markup(
                f'<span foreground="red">✗ Connection failed: {str(e)}</span>'
            )

        button.set_sensitive(True)
        return False  # One-shot idle
