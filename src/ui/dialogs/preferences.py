# ----------------------------------------------------------------------
# SQL Schema Studio 0.9 - Preferences Dialog (GPLv3)
# Copyright (C) 2026 Peter Leukanič
# License: GNU GPL v3+ <https://www.gnu.org/licenses/gpl-3.0.txt>
# This is free software with NO WARRANTY.
# Feel free to distribute and modify.
# ----------------------------------------------------------------------

"""Preferences dialog with persistent settings."""

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("GtkSource", "5")
from gi.repository import Gtk, GtkSource, Pango

from src.utils.gtk_helpers import set_margin
from src.utils.settings import Settings
from src.utils.logging import get_logger

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
        self.set_default_size(520, 460)

        self._build_ui()
        self._load_settings()

    def _build_ui(self):
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)

        # Notebook tabs
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

        # Color scheme
        scheme_label = Gtk.Label(label="Color Scheme", halign=Gtk.Align.START)
        scheme_label.add_css_class("heading")
        scheme_label.set_margin_top(8)
        editor_page.append(scheme_label)

        self._scheme_combo = Gtk.ComboBoxText()
        manager = GtkSource.StyleSchemeManager.get_default()
        for scheme_id in manager.get_scheme_ids():
            scheme = manager.get_scheme(scheme_id)
            self._scheme_combo.append(scheme_id, scheme.get_name())
        self._scheme_combo.set_active(0)
        editor_page.append(self._scheme_combo)

        notebook.append_page(editor_page, Gtk.Label(label="Editor"))

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

    def _load_settings(self):
        """Load saved settings into widgets."""
        editor = self._settings.get_section("editor")
        general = self._settings.get_section("general")

        # Font
        font_str = editor.get("font", "Monospace 12")
        font_desc = Pango.FontDescription.from_string(font_str)
        self._font_button.set_font_desc(font_desc)

        # Tab width
        self._tab_spin.set_value(editor.get("tab_width", 4))

        # Checkboxes
        self._spaces_check.set_active(editor.get("spaces_instead_of_tabs", True))
        self._line_numbers_check.set_active(editor.get("show_line_numbers", True))
        self._highlight_line_check.set_active(editor.get("highlight_current_line", True))

        # Autocomplete
        self._autocomplete_check.set_active(editor.get("autocomplete_enabled", True))

        # Color scheme
        scheme_id = editor.get("color_scheme", "classic")
        model = self._scheme_combo.get_model()
        for i in range(len(model)):
            if model[i][0] == scheme_id:
                self._scheme_combo.set_active(i)
                break

        # General
        self._confirm_close_check.set_active(general.get("confirm_close", True))
        self._restore_session_check.set_active(general.get("restore_session", False))

    def _on_apply(self, button):
        """Save settings and apply to editor."""
        # Save font
        font_desc = self._font_button.get_font_desc()
        if font_desc:
            self._settings.set("editor", "font", font_desc.to_string())

        # Save other editor settings
        self._settings.set("editor", "tab_width", int(self._tab_spin.get_value()))
        self._settings.set("editor", "spaces_instead_of_tabs", self._spaces_check.get_active())
        self._settings.set("editor", "show_line_numbers", self._line_numbers_check.get_active())
        self._settings.set(
            "editor", "highlight_current_line", self._highlight_line_check.get_active()
        )

        # Save autocomplete
        autocomplete_enabled = self._autocomplete_check.get_active()
        self._settings.set("editor", "autocomplete_enabled", autocomplete_enabled)

        scheme_id = self._scheme_combo.get_active_id()
        if scheme_id:
            self._settings.set("editor", "color_scheme", scheme_id)

        # Save general settings
        self._settings.set("general", "confirm_close", self._confirm_close_check.get_active())
        self._settings.set("general", "restore_session", self._restore_session_check.get_active())

        self._settings.save()

        # Apply to live editor (all tabs)
        if self._editor:
            font_family = font_desc.get_family() if font_desc else "Monospace"
            font_size = (font_desc.get_size() // Pango.SCALE) if font_desc else 12

            for tab in self._editor._tabs:
                view = tab._view
                buffer = view.get_buffer()

                view.set_tab_width(int(self._tab_spin.get_value()))
                view.set_insert_spaces_instead_of_tabs(self._spaces_check.get_active())
                view.set_show_line_numbers(self._line_numbers_check.get_active())
                view.set_highlight_current_line(self._highlight_line_check.get_active())

                # Apply font via CSS
                css = f"""
                textview {{
                    font-family: {font_family};
                    font-size: {font_size}pt;
                }}
                """
                provider = Gtk.CssProvider()
                provider.load_from_data(css.encode())
                view.get_style_context().add_provider(
                    provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
                )

                # Apply color scheme
                if scheme_id:
                    manager = GtkSource.StyleSchemeManager.get_default()
                    scheme = manager.get_scheme(scheme_id)
                    if scheme:
                        buffer.set_style_scheme(scheme)

            # Apply autocomplete setting globally
            from src.ui.editor_tabs import EditorTab

            EditorTab.set_autocomplete_enabled(autocomplete_enabled)

            logger.info(f"Preferences applied to {len(self._editor._tabs)} editor tabs")

        self.close()
