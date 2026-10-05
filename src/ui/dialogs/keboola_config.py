# ----------------------------------------------------------------------
# SQL Schema Studio 0.9.5 - Keboola Configuration Dialog (GPLv3)
# Copyright (C) 2026 Peter Leukanič
# License: GNU GPL v3+ <https://www.gnu.org/licenses/gpl-3.0.txt>
# This is free software with NO WARRANTY.
# Feel free to distribute and modify.
# ----------------------------------------------------------------------

"""Configuration dialog for the Keboola Normalizer hook.

Layout: a notebook with four tabs.

    Connection   — API URL + token, Test Connection
    Profiles     — list of saved profiles, Add / Duplicate / Remove / Set Active
    Profile      — editor for the selected profile (engine, tables, SQL)
    Report       — last pipeline run report

The SQL script is edited in the studio's main editor (see editor_bridge)
instead of embedding a second GtkSourceView here.
"""

from __future__ import annotations

import json

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, GLib

from src.hooks.python_hooks.keboola.editor_bridge import (
    open_profile_in_editor,
    save_sql_to_profile,
)
from src.hooks.python_hooks.keboola.engines import list_engines
from src.hooks.python_hooks.keboola.profiles import (
    KeboolaProfile,
    ProfileManager,
)
from src.utils.gtk_helpers import make_labeled_field, run_async, set_margin
from src.utils.logging import get_logger

logger = get_logger(__name__)


