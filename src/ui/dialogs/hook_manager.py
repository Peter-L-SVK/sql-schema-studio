# ----------------------------------------------------------------------
# SQL Schema Studio 0.8 - Hook Manager Dialog (GPLv3)
# Copyright (C) 2026 Peter Leukanič
# License: GNU GPL v3+ <https://www.gnu.org/licenses/gpl-3.0.txt>
# This is free software with NO WARRANTY.
# Feel free to distribute and modify.
# ----------------------------------------------------------------------

"""Hook manager dialog for enabling and configuring plugins."""

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, Gdk

from src.config import HOOK_RESULT_DIALOG_WIDTH, HOOK_RESULT_DIALOG_HEIGHT
from src.utils.gtk_helpers import set_margin
from src.utils.logging import get_logger

logger = get_logger(__name__)


class HookManagerDialog(Gtk.Window):
    """Dialog for managing Python and Perl hooks."""

    def __init__(self, parent, db_connector=None):
        super().__init__(
            title="Hook Manager",
            transient_for=parent,
            modal=True,
        )
        self.set_default_size(500, 400)
        self._build_ui()
        self._load_hooks()
        self._db_connector = db_connector

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

        btn_run = Gtk.Button(label="Run Selected")
        btn_run.add_css_class("suggested-action")
        btn_run.connect("clicked", self._on_run_hook)
        button_box.append(btn_run)

        btn_close = Gtk.Button(label="Close")
        btn_close.connect("clicked", lambda b: self.close())
        button_box.append(btn_close)

        main_box.append(button_box)
        self.set_child(main_box)

    def _load_hooks(self):
        self._list_store.clear()
        try:
            from src.hooks.registry import PluginRegistry

            registry = PluginRegistry()
            registry.discover_plugins()
            hooks = registry.list_hooks()

            for name, hook in hooks.items():
                if hasattr(hook, "get_metadata"):
                    meta = hook.get_metadata()
                    lang = "python"
                    status = "ready"
                else:
                    meta = hook
                    lang = meta.get("type", "perl")
                    status = meta.get("status", "available")

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

    def _on_run_hook(self, button):
        selection = self._tree.get_selection()
        model, tree_iter = selection.get_selected()
        if not tree_iter:
            return

        hook_name = model.get_value(tree_iter, 0)
        logger.info(f"Running hook: {hook_name}")

        try:
            from src.hooks.registry import PluginRegistry
            from src.hooks.base_plugin import HookContext, HookTrigger

            registry = PluginRegistry()
            registry.discover_plugins()

            all_hooks = registry.list_hooks()
            hook = all_hooks.get(hook_name)

            if hook and hasattr(hook, "execute_sync"):
                # Sync hook (new style)
                conn_string = ""
                if self._db_connector and self._db_connector.is_connected:
                    try:
                        conn_string = self._db_connector._get_conn_string()
                    except Exception:
                        pass

                if not conn_string:
                    self._show_error(hook_name, "No active database connection")
                    return

                hook_result = hook.execute_sync(conn_string)
                self._show_result(hook_name, hook_result)

            elif hook and hasattr(hook, "execute"):
                # Async hook (original style) — run in event loop
                context = HookContext(
                    trigger=HookTrigger.SCHEDULED_INTERVAL,
                    database="",
                    connection_pool=None,
                    data={},
                )

                import asyncio

                async def run():
                    return await hook.execute(context)

                with asyncio.Runner() as runner:
                    result = runner.run(run())

                self._show_result(hook_name, str(result))

            elif hook and isinstance(hook, dict) and hook.get("type") == "perl":
                # Perl hook
                from src.hooks.perl.executor import PerlHookExecutor

                executor = PerlHookExecutor()
                import asyncio

                async def run_perl():
                    return await executor.execute(hook["path"], {"data": {}})

                with asyncio.Runner() as runner:
                    result = runner.run(run_perl())
                    self._show_result(hook_name, str(result))

            else:
                logger.warning(f"Hook not executable: {hook_name}")
                self._show_error(hook_name, "Hook not executable")

        except Exception as e:
            logger.error(f"Error: {e}")
            self._show_error(hook_name, str(e))

    def _show_result(self, hook_name, result):
        """Show hook execution result in a readable dialog."""
        import json

        # Parse result if it's a string
        if isinstance(result, str):
            try:
                data = json.loads(result.replace("'", '"'))
            except Exception:
                data = {"message": result}
        else:
            data = result

        # Format as readable text
        text = f"<b>Hook:</b> {hook_name}\n\n"

        if isinstance(data, dict):
            if data.get("status") == "error":
                text += f"<span color='red'><b>Error:</b> {data.get('message', 'Unknown error')}</span>\n"
            else:
                text += "<span color='green'><b>Status:</b> OK</span>\n"
                text += f"<b>Tables analyzed:</b> {data.get('tables_analyzed', 'N/A')}\n"
                text += f"<b>Recommendations:</b> {data.get('recommendations_count', 0)}\n\n"

                recommendations = data.get("recommendations", [])
                if recommendations:
                    text += "<b>Recommendations:</b>\n"
                    for r in recommendations[:10]:  # Limit to 10
                        text += f"  • <b>{r.get('table', '?')}</b>\n"
                        text += f"    Priority: {r.get('priority', '?')}\n"
                        text += f"    Action: {r.get('action', '?')}\n"
                        text += f"    Reason: {r.get('reason', '?')}\n"
                        if r.get("sql"):
                            text += f"    SQL: <tt>{r['sql']}</tt>\n"
                        text += "\n"
        else:
            text += str(data)

        # Create dialog with copy button
        dialog = Gtk.Window(
            transient_for=self,
            modal=True,
            title=f"Hook Result: {hook_name}",
            default_width=HOOK_RESULT_DIALOG_WIDTH,
            default_height=HOOK_RESULT_DIALOG_HEIGHT,
        )
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        set_margin(main_box, 12)

        # Result text (selectable)
        label = Gtk.Label()
        label.set_markup(text)
        label.set_selectable(True)
        label.set_halign(Gtk.Align.START)
        label.set_wrap(True)

        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)
        scroll.set_child(label)
        main_box.append(scroll)

        # Copy button
        btn_copy = Gtk.Button(label="Copy to Clipboard")
        btn_copy.connect("clicked", lambda b: self._copy_to_clipboard(text))

        btn_close = Gtk.Button(label="Close")
        btn_close.connect("clicked", lambda b: dialog.close())

        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        button_box.set_halign(Gtk.Align.END)
        button_box.append(btn_copy)
        button_box.append(btn_close)
        main_box.append(button_box)

        dialog.set_child(main_box)
        dialog.present()

    def _copy_to_clipboard(self, text):
        """Copy text to clipboard."""
        import re

        # Strip HTML tags for plain text
        plain = re.sub(r"<[^>]+>", "", text)
        plain = plain.replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")

        clipboard = Gdk.Display.get_default().get_clipboard()
        clipboard.set(plain)
        logger.info("Result copied to clipboard")

    def _show_error(self, hook_name, error):
        """Show hook execution error."""
        dialog = Gtk.MessageDialog(
            transient_for=self,
            modal=True,
            message_type=Gtk.MessageType.ERROR,
            buttons=Gtk.ButtonsType.OK,
            text=f"Hook failed: {hook_name}",
            secondary_text=error,
        )
        dialog.connect("response", lambda d, r: d.close())
        dialog.present()
