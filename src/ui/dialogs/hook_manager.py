# ----------------------------------------------------------------------
# SQL Schema Studio 0.5 - Hook Manager Dialog (GPLv3)
# Copyright (C) 2026 Peter Leukanič
# License: GNU GPL v3+ <https://www.gnu.org/licenses/gpl-3.0.txt>
# This is free software with NO WARRANTY.
# Feel free to distribute and modify.
# ----------------------------------------------------------------------

"""Hook manager dialog for enabling and configuring plugins."""

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

from src.utils.gtk_helpers import set_margin
from src.utils.logging import get_logger

logger = get_logger(__name__)


class HookManagerDialog(Gtk.Window):
    """Dialog for managing Python and Perl hooks."""

    def __init__(self, parent):
        super().__init__(
            title="Hook Manager",
            transient_for=parent,
            modal=True,
        )
        self.set_default_size(500, 400)
        self._build_ui()
        self._load_hooks()

    def _build_ui(self):
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        set_margin(main_box, 16)

        # Hook list
        label = Gtk.Label(label="Installed Hooks", halign=Gtk.Align.START)
        label.add_css_class("heading")
        main_box.append(label)

        self._list_store = Gtk.ListStore(str, str, bool, str)
        self._tree = Gtk.TreeView(model=self._list_store)
        self._tree.set_headers_visible(True)

        # Name
        name_renderer = Gtk.CellRendererText()
        name_col = Gtk.TreeViewColumn("Hook", name_renderer, text=0)
        name_col.set_expand(True)
        self._tree.append_column(name_col)

        # Language
        lang_renderer = Gtk.CellRendererText()
        lang_col = Gtk.TreeViewColumn("Language", lang_renderer, text=1)
        self._tree.append_column(lang_col)

        # Enabled toggle
        toggle_renderer = Gtk.CellRendererToggle()
        toggle_renderer.connect("toggled", self._on_toggled)
        toggle_col = Gtk.TreeViewColumn("Enabled", toggle_renderer, active=2)
        self._tree.append_column(toggle_col)

        # Status
        status_renderer = Gtk.CellRendererText()
        status_col = Gtk.TreeViewColumn("Status", status_renderer, text=3)
        self._tree.append_column(status_col)

        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)
        scroll.set_child(self._tree)
        main_box.append(scroll)

        # Buttons
        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        button_box.set_halign(Gtk.Align.END)

        btn_refresh = Gtk.Button(label="Refresh")
        btn_refresh.connect("clicked", lambda b: self._load_hooks())
        button_box.append(btn_refresh)

        btn_close = Gtk.Button(label="Close")
        btn_close.connect("clicked", lambda b: self.close())
        button_box.append(btn_close)

        main_box.append(button_box)
        self.set_child(main_box)

    def _load_hooks(self):
        """Load hooks from the registry."""
        self._list_store.clear()

        try:
            from src.hooks.registry import PluginRegistry

            registry = PluginRegistry()
            registry.discover_plugins()
            hooks = registry.list_hooks()

            for name, info in hooks.items():
                if isinstance(info, dict):
                    lang = info.get("type", "python")
                    status = info.get("status", "available")
                else:
                    # It's a BaseHook instance
                    _ = info.get_metadata() if hasattr(info, "get_metadata") else {}
                    lang = "python"
                    status = "ready"

                self._list_store.append([name, lang, False, status])

            logger.info(f"Loaded {len(hooks)} hooks")
        except Exception as e:
            logger.error(f"Failed to load hooks: {e}")

    def _on_toggled(self, renderer, path):
        """Toggle hook enabled state."""
        self._list_store[path][2] = not self._list_store[path][2]
        hook_name = self._list_store[path][0]
        enabled = self._list_store[path][2]
        logger.info(f"Hook '{hook_name}' {'enabled' if enabled else 'disabled'}")
