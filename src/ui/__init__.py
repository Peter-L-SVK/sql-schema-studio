# ----------------------------------------------------------------------
# SQL Schema Studio 0.9 - Ui / __Init__ (GPLv3)
# Copyright (C) 2026 Peter Leukanič
# License: GNU GPL v3+ <https://www.gnu.org/licenses/gpl-3.0.txt>
# This is free software with NO WARRANTY.
# Feel free to distribute and modify.
# ----------------------------------------------------------------------

"""UI package exports."""

from src.ui.ai_tools import AIToolsPopover
from src.ui.results import ResultsPanel
from src.ui.editor import EditorTabs, EditorTab
from src.ui.toolbar import Toolbar
from src.ui.statusbar import StatusBar
from src.ui.browser import DatabaseBrowser
from src.ui.menubar import build_menubar

__all__ = [
    "AIToolsPopover",
    "ResultsPanel",
    "EditorTabs",
    "EditorTab",
    "Toolbar",
    "StatusBar",
    "DatabaseBrowser",
    "build_menubar",
]
