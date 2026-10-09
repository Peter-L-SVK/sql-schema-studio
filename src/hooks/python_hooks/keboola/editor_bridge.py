# ----------------------------------------------------------------------
# SQL Schema Studio 0.9.5 - Keboola Editor Bridge (GPLv3)
# Copyright (C) 2026 Peter Leukanič
# License: GNU GPL v3+ <https://www.gnu.org/licenses/gpl-3.0.txt>
# This is free software with NO WARRANTY.
# Feel free to distribute and modify.
# ----------------------------------------------------------------------

"""Bridge between Keboola profiles and the main SQL editor.

A profile's SQL script is edited in the studio's main editor (the same
one used for regular queries). To route Save (Ctrl+S) back into the
profile instead of a file on disk, the tab's file_path is set to a
magic URI of the form "keboola://<profile>/sql".
"""

from __future__ import annotations

from src.utils.logging import get_logger

logger = get_logger(__name__)

KEBOOLA_URI_PREFIX = "keboola://"


def make_keboola_uri(profile_name: str) -> str:
    """Build the magic URI for a profile's SQL script."""
    return f"{KEBOOLA_URI_PREFIX}{profile_name}/sql"


def is_keboola_uri(path: str | None) -> bool:
    """Check whether a tab's file_path points to a Keboola profile."""
    if path is None:
        return False
    return path.startswith(KEBOOLA_URI_PREFIX)


def profile_name_from_uri(uri: str) -> str | None:
    """Extract the profile name from a keboola:// URI."""
    if not is_keboola_uri(uri):
        return None
    body = uri[len(KEBOOLA_URI_PREFIX) :]
    if body.endswith("/sql"):
        body = body[:-4]
    return body or None


def open_profile_in_editor(window, profile_name: str) -> bool:
    """Open (or focus) a Keboola profile's SQL script in the main editor.

    Walks up the transient_for chain from `window` until it finds a window
    that has an `editor` attribute (i.e. the MainWindow). This lets us call
    this function from nested dialogs like HookManagerDialog → KeboolaConfigDialog
    without passing MainWindow explicitly.

    Returns True if a tab is now focused, False otherwise.
    """
    from src.hooks.python_hooks.keboola.profiles import ProfileManager

    # Find the MainWindow by walking the transient_for chain
    target = window
    seen: set[int] = set()
    while target is not None and id(target) not in seen:
        seen.add(id(target))
        if hasattr(target, "editor"):
            break
        target = target.get_transient_for() if hasattr(target, "get_transient_for") else None

    if target is None or not hasattr(target, "editor"):
        logger.warning("Cannot open editor: no MainWindow with .editor found in parent chain")
        return False

    manager = ProfileManager()
    profile = manager.get(profile_name)
    if profile is None:
        logger.warning(f"Profile '{profile_name}' not found")
        return False

    uri = make_keboola_uri(profile_name)
    editor = target.editor

    # Focus existing tab for this profile
    for i, tab in enumerate(editor._tabs):
        if tab.file_path == uri:
            editor._notebook.set_current_page(i)
            tab._view.grab_focus()
            logger.info(f"Focused existing editor tab for profile '{profile_name}'")
            return True

    # Create a new tab with the profile's SQL
    content = profile.sql_script or (
        "-- Write your transformation SQL here.\n"
        "-- Save with Ctrl+S to write it back to the profile.\n"
    )
    tab = editor.add_tab(title=f"keboola_{profile_name}.sql", content=content)
    tab.file_path = uri
    tab._original_title = f"keboola_{profile_name}.sql"
    tab._view.grab_focus()

    logger.info(f"Opened profile '{profile_name}' SQL in a new editor tab")
    return True


def save_sql_to_profile(profile_name: str, sql: str) -> bool:
    """Write the SQL back into the profile and persist it.

    Returns True on success, False if the profile no longer exists.
    """
    from src.hooks.python_hooks.keboola.profiles import ProfileManager

    manager = ProfileManager()
    profile = manager.get(profile_name)
    if profile is None:
        logger.error(f"Cannot save SQL: profile '{profile_name}' not found")
        return False

    profile.sql_script = sql
    manager.add(profile)
    logger.info(f"Saved SQL to Keboola profile '{profile_name}' ({len(sql)} chars)")
    return True
