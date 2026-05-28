# ----------------------------------------------------------------------
# SQL Schema Studio 0.5 - Settings Manager (GPLv3)
# Copyright (C) 2026 Peter Leukanič
# License: GNU GPL v3+ <https://www.gnu.org/licenses/gpl-3.0.txt>
# This is free software with NO WARRANTY.
# Feel free to distribute and modify.
# ----------------------------------------------------------------------

"""Persistent user settings stored in ~/.config/sql-schema-studio/"""

import json
from pathlib import Path

from src.utils.logging import get_logger

logger = get_logger(__name__)

CONFIG_DIR = Path.home() / ".config" / "sql-schema-studio"
SETTINGS_FILE = CONFIG_DIR / "settings.json"

DEFAULTS = {
    "editor": {
        "font": "Monospace 12",
        "tab_width": 4,
        "spaces_instead_of_tabs": True,
        "show_line_numbers": True,
        "highlight_current_line": True,
        "color_scheme": "classic",
    },
    "general": {
        "confirm_close": True,
        "restore_session": False,
    },
    "window": {
        "width": 1200,
        "height": 800,
        "browser_width": 220,
    },
}


class Settings:
    """Persistent user settings backed by JSON."""

    def __init__(self):
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        self._data: dict[str, dict] = self._load()

    def _load(self) -> dict:
        """Load settings from disk or return defaults."""
        if SETTINGS_FILE.exists():
            try:
                with open(SETTINGS_FILE, "r") as f:
                    data = json.load(f)
                return self._deep_merge(DEFAULTS.copy(), data)
            except Exception as e:
                logger.warning(f"Failed to load settings: {e}")
        return DEFAULTS.copy()

    def _deep_merge(self, base: dict, override: dict) -> dict:
        """Recursively merge override into base, keeping base keys that don't exist in override."""
        for key, value in override.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                base[key] = self._deep_merge(base[key], value)
            else:
                base[key] = value
        return base

    def save(self):
        """Save settings to disk."""
        try:
            with open(SETTINGS_FILE, "w") as f:
                json.dump(self._data, f, indent=2)
            logger.debug("Settings saved")
        except Exception as e:
            logger.error(f"Failed to save settings: {e}")

    def get(self, section: str, key: str, default=None):
        """Get a setting value."""
        return self._data.get(section, {}).get(key, default)

    def set(self, section: str, key: str, value):
        """Set a setting value."""
        if section not in self._data:
            self._data[section] = {}
        self._data[section][key] = value

    def get_section(self, section: str) -> dict:
        """Get an entire settings section."""
        return self._data.get(section, {})
