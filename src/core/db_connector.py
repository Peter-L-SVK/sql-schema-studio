# ----------------------------------------------------------------------
# SQL Schema Studio - Database Connector (GPLv3)
# Copyright (C) 2025-2026 Peter Leukanič
# License: GNU GPL v3+ <https://www.gnu.org/licenses/gpl-3.0.txt>
# This is free software with NO WARRANTY.
# Feel free to distribute and modify.
# ----------------------------------------------------------------------

from __future__ import annotations

import psycopg
from dataclasses import dataclass
from typing import Optional, List, Dict, Any


@dataclass
class ConnectionProfile:
    name: str
    host: str = "localhost"
    port: int = 5432
    database: str = "postgres"
    username: str = "postgres"
    password: str = ""
    ssl_mode: str = "prefer"


class DatabaseConnector:
    def __init__(self):
        self._profiles: Dict[str, ConnectionProfile] = {}
        self._active_profile: Optional[str] = None
        self._active_profile_obj: Optional[ConnectionProfile] = None

    def add_profile(self, profile: ConnectionProfile):
        self._profiles[profile.name] = profile

    def remove_profile(self, name: str):
        if name in self._profiles:
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
            print(f"Connect error: {e}")
            return False

    def disconnect(self, profile_name: str | None = None) -> None:
        """Clear the active connection state (connections are per-query, nothing to close)."""
        name = profile_name or self._active_profile
        if name and self._active_profile == name:
            self._active_profile = None
            self._active_profile_obj = None

    def _build_conn_string(self, profile: ConnectionProfile) -> str:
        return (
            f"host={profile.host} port={profile.port} "
            f"dbname={profile.database} user={profile.username} "
            f"password={profile.password}"
        )

    def _get_conn_string(self) -> str:
        """Build connection string for the active profile."""
        if not self._active_profile_obj:
            raise RuntimeError("No active connection")
        return self._build_conn_string(self._active_profile_obj)

    def execute_sync(self, query: str, params: tuple | None = None) -> list[dict[str, Any]]:
        """Execute a query from a background thread using a direct sync connection"""
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
            "WHERE schema_name NOT IN ('pg_catalog', 'information_schema') "
            "ORDER BY schema_name"
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