class KeboolaConfigDialog(Gtk.Window):
    """Configuration dialog for the Keboola Normalizer hook."""

    def __init__(self, parent, hook, on_saved=None):
        super().__init__(
            title="Keboola Normalizer Configuration",
            transient_for=parent,
            modal=False,   # non-modal so the user can work in the editor
        )
        self._window = parent
        self._hook = hook
        self._on_saved = on_saved
        self._manager = ProfileManager()
        self._selected_name: str = self._manager.active_name or ""

        self.set_default_size(720, 640)
        self._build_ui()
        self._refresh_profile_list()
        self._load_selected_profile()

    # ==================================================================
    # UI construction
    # ==================================================================

    def _build_ui(self):
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        set_margin(main_box, 0)

        notebook = Gtk.Notebook()
        notebook.set_vexpand(True)
        set_margin(notebook, 12)

        notebook.append_page(self._build_connection_tab(), Gtk.Label(label="Connection"))
        notebook.append_page(self._build_profiles_tab(), Gtk.Label(label="Profiles"))
        notebook.append_page(self._build_profile_editor_tab(), Gtk.Label(label="Profile"))
        notebook.append_page(self._build_report_tab(), Gtk.Label(label="Report"))

        main_box.append(notebook)

        # Bottom button row
        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        button_box.set_halign(Gtk.Align.END)
        set_margin(button_box, 12)

        self._status_label = Gtk.Label()
        self._status_label.set_halign(Gtk.Align.START)
        self._status_label.set_hexpand(True)
        button_box.append(self._status_label)

        btn_close = Gtk.Button(label="Close")
        btn_close.connect("clicked", lambda b: self.close())
        button_box.append(btn_close)

        btn_save = Gtk.Button(label="Save")
        btn_save.add_css_class("suggested-action")
        btn_save.connect("clicked", self._on_save)
        button_box.append(btn_save)

        main_box.append(button_box)
        self.set_child(main_box)

    # ------------------------------------------------------------------
    # Tab 1 — Connection
    # ------------------------------------------------------------------

    def _build_connection_tab(self) -> Gtk.Box:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        set_margin(box, 16)

        info = Gtk.Label()
        info.set_markup(
            '<span size="small" foreground="gray">'
            "The API token is stored in your system keyring, never in the "
            "profile JSON. Each profile has its own token.\n"
            "Get tokens from: Keboola Connection → Settings → API tokens"
            "</span>"
        )
        info.set_wrap(True)
        info.set_halign(Gtk.Align.START)
        box.append(info)

        # The API URL / token live on the profile, but for convenience
        # we edit them here for the *currently selected* profile.
        box.append(Gtk.Label(label="Currently selected profile:", halign=Gtk.Align.START))

        self._conn_profile_label = Gtk.Label()
        self._conn_profile_label.set_halign(Gtk.Align.START)
        self._conn_profile_label.add_css_class("heading")
        box.append(self._conn_profile_label)

        self._conn_api_url = Gtk.Entry()
        self._conn_api_url.set_placeholder_text("https://connection.keboola.com")
        box.append(make_labeled_field("API URL:", self._conn_api_url))

        self._conn_token = Gtk.Entry()
        self._conn_token.set_visibility(False)
        self._conn_token.set_placeholder_text("Your Keboola API token")
        box.append(make_labeled_field("API Token:", self._conn_token))

        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        btn_test = Gtk.Button(label="Test Connection")
        btn_test.connect("clicked", self._on_test_connection)
        btn_box.append(btn_test)
        box.append(btn_box)

        self._conn_status = Gtk.Label()
        self._conn_status.set_halign(Gtk.Align.START)
        self._conn_status.set_wrap(True)
        box.append(self._conn_status)

        return box

    # ------------------------------------------------------------------
    # Tab 2 — Profiles list
    # ------------------------------------------------------------------

    def _build_profiles_tab(self) -> Gtk.Box:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        set_margin(box, 16)

        hint = Gtk.Label()
        hint.set_markup(
            '<span size="small" foreground="gray">'
            "Each profile describes one transformation. Create separate "
            "profiles for separate datasets or engines."
            "</span>"
        )
        hint.set_halign(Gtk.Align.START)
        hint.set_wrap(True)
        box.append(hint)

        # List
        self._profile_store = Gtk.ListStore(str, str, str, bool)  # name, engine, id, active
        tree = Gtk.TreeView(model=self._profile_store)
        tree.set_headers_visible(True)

        for title, col_idx, expand in [
            ("Name", 0, True),
            ("Engine", 1, False),
            ("Transformation ID", 2, False),
            ("Active", 3, False),
        ]:
            renderer = Gtk.CellRendererText()
            if col_idx == 3:
                renderer = Gtk.CellRendererToggle()
                renderer.set_property("activatable", False)
            col = Gtk.TreeViewColumn(title, renderer, text=col_idx) if col_idx != 3 else \
                  Gtk.TreeViewColumn(title, renderer, active=col_idx)
            col.set_expand(expand)
            tree.append_column(col)

        self._profile_tree = tree
        tree.get_selection().connect("changed", self._on_profile_selected)

        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)
        scroll.set_child(tree)
        box.append(scroll)

        # Buttons
        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)

        btn_add = Gtk.Button(label="New")
        btn_add.connect("clicked", self._on_profile_new)
        btn_box.append(btn_add)

        btn_dup = Gtk.Button(label="Duplicate")
        btn_dup.connect("clicked", self._on_profile_duplicate)
        btn_box.append(btn_dup)

        btn_active = Gtk.Button(label="Set Active")
        btn_active.connect("clicked", self._on_profile_set_active)
        btn_box.append(btn_active)

        btn_remove = Gtk.Button(label="Remove")
        btn_remove.add_css_class("destructive-action")
        btn_remove.connect("clicked", self._on_profile_remove)
        btn_box.append(btn_remove)

        box.append(btn_box)
        return box

    # ------------------------------------------------------------------
    # Tab 3 — Profile editor
    # ------------------------------------------------------------------

    def _build_profile_editor_tab(self) -> Gtk.Box:
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        set_margin(outer, 16)

        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        set_margin(box, 4)

        # Name
        self._ed_name = Gtk.Entry()
        box.append(make_labeled_field("Profile Name:", self._ed_name))

        # Engine
        self._ed_engine = Gtk.ComboBoxText()
        self._engine_ids: list[str] = []
        for engine_id, display in list_engines():
            self._ed_engine.append(engine_id, display)
            self._engine_ids.append(engine_id)
        box.append(make_labeled_field("Engine:", self._ed_engine))

        # Bucket
        self._ed_bucket = Gtk.Entry()
        box.append(make_labeled_field("Input Bucket:", self._ed_bucket))

        # Input table
        self._ed_input = Gtk.Entry()
        box.append(make_labeled_field("Input Table:", self._ed_input))

        # Output table
        self._ed_output = Gtk.Entry()
        box.append(make_labeled_field("Output Table:", self._ed_output))

        # Transformation ID (with a "Create new" checkbox)
        self._ed_new_transform = Gtk.CheckButton(label="Create new transformation (ignore ID below)")
        self._ed_new_transform.connect("toggled", self._on_new_transform_toggled)
        box.append(self._ed_new_transform)

        self._ed_transform_id = Gtk.Entry()
        self._ed_transform_id.set_placeholder_text("Existing transformation ID")
        box.append(make_labeled_field("Transformation ID:", self._ed_transform_id))

        # Download directory
        dir_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        self._ed_download_dir = Gtk.Entry()
        self._ed_download_dir.set_hexpand(True)
        dir_row.append(self._ed_download_dir)
        btn_browse = Gtk.Button(label="...")
        btn_browse.connect("clicked", self._on_browse_download_dir)
        dir_row.append(btn_browse)
        box.append(make_labeled_field("Download Dir:", dir_row))

        # Auto download checkbox
        self._ed_auto_download = Gtk.CheckButton(label="Auto-download cleaned CSV after run")
        box.append(self._ed_auto_download)

        # --- SQL section ---
        sep = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        box.append(sep)

        sql_label = Gtk.Label(label="SQL Script", halign=Gtk.Align.START)
        sql_label.add_css_class("heading")
        box.append(sql_label)

        sql_hint = Gtk.Label()
        sql_hint.set_markup(
            '<span size="small" foreground="gray">'
            "The SQL is edited in the studio's main editor (full syntax "
            "highlighting, autocomplete, find/replace). Save with Ctrl+S "
            "to write it back into this profile."
            "</span>"
        )
        sql_hint.set_wrap(True)
        sql_hint.set_halign(Gtk.Align.START)
        box.append(sql_hint)

        # Preview (read-only)
        self._sql_preview = Gtk.TextView()
        self._sql_preview.set_editable(False)
        self._sql_preview.set_monospace(True)
        self._sql_preview.set_wrap_mode(Gtk.WrapMode.NONE)
        self._sql_preview.set_size_request(-1, 120)

        preview_scroll = Gtk.ScrolledWindow()
        preview_scroll.set_min_content_height(120)
        preview_scroll.set_child(self._sql_preview)
        box.append(preview_scroll)

        # SQL buttons
        sql_btns = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)

        btn_edit = Gtk.Button(label="Edit in Studio...")
        btn_edit.add_css_class("suggested-action")
        btn_edit.set_tooltip_text(
            "Open the SQL script in the main editor. Press Ctrl+S there to save "
            "it back into this profile."
        )
        btn_edit.connect("clicked", self._on_edit_sql)
        sql_btns.append(btn_edit)

        btn_reload = Gtk.Button(label="Reload")
        btn_reload.set_tooltip_text("Discard editor changes and reload from the profile")
        btn_reload.connect("clicked", lambda b: self._refresh_sql_preview())
        sql_btns.append(btn_reload)

        box.append(sql_btns)
        scroll.set_child(box)
        outer.append(scroll)
        return outer

    # ------------------------------------------------------------------
    # Tab 4 — Report
    # ------------------------------------------------------------------

    def _build_report_tab(self) -> Gtk.Box:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        set_margin(box, 16)

        self._report_view = Gtk.TextView()
        self._report_view.set_editable(False)
        self._report_view.set_monospace(True)
        self._report_view.set_wrap_mode(Gtk.WrapMode.WORD)

        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)
        scroll.set_child(self._report_view)
        box.append(scroll)

        btn_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)

        self._btn_show_file = Gtk.Button(label="Show Last File")
        self._btn_show_file.set_sensitive(False)
        self._btn_show_file.connect("clicked", self._on_show_last_file)
        btn_row.append(self._btn_show_file)

        self._last_downloaded_path: str = ""
        box.append(btn_row)

        return box

    # ==================================================================
    # Profile list handling
    # ==================================================================

    def _refresh_profile_list(self):
        self._profile_store.clear()
        for name in self._manager.list_names():
            profile = self._manager.get(name)
            if profile is None:
                continue
            transform_id = profile.transformation_id or "(new)"
            is_active = name == self._manager.active_name
            self._profile_store.append([name, profile.engine, transform_id, is_active])

    def _on_profile_selected(self, selection):
        model, tree_iter = selection.get_selected()
        if tree_iter is None:
            return
        name = model.get_value(tree_iter, 0)
        if name != self._selected_name:
            self._selected_name = name
            self._load_selected_profile()

    def _on_profile_new(self, _button):
        # Generate a unique name
        base = "New Profile"
        name = base
        i = 1
        while self._manager.get(name) is not None:
            i += 1
            name = f"{base} {i}"

        profile = KeboolaProfile(name=name)
        self._manager.add(profile)
        self._manager.set_active(name)
        self._selected_name = name
        self._refresh_profile_list()
        self._load_selected_profile()
        self._set_status(f"Created profile '{name}'")

    def _on_profile_duplicate(self, _button):
        if not self._selected_name:
            return
        src = self._manager.get(self._selected_name)
        if src is None:
            return
        base = f"{src.name} copy"
        name = base
        i = 1
        while self._manager.get(name) is not None:
            i += 1
            name = f"{base} {i}"

        import copy as _copy

        dup = _copy.deepcopy(src)
        dup.name = name
        dup.transformation_id = None  # force create new
        # Copy the token to the new keyring entry
        token = src.get_token()
        if token:
            dup.save_token(token)

        self._manager.add(dup)
        self._selected_name = name
        self._refresh_profile_list()
        self._load_selected_profile()
        self._set_status(f"Duplicated as '{name}'")

    def _on_profile_set_active(self, _button):
        if not self._selected_name:
            return
        self._manager.set_active(self._selected_name)
        self._refresh_profile_list()
        self._set_status(f"Active profile: {self._selected_name}")

    def _on_profile_remove(self, _button):
        if not self._selected_name:
            return
        name = self._selected_name
        self._manager.remove(name)
        self._selected_name = self._manager.active_name or ""
        self._refresh_profile_list()
        self._load_selected_profile()
        self._set_status(f"Removed profile '{name}'")

    # ==================================================================
    # Profile editor loading / saving
    # ==================================================================

    def _load_selected_profile(self):
        profile = self._manager.get(self._selected_name)
        if profile is None:
            return

        self._ed_name.set_text(profile.name)
        self._ed_bucket.set_text(profile.bucket)
        self._ed_input.set_text(profile.input_table)
        self._ed_output.set_text(profile.output_table)
        self._ed_transform_id.set_text(profile.transformation_id or "")
        self._ed_new_transform.set_active(profile.transformation_id is None)
        self._ed_download_dir.set_text(profile.download_dir)
        self._ed_auto_download.set_active(profile.auto_download)

        # Engine combo
        if profile.engine in self._engine_ids:
            self._ed_engine.set_active(self._engine_ids.index(profile.engine))
        else:
            self._ed_engine.set_active(0)

        # Connection tab
        self._conn_profile_label.set_text(profile.name)
        self._conn_api_url.set_text(profile.api_url)
        self._conn_token.set_text(profile.get_token())
        self._conn_status.set_text("")

        self._refresh_sql_preview()

    def _refresh_sql_preview(self):
        profile = self._manager.get(self._selected_name)
        if profile is None:
            return
        buffer = self._sql_preview.get_buffer()
        buffer.set_text(profile.sql_script or "(empty — click 'Edit in Studio...')")

    def _on_new_transform_toggled(self, check):
        enabled = not check.get_active()
        self._ed_transform_id.set_sensitive(enabled)

    def _on_browse_download_dir(self, _button):
        dialog = Gtk.FileDialog()
        dialog.set_title("Select Download Directory")

        def on_select(dialog, result):
            try:
                folder = dialog.select_folder_finish(result)
                if folder:
                    self._ed_download_dir.set_text(folder.get_path())
            except Exception:
                pass

        dialog.select_folder(self, None, on_select)

    # ==================================================================
    # SQL editor integration
    # ==================================================================

    def _on_edit_sql(self, _button):
        # First save any pending editor changes so the SQL is current
        self._on_save(None)

        if not self._selected_name:
            return

        ok = open_profile_in_editor(self._window, self._selected_name)
        if ok:
            self._set_status(
                f'Profile "{self._selected_name}" opened in the main editor. '
                "Press Ctrl+S there to save back."
            )
        else:
            self._set_status("Failed to open editor — is a window available?")

    # ==================================================================
    # Connection test
    # ==================================================================

    def _on_test_connection(self, _button):
        api_url = self._conn_api_url.get_text().strip()
        token = self._conn_token.get_text().strip()
        if not api_url or not token:
            self._conn_status.set_markup(
                '<span foreground="red">✗ Enter both API URL and token</span>'
            )
            return

        self._conn_status.set_text("Testing…")

        def do_test():
            from src.hooks.python_hooks.keboola.client import KeboolaClient, KeboolaError

            try:
                client = KeboolaClient(api_url, token)
                info = client.verify_connection()
                return True, info
            except KeboolaError as e:
                return False, str(e)
            except Exception as e:
                return False, f"Unexpected error: {e}"

        def on_done(result):
            ok, payload = result
            if ok:
                project = payload.get("owner", {}).get("name") or payload.get(
                    "project", {}
                ).get("name", "unknown")
                self._conn_status.set_markup(
                    f'<span foreground="green">✓ Connected to project: {project}</span>'
                )
            else:
                self._conn_status.set_markup(f'<span foreground="red">✗ {payload}</span>')

        run_async(do_test, on_done)

    # ==================================================================
    # Save / status
    # ==================================================================

    def _on_save(self, _button):
        if not self._selected_name:
            return

        profile = self._manager.get(self._selected_name)
        if profile is None:
            return

        # Read editor fields
        new_name = self._ed_name.get_text().strip()
        if not new_name:
            self._set_status("Profile name cannot be empty", error=True)
            return

        # If the name changed, we need to move the keyring entry
        if new_name != self._selected_name:
            old_name = self._selected_name
            old_token = profile.get_token()
            self._manager.remove(old_name)
            profile.name = new_name
            if old_token:
                profile.save_token(old_token)
            self._selected_name = new_name

        profile.bucket = self._ed_bucket.get_text().strip()
        profile.input_table = self._ed_input.get_text().strip()
        profile.output_table = self._ed_output.get_text().strip()
        profile.download_dir = self._ed_download_dir.get_text().strip()
        profile.auto_download = self._ed_auto_download.get_active()

        # Engine
        idx = self._ed_engine.get_active()
        if 0 <= idx < len(self._engine_ids):
            profile.engine = self._engine_ids[idx]

        # Transformation ID
        if self._ed_new_transform.get_active():
            profile.transformation_id = None
        else:
            profile.transformation_id = self._ed_transform_id.get_text().strip() or None

        # Connection fields (API URL + token)
        api_url = self._conn_api_url.get_text().strip()
        if api_url:
            profile.api_url = api_url
        token = self._conn_token.get_text().strip()
        if token:
            profile.save_token(token)

        # Persist
        self._manager.add(profile)
        self._manager.set_active(self._selected_name)

        self._refresh_profile_list()
        self._refresh_sql_preview()
        self._set_status(f"Saved profile '{profile.name}'")

        if self._on_saved:
            try:
                self._on_saved()
            except Exception as e:
                logger.warning(f"on_saved callback failed: {e}")

    def _set_status(self, msg: str, error: bool = False):
        color = "red" if error else "gray"
        self._status_label.set_markup(f'<span foreground="{color}">{msg}</span>')

    # ==================================================================
    # Report tab helpers (called externally by the runner)
    # ==================================================================

    def show_report(self, report: dict):
        """Display a pipeline report in the Report tab."""
        import json as _json

        text = _json.dumps(report, indent=2, default=str)
        buffer = self._report_view.get_buffer()
        buffer.set_text(text)

        path = report.get("downloaded_csv") or ""
        self._last_downloaded_path = path
        self._btn_show_file.set_sensitive(bool(path))

    def _on_show_last_file(self, _button):
        if not self._last_downloaded_path:
            return
        from src.hooks.python_hooks.keboola.client import KeboolaClient

        KeboolaClient.open_in_file_manager(self._last_downloaded_path)
