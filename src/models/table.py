# ----------------------------------------------------------------------
# SQL Schema Studio 0.7 - Table Model (GPLv3)
# Copyright (C) 2026 Peter Leukanič
# License: GNU GPL v3+ <https://www.gnu.org/licenses/gpl-3.0.txt>
# This is free software with NO WARRANTY.
# Feel free to distribute and modify.
# ----------------------------------------------------------------------

"""
Table model representation
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional
from .column import Column


@dataclass
class Table:
    """Represents a database table"""

    name: str
    schema: str = "public"
    columns: List[Column] = field(default_factory=list)
    primary_key: List[str] = field(default_factory=list)
    comment: Optional[str] = None

    def add_column(self, column: Column):
        """Add a column to the table"""
        self.columns.append(column)
        if column.is_primary_key:
            self.primary_key.append(column.name)

    def get_column(self, name: str) -> Optional[Column]:
        """Get a column by name"""
        for col in self.columns:
            if col.name == name:
                return col
        return None

    def to_sql(self) -> str:
        """Generate CREATE TABLE SQL."""
        parts = [f"CREATE TABLE {self.schema}.{self.name} ("]

        col_defs = []
        for col in self.columns:
            col_defs.append(f"    {col.to_sql()}")

        if self.primary_key:
            pk_cols = ", ".join(self.primary_key)
            col_defs.append(f"    PRIMARY KEY ({pk_cols})")

        parts.append(",\n".join(col_defs))
        parts.append(");")

        if self.comment:
            escaped = self.comment.replace("'", "''")
            parts.append(f"\nCOMMENT ON TABLE {self.schema}.{self.name} IS '{escaped}';")

        return "\n".join(parts)
