# ----------------------------------------------------------------------
# SQL Schema Studio 0.8 - About Dialog (GPLv3)
# Copyright (C) 2026 Peter Leukanič
# License: GNU GPL v3+ <https://www.gnu.org/licenses/gpl-3.0.txt>
# This is free software with NO WARRANTY.
# Feel free to distribute and modify.
# ----------------------------------------------------------------------

from __future__ import annotations

from src.utils.logging import get_logger

logger = get_logger(__name__)

import platform
import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, Gdk


def show_about(parent):
    """Show the About dialog — adaptive to all desktop environments"""

    # System info for diagnostics
    system_info = (
        f"OS: {platform.system()} {platform.release()}\n"
        f"Architecture: {platform.machine()}\n"
        f"Desktop: {_detect_desktop()}\n"
        f"Python: {platform.python_version()}\n"
        f"GTK: {Gtk.MAJOR_VERSION}.{Gtk.MINOR_VERSION}.{Gtk.MICRO_VERSION}\n"
        f"PostgreSQL: psycopg3"
    )

    dialog = Gtk.AboutDialog(
        transient_for=parent,
        modal=True,
        program_name="SQL Schema Studio",
        version="0.8.0",
        comments="Intelligent PostgreSQL Management Platform\n\n"
        "Visual schema designer • SQL editor • AI analytics\n"
        "Written in Python3 and Gtk-4.0\n\n"
        "Plugin system with Python3 & Perl5 hooks",
        license_type=Gtk.License.GPL_3_0,
        website="https://github.com/Peter-L-SVK/sql-schema-studio",
        website_label="GitHub Repository",
        authors=[
            "Peter Leukanič <peter@leukanic.eu>",
        ],
        artists=[
            "Peter Leukanič",
        ],
        translator_credits=[
            " ",
        ],
        documenters=[
            "Peter Leukanič",
        ],
        copyright="© 2026 Peter Leukanič\n"
        "Licensed under GNU General Public License v3 or later\n\n"
        "This program comes with ABSOLUTELY NO WARRANTY.\n"
        "This is free software, and you are welcome to\n"
        "redistribute it under certain conditions.",
        wrap_license=True,
        system_information=system_info,
    )

    # Set icon — works on all DEs
    import os

    icon_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "resources",
        "ui",
        "icons",
        "logo.svg",
    )
    if os.path.exists(icon_path):
        texture = Gdk.Texture.new_from_filename(icon_path)
        dialog.set_logo(texture)
    else:
        dialog.set_logo_icon_name("database")

    # Add credits section
    dialog.add_credit_section(
        "Powered by",
        [
            "GTK 4 Toolkit",
            "GtkSourceView 5",
            "NumPy, pandas and scikit-learn",
            "Perl 5 (Hook System)",
            "psycopg 3 (PostgreSQL Driver)",
            "Python 3",
            "SQLite 3 (Query History and Settings)",
        ],
    )

    dialog.add_credit_section(
        "Special Thanks",
        [
            "GNOME Foundation",
            "KDE Plasma Team",
            "Linux Mint / Cinnamon Team",
            "PostgreSQL Global Development Group",
            "Python Software Foundation",
            "SQLite Consortium",
        ],
    )

    dialog.add_credit_section(
        "Icon",
        [
            "DB Browser for SQLite contributors",
            "      (sqlitebrowser.org) - GPLv3",
        ],
    )

    dialog.present()


def _detect_desktop() -> str:
    """Detect current desktop environment"""
    import os

    desktop = os.environ.get("XDG_CURRENT_DESKTOP", "Unknown")
    session = os.environ.get("GDMSESSION", "")

    if "cinnamon" in desktop.lower():
        return f"Cinnamon ({session})" if session else "Cinnamon"
    elif "gnome" in desktop.lower():
        return f"GNOME ({session})" if session else "GNOME"
    elif "mate" in desktop.lower():
        return "MATE"
    elif "xfce" in desktop.lower():
        return "XFCE"
    elif "kde" in desktop.lower():
        return "KDE Plasma"
    else:
        return desktop
