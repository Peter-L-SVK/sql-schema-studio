# ----------------------------------------------------------------------
# SQL Schema Studio 0.9.5 - Keboola Transformation Engines (GPLv3)
# Copyright (C) 2026 Peter Leukanič
# License: GNU GPL v3+ <https://www.gnu.org/licenses/gpl-3.0.txt>
# This is free software with NO WARRANTY.
# Feel free to distribute and modify.
# ----------------------------------------------------------------------

"""Supported Keboola transformation engines.

Each engine maps to a Keboola component ID and describes the SQL
dialect quirks (identifier quoting, required qualified names) so
the SQL editor and validator can give accurate hints.
"""

from __future__ import annotations

from typing import TypedDict


class EngineConfig(TypedDict):
    """Definition of a single transformation engine."""

    display_name: str
    component_id: str
    identifier_quote: str
    qualified_names_required: bool
    default_output_prefix: str
    docs_url: str


ENGINES: dict[str, EngineConfig] = {
    "bigquery": {
        "display_name": "Google BigQuery",
        "component_id": "keboola.google-bigquery-transformation",
        "identifier_quote": "`",
        "qualified_names_required": True,
        "default_output_prefix": "out.c-sql-schema-studio",
        "docs_url": "https://help.keboola.com/components/transformations/bigquery/",
    },
    "snowflake": {
        "display_name": "Snowflake",
        "component_id": "keboola.snowflake-transformation",
        "identifier_quote": '"',
        "qualified_names_required": False,
        "default_output_prefix": "out.c-sql-schema-studio",
        "docs_url": "https://help.keboola.com/components/transformations/snowflake/",
    },
}


def get_engine(engine_id: str) -> EngineConfig:
    """Return engine config or raise ValueError with a helpful message."""
    if engine_id not in ENGINES:
        available = ", ".join(ENGINES.keys())
        raise ValueError(f"Unknown engine '{engine_id}'. Available engines: {available}")
    return ENGINES[engine_id]


def list_engines() -> list[tuple[str, str]]:
    """Return list of (engine_id, display_name) tuples for UI combo boxes."""
    return [(eid, cfg["display_name"]) for eid, cfg in ENGINES.items()]
