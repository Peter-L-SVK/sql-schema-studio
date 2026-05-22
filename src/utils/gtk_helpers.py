# ----------------------------------------------------------------------
# SQL Schema Studio - GTK4 Helpers (GPLv3)
# Copyright (C) 2026 Peter Leukanič
# License: GNU GPL v3+ <https://www.gnu.org/licenses/gpl-3.0.txt>
# This is free software with NO WARRANTY.
# Feel free to distribute and modify.
# ----------------------------------------------------------------------

"""GTK4 utility helpers for consistent UI building"""

from __future__ import annotations

import gi
import threading

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, GLib


def run_async(func, callback=None):
    """Run a function in a background thread, callback in main thread"""

    def _run():
        try:
            result = func()  # Call the sync function directly
            if callback:
                GLib.idle_add(callback, result)
        except Exception as e:
            print(f"Async error: {e}")
            import traceback

            traceback.print_exc()

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()


def set_margin(widget: Gtk.Widget, margin: int):
    """Set all four margins to the same value"""
    widget.set_margin_start(margin)
    widget.set_margin_end(margin)
    widget.set_margin_top(margin)
    widget.set_margin_bottom(margin)


def set_margin_horizontal(widget: Gtk.Widget, margin: int):
    """Set start and end margins"""
    widget.set_margin_start(margin)
    widget.set_margin_end(margin)


def set_margin_vertical(widget: Gtk.Widget, margin: int):
    """Set top and bottom margins"""
    widget.set_margin_top(margin)
    widget.set_margin_bottom(margin)


def make_labeled_field(label_text: str, entry: Gtk.Widget, label_width: int = 14) -> Gtk.Box:
    """Create a horizontally packed label + widget row"""
    box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)

    label = Gtk.Label(label=label_text)
    label.set_width_chars(label_width)
    label.set_halign(Gtk.Align.END)
    box.append(label)

    entry.set_hexpand(True)
    box.append(entry)

    return box


def make_button_box(buttons: list, halign: Gtk.Align = Gtk.Align.END) -> Gtk.Box:
    """Create a horizontal button row with consistent spacing"""
    box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
    box.set_halign(halign)

    for btn in buttons:
        box.append(btn)

    return box


def make_section_header(text: str) -> Gtk.Label:
    """Create a styled section header label"""
    label = Gtk.Label(label=text)
    label.add_css_class("panel-header")
    label.set_halign(Gtk.Align.START)
    return label
