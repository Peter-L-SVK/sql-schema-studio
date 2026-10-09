# ----------------------------------------------------------------------
# SQL Schema Studio 0.9.5 - Keboola Profile Manager (GPLv3)
# Copyright (C) 2026 Peter Leukanič
# License: GNU GPL v3+ <https://www.gnu.org/licenses/gpl-3.0.txt>
# This is free software with NO WARRANTY.
# Feel free to distribute and modify.
# ----------------------------------------------------------------------

"""Keboola profile management — JSON metadata + keyring for secrets.

Profiles live in ~/.config/sql-schema-studio/keboola_profiles.json.
The API token is NEVER stored in JSON — it lives in the system keyring
under service name "sql-schema-studio-keboola" with key "<profile>/token".
"""

from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional

import keyring

from src.hooks.python_hooks.keboola.engines import ENGINES
from src.utils.logging import get_logger

logger = get_logger(__name__)

KEYRING_SERVICE = "sql-schema-studio-keboola"
CONFIG_DIR = Path.home() / ".config" / "sql-schema-studio"
PROFILES_FILE = CONFIG_DIR / "keboola_profiles.json"


@dataclass
class KeboolaProfile:
    """A single Keboola pipeline profile."""

    name: str
    engine: str = "bigquery"  # "bigquery" | "snowflake"
    api_url: str = "https://connection.keboola.com"
    bucket: str = "in.c-sql-schema-studio"
    input_table: str = "csv_input"
    output_table: str = "out_cleaned_data"

    # Transformation: None means "create new", a string means "update existing"
    transformation_id: Optional[str] = None

    # SQL script (small — stored in JSON; for large scripts consider a separate file)
    sql_script: str = ""

    # Output options
    auto_download: bool = True
    download_dir: str = str(Path.home() / "Documents")

    # --- Keyring helpers (token is NOT stored in JSON) ---

    def save_token(self, token: str) -> None:
        """Store API token in system keyring."""
        try:
            keyring.set_password(KEYRING_SERVICE, f"{self.name}/token", token)
            logger.info(f"Token saved for profile '{self.name}'")
        except Exception as e:
            logger.warning(f"Could not save token to keyring: {e}")

    def get_token(self) -> str:
        """Retrieve API token from system keyring."""
        try:
            saved = keyring.get_password(KEYRING_SERVICE, f"{self.name}/token")
            return saved or ""
        except Exception as e:
            logger.warning(f"Could not retrieve token from keyring: {e}")
            return ""

    def delete_token(self) -> None:
        """Remove token from system keyring."""
        try:
            keyring.delete_password(KEYRING_SERVICE, f"{self.name}/token")
        except Exception:
            pass

    def validate(self) -> list[str]:
        """Return list of validation errors (empty if valid)."""
        errors: list[str] = []
        if not self.name.strip():
            errors.append("Profile name is required")
        if self.engine not in ENGINES:
            errors.append(f"Unknown engine: {self.engine}")
        if not self.api_url.strip():
            errors.append("API URL is required")
        if not self.bucket.strip():
            errors.append("Bucket is required")
        if not self.input_table.strip():
            errors.append("Input table name is required")
        if not self.output_table.strip():
            errors.append("Output table name is required")
        if not self.get_token():
            errors.append("API token is not set")
        return errors

    def to_dict(self) -> dict:
        """Serialize profile without the token."""
        return asdict(self)


class ProfileManager:
    """Load, save, and manage Keboola profiles."""

    def __init__(self):
        self._profiles: dict[str, KeboolaProfile] = {}
        self._active: str = ""
        self._load()

    # --- Persistence ---

    def _load(self) -> None:
        """Load profiles from JSON on disk."""
        if not PROFILES_FILE.exists():
            logger.debug("No Keboola profiles file found, starting fresh")
            return
        try:
            with open(PROFILES_FILE, "r") as f:
                data = json.load(f)
            for name, raw in data.get("profiles", {}).items():
                self._profiles[name] = KeboolaProfile(**raw)
            self._active = data.get("active_profile", "")
            logger.info(f"Loaded {len(self._profiles)} Keboola profiles")
        except Exception as e:
            logger.error(f"Failed to load Keboola profiles: {e}")

    def _save(self) -> None:
        """Save profiles to JSON on disk (token NOT included)."""
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        try:
            data = {
                "active_profile": self._active,
                "profiles": {name: prof.to_dict() for name, prof in self._profiles.items()},
            }
            with open(PROFILES_FILE, "w") as f:
                json.dump(data, f, indent=2)
            logger.debug("Keboola profiles saved")
        except Exception as e:
            logger.error(f"Failed to save Keboola profiles: {e}")

    # --- CRUD ---

    def add(self, profile: KeboolaProfile) -> None:
        """Add or replace a profile, save to disk."""
        self._profiles[profile.name] = profile
        if not self._active:
            self._active = profile.name
        self._save()

    def remove(self, name: str) -> None:
        """Remove a profile and its token, save to disk."""
        if name in self._profiles:
            self._profiles[name].delete_token()
            del self._profiles[name]
        if self._active == name:
            self._active = next(iter(self._profiles), "")
        self._save()

    def get(self, name: str) -> Optional[KeboolaProfile]:
        return self._profiles.get(name)

    def list_names(self) -> list[str]:
        return list(self._profiles.keys())

    # --- Active profile ---

    @property
    def active_name(self) -> str:
        return self._active

    @property
    def active(self) -> Optional[KeboolaProfile]:
        if not self._active:
            return None
        return self._profiles.get(self._active)

    def set_active(self, name: str) -> None:
        if name in self._profiles:
            self._active = name
            self._save()
