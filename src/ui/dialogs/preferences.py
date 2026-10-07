# ----------------------------------------------------------------------
# SQL Schema Studio 0.9.5 - Preferences Dialog (GPLv3)
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
from src.ui.results.terminal_themes import get_terminal_theme_names_by_variant

logger = get_logger(__name__)


# Schemes that don't declare their variant explicitly in the GtkSourceView
# metadata. Kept in sync with the most common installs (GNOME, KDE, Fedora).
_KNOWN_DARK_SCHEMES = {
    "oblivion",
    "cobalt",
    "solarized-dark",
    "monokai",
    "nord",
    "dracula",
    "kate-dark",
    "builder-dark",
    "Adwaita-dark",
}

_KNOWN_LIGHT_SCHEMES = {
    "classic",
    "tango",
    "solarized-light",
    "kate",
    "builder",
    "Adwaita",
    "gnome",
}


def _is_dark_scheme(scheme_id: str) -> bool:
    """Heuristic: is a GtkSourceView scheme dark?

    Priority:
    1. Explicit "dark" / "light" in the id.
    2. Known scheme lists.
    3. Fallback: assume light (safer for first-time users).
    """
    lower = scheme_id.lower()
    if "dark" in lower:
        return True
    if "light" in lower:
        return False
    if scheme_id in _KNOWN_DARK_SCHEMES:
        return True
    if scheme_id in _KNOWN_LIGHT_SCHEMES:
        return False
    return False


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
        self.set_default_size(520, 560)

        # Snapshots for change detection
        self._originals = {}

        # Suppress combo change handlers during programmatic updates
        self._loading = False

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

        # ---- Theme Mode ----
        theme_label = Gtk.Label(label="Theme Mode", halign=Gtk.Align.START)
        theme_label.add_css_class("heading")
        theme_label.set_margin_top(8)
        editor_page.append(theme_label)

        theme_hint = Gtk.Label()
        theme_hint.set_markup(
            '<span size="small" foreground="gray">'
            "Filters the color schemes below to match light or dark."
            "</span>"
        )
        theme_hint.set_halign(Gtk.Align.START)
        theme_hint.set_wrap(True)
        editor_page.append(theme_hint)

        self._theme_mode_combo = Gtk.ComboBoxText()
        self._theme_mode_combo.append("auto", "Auto (follow system)")
        self._theme_mode_combo.append("light", "Light")
        self._theme_mode_combo.append("dark", "Dark")
        self._theme_mode_combo.set_active_id("auto")
        self._theme_mode_combo.connect("changed", self._on_theme_mode_changed)
        editor_page.append(self._theme_mode_combo)

        # Editor color scheme
        scheme_label = Gtk.Label(label="Editor Color Scheme", halign=Gtk.Align.START)
        scheme_label.add_css_class("heading")
        scheme_label.set_margin_top(8)
        editor_page.append(scheme_label)

        self._scheme_combo = Gtk.ComboBoxText()
        self._scheme_ids = []  # parallel list — GTK4 StringList workaround
        # Populate is done by _repopulate_schemes() — called from theme_mode change
        editor_page.append(self._scheme_combo)

        notebook.append_page(editor_page, Gtk.Label(label="Editor"))

        # --- Terminal tab ---
        terminal_page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        set_margin(terminal_page, 16)

        terminal_scheme_label = Gtk.Label(label="Terminal Color Theme", halign=Gtk.Align.START)
        terminal_scheme_label.add_css_class("heading")
        terminal_page.append(terminal_scheme_label)

        terminal_hint = Gtk.Label()
        terminal_hint.set_markup(
            '<span size="small" foreground="gray">'
            "Filtered by the Theme Mode in the Editor tab."
            "</span>"
        )
        terminal_hint.set_halign(Gtk.Align.START)
        terminal_hint.set_wrap(True)
        terminal_page.append(terminal_hint)

        self._terminal_scheme_combo = Gtk.ComboBoxText()
        self._terminal_theme_ids = []  # parallel list
        # Populate is done by _repopulate_terminal_themes()
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
    # Theme mode → repopulate scheme/theme combos
    # =================================================================

    def _resolve_theme_mode(self, mode: str) -> str:
        """Map 'auto' to the actual variant using the system setting."""
        if mode != "auto":
            return mode
        try:
            gtk_settings = Gtk.Settings.get_default()
            is_dark = gtk_settings.get_property("gtk-application-prefer-dark-theme")
            return "dark" if is_dark else "light"
        except Exception:
            return "light"

    def _on_theme_mode_changed(self, combo):
        """Rebuild scheme and terminal combos to match the new theme mode."""
        if self._loading:
            return
        mode = combo.get_active_id() or "auto"
        variant = self._resolve_theme_mode(mode)
        self._repopulate_schemes(variant)
        self._repopulate_terminal_themes(variant)

    def _repopulate_schemes(self, variant: str):
        """Rebuild the editor scheme combo filtered by variant."""
        # Remember current selection so we can restore it if still valid
        current = self._scheme_combo.get_active_id()

        self._scheme_combo.remove_all()
        self._scheme_ids.clear()

        manager = GtkSource.StyleSchemeManager.get_default()
        for scheme_id in manager.get_scheme_ids():
            is_dark = _is_dark_scheme(scheme_id)
            if variant == "dark" and not is_dark:
                continue
            if variant == "light" and is_dark:
                continue
            scheme = manager.get_scheme(scheme_id)
            self._scheme_combo.append(scheme_id, scheme.get_name() or scheme_id)
            self._scheme_ids.append(scheme_id)

        # Restore selection if it survived the filter
        if current and current in self._scheme_ids:
            self._scheme_combo.set_active_id(current)
        elif self._scheme_ids:
            self._scheme_combo.set_active(0)

    def _repopulate_terminal_themes(self, variant: str):
        """Rebuild the terminal theme combo filtered by variant."""
        current = self._terminal_scheme_combo.get_active_id()

        self._terminal_scheme_combo.remove_all()
        self._terminal_theme_ids.clear()

        for theme_id, theme_name in get_terminal_theme_names_by_variant(variant):
            self._terminal_scheme_combo.append(theme_id, theme_name)
            self._terminal_theme_ids.append(theme_id)

        # Restore selection if it survived
        if current and current in self._terminal_theme_ids:
            self._terminal_scheme_combo.set_active_id(current)
        elif self._terminal_theme_ids:
            self._terminal_scheme_combo.set_active(0)

    # =================================================================
    # Load settings & snapshot originals
    # =================================================================

    def _load_settings(self):
        """Load saved settings into widgets and snapshot original values."""
        self._loading = True

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

        # Theme mode — set BEFORE populating schemes so filtering uses it
        theme_mode = editor.get("theme_mode", "auto")
        self._theme_mode_combo.set_active_id(theme_mode)

        # Manually trigger population with the loaded mode
        variant = self._resolve_theme_mode(theme_mode)
        self._repopulate_schemes(variant)
        self._repopulate_terminal_themes(variant)

        # Now select the saved scheme/theme if still present
        saved_scheme = editor.get("color_scheme", "classic")
        if saved_scheme in self._scheme_ids:
            self._scheme_combo.set_active_id(saved_scheme)

        saved_terminal = editor.get("terminal_scheme", "dark")
        if saved_terminal in self._terminal_theme_ids:
            self._terminal_scheme_combo.set_active_id(saved_terminal)

        # General
        self._confirm_close_check.set_active(general.get("confirm_close", True))
        self._restore_session_check.set_active(general.get("restore_session", False))

        self._loading = False

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
            "theme_mode": self._theme_mode_combo.get_active_id(),
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
            "theme_mode": self._theme_mode_combo.get_active_id(),
            "color_scheme": self._scheme_combo.get_active_id(),
            "terminal_scheme": self._terminal_scheme_combo.get_active_id(),
            "confirm_close": self._confirm_close_check.get_active(),
            "restore_session": self._restore_session_check.get_active(),
        }

        changed = {key: val for key, val in current.items() if val != self._originals.get(key)}

        if not changed:
            logger.debug("Preferences: nothing changed, skipping save")
            self.close()
            return

        logger.info(f"Preferences changed: {list(changed.keys())}")

        for key, val in changed.items():
            if key in ("confirm_close", "restore_session"):
                self._settings.set("general", key, val)
            else:
                self._settings.set("editor", key, val)

        self._settings.save()

        if self._editor:
            # theme_mode is not applied to the editor directly — it only
            # gates the scheme/theme dropdowns. Exclude it from side-effects.
            changed_editor = {
                k: v
                for k, v in changed.items()
                if k not in (
                    "confirm_close",
                    "restore_session",
                    "terminal_font",
                    "terminal_scheme",
                    "theme_mode",
                )
            }
            changed_terminal = {
                k: v for k, v in changed.items() if k in ("terminal_font", "terminal_scheme")
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

        self._snapshot_originals()
        self.close()
