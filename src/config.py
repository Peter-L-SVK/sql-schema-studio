# ----------------------------------------------------------------------
# SQL Schema Studio 0.8 - Configuration (GPLv3)
# Copyright (C) 2026 Peter Leukanič
# License: GNU GPL v3+ <https://www.gnu.org/licenses/gpl-3.0.txt>
# This is free software with NO WARRANTY.
# Feel free to distribute and modify.
# ----------------------------------------------------------------------

"""Centralized configuration constants for SQL Schema Studio."""

# --- Database ---
EXCLUDED_SCHEMAS: frozenset[str] = frozenset(
    {
        "pg_catalog",
        "information_schema",
        "pg_toast",
        "pg_temp_1",
        "pg_toast_temp_1",
    }
)

DDL_COMMANDS: frozenset[str] = frozenset(
    {
        "CREATE",
        "ALTER",
        "DROP",
        "TRUNCATE",
        "RENAME",
    }
)

DML_COMMANDS: frozenset[str] = frozenset(
    {
        "INSERT",
        "UPDATE",
        "DELETE",
    }
)

# Combined — any statement that should trigger a browser refresh
REFRESH_TRIGGER_COMMANDS: frozenset[str] = DDL_COMMANDS | DML_COMMANDS

# Default values when openning Connect
DEFAULT_PORT: int = 5432
DEFAULT_HOST: str = "localhost"
DEFAULT_DATABASE: str = "postgres"
DEFAULT_USER: str = "postgres"

# --- UI ---
DEFAULT_WINDOW_WIDTH: int = 1200
DEFAULT_WINDOW_HEIGHT: int = 800
BROWSER_PANEL_WIDTH: int = 260
RESULTS_ROW_LIMIT: int = 500

# --- Query ---
DEFAULT_QUERY_TIMEOUT: int = 30
MAX_QUERY_DISPLAY_LENGTH: int = 100

# --- Hooks ---
HOOK_MEMORY_LIMIT_MB: int = 512
HOOK_TIME_LIMIT_SECONDS: int = 30

# --- Keyring ---
KEYRING_SERVICE_NAME: str = "sql-schema-studio"

# Schema designer
SCHEMA_TABLE_WIDTH: int = 200
SCHEMA_TABLE_ROW_HEIGHT: int = 26
SCHEMA_TABLE_HEADER_HEIGHT: int = 32
SCHEMA_TABLE_BODY_PADDING: int = 4
SCHEMA_CANVAS_WIDTH: int = 1200
SCHEMA_CANVAS_HEIGHT: int = 800

# Schema Designer colors
SCHEMA_COLORS = {
    "blue": (0.3, 0.5, 0.8),
    "green": (0.3, 0.7, 0.4),
    "orange": (0.9, 0.5, 0.2),
    "red": (0.8, 0.3, 0.3),
    "purple": (0.6, 0.4, 0.8),
    "gray": (0.5, 0.5, 0.5),
    "teal": (0.2, 0.7, 0.7),
    "pink": (0.9, 0.4, 0.7),
}

# Hook manager
HOOK_RESULT_DIALOG_WIDTH: int = 500
HOOK_RESULT_DIALOG_HEIGHT: int = 400
