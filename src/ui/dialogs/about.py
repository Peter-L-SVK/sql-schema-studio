# ----------------------------------------------------------------------
# SQL Schema Studio - About Dialog (GPLv3)
# Copyright (C) 2026 Peter Leukanič
# License: GNU GPL v3+ <https://www.gnu.org/licenses/gpl-3.0.txt>
# This is free software with NO WARRANTY.
# Feel free to distribute and modify.
# ----------------------------------------------------------------------

from __future__ import annotations

import platform
import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk


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
        version="0.1.0",
        comments="Intelligent PostgreSQL Management Platform\n\n"
        "Visual schema designer • SQL editor • AI analytics\n"
        "Plugin system with Python3 & Perl5 hooks",
        license_type=Gtk.License.GPL_3_0,
        website="https://github.com/peter-leukanic/sql-schema-studio",
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
    try:
        dialog.set_logo_icon_name("application-x-sqlite3")
    except Exception:
        pass

    # Add credits section
    dialog.add_credit_section(
        "Powered by",
        [
            "GTK4 Toolkit",
            "Python 3",
            "psycopg3 PostgreSQL Driver",
            "GtkSourceView 5",
            "NumPy / pandas / scikit-learn",
            "Perl 5 (Hook System)",
        ],
    )

    dialog.add_credit_section(
        "Special Thanks",
        [
            "PostgreSQL Global Development Group",
            "GNOME Foundation",
            "Linux Mint / Cinnamon Team",
            "Python Software Foundation",
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
