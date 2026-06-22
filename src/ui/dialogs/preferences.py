# ----------------------------------------------------------------------
# SQL Schema Studio 0.9 - Preferences Dialog (GPLv3)
# Copyright (C) 2026 Peter Leukanič
# License: GNU GPL v3+ <https://www.gnu.org/licenses/gpl-3.0.txt>
# This is free software with NO WARRANTY.
# Feel free to distribute and modify.
# ----------------------------------------------------------------------

"""Preferences dialog with persistent settings."""

import os
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("GtkSource", "5")
from gi.repository import Gtk, GtkSource, Pango

from src.utils.gtk_helpers import set_margin
from src.utils.settings import Settings
from src.utils.logging import get_logger
from src.ui.results import ResultsPanel

logger = get_logger(__name__)


class PreferencesDialog(Gtk.Window):
    """Preferences dialog with editor and general settings."""

    def __init__(self, parent, editor=None):
        super().__init__(
            title="Preferences",
            transient_for=parent,
            modal=True,
        )
        self._editor = editor
        self._settings = Settings()
        self.set_default_size(520, 500)

        # Snapshots for change detection
        self._originals = {}

        self._build_ui()
        self._load_settings()

    # =================================================================
    # UI construction
    # =================================================================

    def _build_ui(self):
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)

        notebook = Gtk.Notebook()
        set_margin(notebook, 12)

        # --- Editor tab ---
        editor_page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        set_margin(editor_page, 16)

        # Font
        font_label = Gtk.Label(label="Font", halign=Gtk.Align.START)
        font_label.add_css_class("heading")
        editor_page.append(font_label)
        font_dialog = Gtk.FontDialog()
        font_dialog.set_title("Select Editor Font")
        self._font_button = Gtk.FontDialogButton(dialog=font_dialog)
        editor_page.append(self._font_button)

        # Tab width
        tab_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        tab_box.append(Gtk.Label(label="Tab width:"))
        self._tab_spin = Gtk.SpinButton.new_with_range(2, 8, 1)
        self._tab_spin.set_value(4)
        tab_box.append(self._tab_spin)
        editor_page.append(tab_box)

        # Checkboxes
        self._spaces_check = Gtk.CheckButton(label="Insert spaces instead of tabs")
        editor_page.append(self._spaces_check)
        self._line_numbers_check = Gtk.CheckButton(label="Show line numbers")
        editor_page.append(self._line_numbers_check)
        self._highlight_line_check = Gtk.CheckButton(label="Highlight current line")
        editor_page.append(self._highlight_line_check)

        # Autocomplete
        autocomplete_label = Gtk.Label(label="Autocomplete", halign=Gtk.Align.START)
        autocomplete_label.add_css_class("heading")
        autocomplete_label.set_margin_top(8)
        editor_page.append(autocomplete_label)
        self._autocomplete_check = Gtk.CheckButton(label="Enable SQL keyword autocomplete")
        editor_page.append(self._autocomplete_check)

        # Editor color scheme
        scheme_label = Gtk.Label(label="Editor Color Scheme", halign=Gtk.Align.START)
        scheme_label.add_css_class("heading")
        scheme_label.set_margin_top(8)
        editor_page.append(scheme_label)

        self._scheme_combo = Gtk.ComboBoxText()
        self._scheme_ids = []  # parallel list — GTK4 StringList workaround
        manager = GtkSource.StyleSchemeManager.get_default()
        manager.set_search_path(
            [
                "/usr/share/gtksourceview-5/styles",
                "/usr/share/gtksourceview-4/styles",
                "/usr/share/gtksourceview-3.0/styles",
                os.path.expanduser("~/.local/share/gtksourceview-5/styles"),
                os.path.expanduser("~/.local/share/gtksourceview-3.0/styles"),
            ]
        )
        for scheme_id in manager.get_scheme_ids():
            scheme = manager.get_scheme(scheme_id)
            self._scheme_combo.append(scheme_id, scheme.get_name() or scheme_id)
            self._scheme_ids.append(scheme_id)
        self._scheme_combo.set_active(0)
        editor_page.append(self._scheme_combo)

        notebook.append_page(editor_page, Gtk.Label(label="Editor"))

        # --- Terminal tab ---
        terminal_page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        set_margin(terminal_page, 16)

        terminal_scheme_label = Gtk.Label(label="Terminal Color Theme", halign=Gtk.Align.START)
        terminal_scheme_label.add_css_class("heading")
        terminal_page.append(terminal_scheme_label)

        self._terminal_scheme_combo = Gtk.ComboBoxText()
        self._terminal_theme_ids = []  # parallel list

        for theme_id, theme_name in ResultsPanel.get_theme_names():
            self._terminal_scheme_combo.append(theme_id, theme_name)
            self._terminal_theme_ids.append(theme_id)

        terminal_page.append(self._terminal_scheme_combo)

        # Terminal font
        terminal_font_label = Gtk.Label(label="Terminal Font", halign=Gtk.Align.START)
        terminal_font_label.add_css_class("heading")
        terminal_font_label.set_margin_top(8)
        terminal_page.append(terminal_font_label)

        terminal_font_dialog = Gtk.FontDialog()
        terminal_font_dialog.set_title("Select Terminal Font")
        self._terminal_font_button = Gtk.FontDialogButton(dialog=terminal_font_dialog)
        terminal_page.append(self._terminal_font_button)

        notebook.append_page(terminal_page, Gtk.Label(label="Terminal"))

        # --- General tab ---
        general_page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        set_margin(general_page, 16)

        self._confirm_close_check = Gtk.CheckButton(label="Warn when closing with unsaved changes")
        general_page.append(self._confirm_close_check)

        self._restore_session_check = Gtk.CheckButton(label="Restore last session on startup")
        general_page.append(self._restore_session_check)

        notebook.append_page(general_page, Gtk.Label(label="General"))

        main_box.append(notebook)

        # Buttons
        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        button_box.set_halign(Gtk.Align.END)
        set_margin(button_box, 12)

        btn_close = Gtk.Button(label="Close")
        btn_close.connect("clicked", lambda b: self.close())
        button_box.append(btn_close)

        self._btn_save = Gtk.Button(label="Apply")
        self._btn_save.add_css_class("suggested-action")
        self._btn_save.connect("clicked", self._on_apply)
        button_box.append(self._btn_save)

        main_box.append(button_box)
        self.set_child(main_box)

    # =================================================================
    # Load settings & snapshot originals
    # =================================================================

    def _load_settings(self):
        """Load saved settings into widgets and snapshot original values."""
        editor = self._settings.get_section("editor")
        general = self._settings.get_section("general")

        # Font
        font_str = editor.get("font", "Monospace 12")
        font_desc = Pango.FontDescription.from_string(font_str)
        self._font_button.set_font_desc(font_desc)

        # Terminal font
        terminal_font_str = editor.get("terminal_font", "Monospace 10")
        terminal_font_desc = Pango.FontDescription.from_string(terminal_font_str)
        self._terminal_font_button.set_font_desc(terminal_font_desc)

        # Tab width
        self._tab_spin.set_value(editor.get("tab_width", 4))

        # Checkboxes
        self._spaces_check.set_active(editor.get("spaces_instead_of_tabs", True))
        self._line_numbers_check.set_active(editor.get("show_line_numbers", True))
        self._highlight_line_check.set_active(editor.get("highlight_current_line", True))
        self._autocomplete_check.set_active(editor.get("autocomplete_enabled", True))

        # Editor color scheme — use parallel ID list (GTK4 StringList fix)
        scheme_id = editor.get("color_scheme", "classic")
        try:
            idx = self._scheme_ids.index(scheme_id)
            self._scheme_combo.set_active(idx)
        except ValueError:
            self._scheme_combo.set_active(0)

        # Terminal theme — use parallel ID list (GTK4 StringList fix)
        terminal_theme = editor.get("terminal_scheme", "dark")
        try:
            idx = self._terminal_theme_ids.index(terminal_theme)
            self._terminal_scheme_combo.set_active(idx)
        except ValueError:
            self._terminal_scheme_combo.set_active(0)

        # General
        self._confirm_close_check.set_active(general.get("confirm_close", True))
        self._restore_session_check.set_active(general.get("restore_session", False))

        # Snapshot for change detection
        self._snapshot_originals()

    def _snapshot_originals(self):
        """Capture current widget values so _on_apply can compare."""
        font_desc = self._font_button.get_font_desc()
        terminal_font_desc = self._terminal_font_button.get_font_desc()

        self._originals = {
            "font": font_desc.to_string() if font_desc else None,
            "terminal_font": terminal_font_desc.to_string() if terminal_font_desc else None,
            "tab_width": int(self._tab_spin.get_value()),
            "spaces_instead_of_tabs": self._spaces_check.get_active(),
            "show_line_numbers": self._line_numbers_check.get_active(),
            "highlight_current_line": self._highlight_line_check.get_active(),
            "autocomplete_enabled": self._autocomplete_check.get_active(),
            "color_scheme": self._scheme_combo.get_active_id(),
            "terminal_scheme": self._terminal_scheme_combo.get_active_id(),
            "confirm_close": self._confirm_close_check.get_active(),
            "restore_session": self._restore_session_check.get_active(),
        }

    # =================================================================
    # Apply (delta-only)
    # =================================================================

    def _on_apply(self, button):
        """Save and apply only settings that actually changed."""
        window = self.get_transient_for()

        # Read current values
        font_desc = self._font_button.get_font_desc()
        terminal_font_desc = self._terminal_font_button.get_font_desc()

        current = {
            "font": font_desc.to_string() if font_desc else None,
            "terminal_font": terminal_font_desc.to_string() if terminal_font_desc else None,
            "tab_width": int(self._tab_spin.get_value()),
            "spaces_instead_of_tabs": self._spaces_check.get_active(),
            "show_line_numbers": self._line_numbers_check.get_active(),
            "highlight_current_line": self._highlight_line_check.get_active(),
            "autocomplete_enabled": self._autocomplete_check.get_active(),
            "color_scheme": self._scheme_combo.get_active_id(),
            "terminal_scheme": self._terminal_scheme_combo.get_active_id(),
            "confirm_close": self._confirm_close_check.get_active(),
            "restore_session": self._restore_session_check.get_active(),
        }

        # Determine what changed
        changed = {
            key: val
            for key, val in current.items()
            if val != self._originals.get(key)
        }

        if not changed:
            logger.debug("Preferences: nothing changed, skipping save")
            self.close()
            return

        logger.info(f"Preferences changed: {list(changed.keys())}")

        # Persist only changed keys
        for key, val in changed.items():
            if key in ("confirm_close", "restore_session"):
                self._settings.set("general", key, val)
            else:
                self._settings.set("editor", key, val)

        self._settings.save()

        # Apply editor side-effects only for changed editor keys
        if self._editor:
            changed_editor = {
                k: v for k, v in changed.items()
                if k not in ("confirm_close", "restore_session", "terminal_font", "terminal_scheme")
            }
            changed_terminal = {
                k: v for k, v in changed.items()
                if k in ("terminal_font", "terminal_scheme")
            }

            if changed_editor:
                font_family = font_desc.get_family() if font_desc else "Monospace"
                font_size = (font_desc.get_size() // Pango.SCALE) if font_desc else 12

                for tab in self._editor._tabs:
                    view = tab._view
                    buffer = view.get_buffer()

                    if "tab_width" in changed_editor:
                        view.set_tab_width(current["tab_width"])
                    if "spaces_instead_of_tabs" in changed_editor:
                        view.set_insert_spaces_instead_of_tabs(current["spaces_instead_of_tabs"])
                    if "show_line_numbers" in changed_editor:
                        view.set_show_line_numbers(current["show_line_numbers"])
                    if "highlight_current_line" in changed_editor:
                        view.set_highlight_current_line(current["highlight_current_line"])

                    if "font" in changed_editor:
                        css = (
                            "textview {"
                            f"  font-family: {font_family};"
                            f"  font-size: {font_size}pt;"
                            "}"
                        )
                        provider = Gtk.CssProvider()
                        provider.load_from_data(css.encode())
                        view.get_style_context().add_provider(
                            provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
                        )

                    if "color_scheme" in changed_editor and current["color_scheme"]:
                        manager = GtkSource.StyleSchemeManager.get_default()
                        scheme = manager.get_scheme(current["color_scheme"])
                        if scheme:
                            buffer.set_style_scheme(scheme)

                if "autocomplete_enabled" in changed_editor:
                    from src.ui.editor_tabs import EditorTab
                    EditorTab.set_autocomplete_enabled(current["autocomplete_enabled"])

                logger.info(
                    f"Editor preferences applied to {len(self._editor._tabs)} tabs: "
                    f"{list(changed_editor.keys())}"
                )

            if changed_terminal and window and hasattr(window, "results"):
                if "terminal_font" in changed_terminal and window.results.terminal:
                    window.results.terminal.set_font(terminal_font_desc)
                if "terminal_scheme" in changed_terminal and current["terminal_scheme"]:
                    window.results.apply_terminal_scheme(current["terminal_scheme"])
                logger.info(f"Terminal preferences applied: {list(changed_terminal.keys())}")

        # Update snapshot so next Apply is also delta-only
        self._snapshot_originals()
        self.close()
