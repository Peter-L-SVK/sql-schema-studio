# ----------------------------------------------------------------------
# SQL Schema Studio 0.6 - Menu Bar (GPLv3)
# Copyright (C) 2026 Peter Leukanič
# License: GNU GPL v3+ <https://www.gnu.org/licenses/gpl-3.0.txt>
# This is free software with NO WARRANTY.
# Feel free to distribute and modify.
# ----------------------------------------------------------------------

"""Application menu bar"""

from __future__ import annotations
import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, Gio


def build_menubar():
    """Create the application menu bar"""
    menubar = Gio.Menu()

    # File
    file_menu = Gio.Menu()
    file_menu.append("New Connection...", "app.new_connection")
    file_menu.append("Open Schema File...", "app.open_schema")
    file_menu.append("Save Schema", "app.save_schema")
    file_menu.append("Save Schema As...", "app.save_schema_as")
    file_menu.append_section(None, Gio.Menu())
    file_menu.append("Export", "app.export")
    file_menu.append_section(None, Gio.Menu())
    file_menu.append("Quit", "app.quit")

    # Edit
    edit_menu = Gio.Menu()
    edit_menu.append("Undo", "app.undo")
    edit_menu.append("Redo", "app.redo")
    edit_menu.append_section(None, Gio.Menu())
    edit_menu.append("Cut", "app.cut")
    edit_menu.append("Copy", "app.copy")
    edit_menu.append("Paste", "app.paste")
    edit_menu.append_section(None, Gio.Menu())
    edit_menu.append("Preferences", "app.preferences")

    # View
    view_menu = Gio.Menu()
    view_menu.append("Database Browser", "app.view_browser")
    view_menu.append("SQL Editor", "app.view_editor")
    view_menu.append("Results Panel", "app.view_results")
    view_menu.append_section(None, Gio.Menu())
    view_menu.append("Hook Manager", "app.view_hooks")
    view_menu.append("Analytics Dashboard", "app.view_analytics")

    # Query
    query_menu = Gio.Menu()
    query_menu.append("Execute (F5)", "app.query_execute")
    query_menu.append("Execute Selection", "app.query_execute_selection")
    query_menu.append_section(None, Gio.Menu())
    query_menu.append("Format SQL", "app.query_format")
    query_menu.append("Explain Analyze", "app.query_explain")
    query_menu.append("Query History", "app.query_history")

    # Tools
    tools_menu = Gio.Menu()
    tools_menu.append("Schema Designer", "app.tools_schema_designer")
    tools_menu.append("Migration Generator", "app.tools_migration")
    tools_menu.append_section(None, Gio.Menu())
    tools_menu.append("AI Index Advisor", "app.tools_index_advisor")
    tools_menu.append("Query Analyzer", "app.tools_query_analyzer")

    # Help
    help_menu = Gio.Menu()
    help_menu.append("Documentation", "app.help_docs")
    help_menu.append("About", "app.about")

    menubar.append_submenu("File", file_menu)
    menubar.append_submenu("Edit", edit_menu)
    menubar.append_submenu("View", view_menu)
    menubar.append_submenu("Query", query_menu)
    menubar.append_submenu("Tools", tools_menu)
    menubar.append_submenu("Help", help_menu)

    widget = Gtk.PopoverMenuBar()
    widget.set_menu_model(menubar)
    return widget
