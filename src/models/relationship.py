# ----------------------------------------------------------------------
# SQL Schema Studio 0.2 - Relationship Model (GPLv3)
# Copyright (C) 2026 Peter Leukanič
# License: GNU GPL v3+ <https://www.gnu.org/licenses/gpl-3.0.txt>
# This is free software with NO WARRANTY.
# Feel free to distribute and modify.
# ----------------------------------------------------------------------

"""
Relationship/foreign key model
"""

from __future__ import annotations
from dataclasses import dataclass


@dataclass
class Relationship:
    """Represents a foreign key relationship"""

    name: str
    source_table: str
    source_columns: list
    target_table: str
    target_columns: list
    on_delete: str = "NO ACTION"
    on_update: str = "NO ACTION"
    source_schema: str = "public"
    target_schema: str = "public"

    def _quote(self, name: str) -> str:
        """Quote a PostgreSQL identifier safely."""
        return f'"{name}"'

    def to_sql(self) -> str:
        """Generate FOREIGN KEY constraint SQL."""
        src_table = f"{self._quote(self.source_schema)}.{self._quote(self.source_table)}"
        tgt_table = f"{self._quote(self.target_schema)}.{self._quote(self.target_table)}"
        src_cols = ", ".join(self._quote(c) for c in self.source_columns)
        tgt_cols = ", ".join(self._quote(c) for c in self.target_columns)

        sql = (
            f"ALTER TABLE {src_table} "
            f"ADD CONSTRAINT {self._quote(self.name)} "
            f"FOREIGN KEY ({src_cols}) "
            f"REFERENCES {tgt_table} ({tgt_cols})"
        )

        if self.on_delete != "NO ACTION":
            sql += f" ON DELETE {self.on_delete}"
            if self.on_update != "NO ACTION":
                sql += f" ON UPDATE {self.on_update}"

        return sql + ";"
