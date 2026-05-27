# ----------------------------------------------------------------------
# SQL Schema Studio 0.4 - Database Connector (GPLv3)
# Copyright (C) 2025-2026 Peter Leukanič
# License: GNU GPL v3+ <https://www.gnu.org/licenses/gpl-3.0.txt>
# This is free software with NO WARRANTY.
# Feel free to distribute and modify.
# ----------------------------------------------------------------------

from __future__ import annotations

import keyring
import psycopg
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any

from src.utils.logging import get_logger
from src.config import (
    DEFAULT_HOST,
    DEFAULT_PORT,
    DEFAULT_DATABASE,
    DEFAULT_USER,
    EXCLUDED_SCHEMAS,
)

logger = get_logger(__name__)
SERVICE_NAME = "sql-schema-studio"


@dataclass
class ConnectionProfile:
    """Database connection configuration. Passwords stored in system keyring."""

    name: str
    host: str = DEFAULT_HOST
    port: int = DEFAULT_PORT
    database: str = DEFAULT_DATABASE
    username: str = DEFAULT_USER
    password: str = field(default="", repr=False)
    ssl_mode: str = "prefer"

    def __post_init__(self):
        if self.password:
            self.save_password(self.password)

    def _get_key(self) -> str:
        return f"{self.name}/{self.username}"

    def save_password(self, password: str) -> None:
        """Store password in system keyring."""
        try:
            keyring.set_password(SERVICE_NAME, self._get_key(), password)
        except Exception as e:
            logger.warning(f"Could not save password to keyring: {e}")

    def get_password(self) -> str:
        """Retrieve password from system keyring."""
        try:
            saved = keyring.get_password(SERVICE_NAME, self._get_key())
            return saved or ""
        except Exception as e:
            logger.warning(f"Could not retrieve password from keyring: {e}")
            return ""

    def delete_password(self) -> None:
        """Remove password from system keyring."""
        try:
            keyring.delete_password(SERVICE_NAME, self._get_key())
        except Exception:
            pass

    def to_dict(self) -> dict:
        """Serialize without password."""
        return {
            "name": self.name,
            "host": self.host,
            "port": self.port,
            "database": self.database,
            "username": self.username,
            "ssl_mode": self.ssl_mode,
        }


class DatabaseConnector:
    """Manages PostgreSQL connections with keyring-backed credentials."""

    def __init__(self):
        self._profiles: Dict[str, ConnectionProfile] = {}
        self._active_profile: Optional[str] = None
        self._active_profile_obj: Optional[ConnectionProfile] = None

    @property
    def is_connected(self) -> bool:
        return self._active_profile is not None

    @property
    def active_profile_name(self) -> str | None:
        return self._active_profile

    def add_profile(self, profile: ConnectionProfile):
        self._profiles[profile.name] = profile

    def remove_profile(self, name: str):
        if name in self._profiles:
            self._profiles[name].delete_password()
            del self._profiles[name]
        if self._active_profile == name:
            self._active_profile = None
            self._active_profile_obj = None

    def list_profiles(self) -> List[str]:
        return list(self._profiles.keys())

    def get_profile(self, name: str) -> Optional[ConnectionProfile]:
        return self._profiles.get(name)

    def connect_sync(self, profile_or_name) -> bool:
        """Verify credentials with a quick sync ping, then mark as active."""
        if isinstance(profile_or_name, str):
            profile = self._profiles.get(profile_or_name)
        else:
            profile = profile_or_name
            self._profiles[profile.name] = profile

        if not profile:
            return False

        try:
            with psycopg.connect(self._build_conn_string(profile)) as conn:
                conn.execute("SELECT 1")
            self._active_profile = profile.name
            self._active_profile_obj = profile
            return True
        except Exception as e:
            logger.error(f"Connect error: {e}")
            return False

    def disconnect(self, profile_name: str | None = None) -> None:
        """Clear the active connection state."""
        name = profile_name or self._active_profile
        if name and self._active_profile == name:
            self._active_profile = None
            self._active_profile_obj = None

    def _build_conn_string(self, profile: ConnectionProfile) -> str:
        return (
            f"host={profile.host} port={profile.port} "
            f"dbname={profile.database} user={profile.username} "
            f"password={profile.get_password()}"
        )

    def _get_conn_string(self) -> str:
        """Build connection string for the active profile."""
        if not self._active_profile_obj:
            raise RuntimeError("No active connection")
        return self._build_conn_string(self._active_profile_obj)

    def execute_sync(self, query: str, params: tuple | None = None) -> list[dict[str, Any]]:
        """Execute a query from a background thread using a direct sync connection."""
        conn_string = self._get_conn_string()

        with psycopg.connect(conn_string) as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                if cur.description:
                    columns = [desc[0] for desc in cur.description]
                    rows = cur.fetchall()
                    return [dict(zip(columns, row)) for row in rows]
                return []

    def get_schemas(self) -> List[str]:
        results = self.execute_sync(
            "SELECT schema_name FROM information_schema.schemata "
            "WHERE schema_name != ALL(%s) "
            "ORDER BY schema_name",
            (list(EXCLUDED_SCHEMAS),),
        )
        return [r["schema_name"] for r in results]

    def get_tables(self, schema: str = "public") -> List[Dict]:
        return self.execute_sync(
            "SELECT table_name, table_type "
            "FROM information_schema.tables "
            "WHERE table_schema = %s "
            "ORDER BY table_name",
            (schema,),
        )
