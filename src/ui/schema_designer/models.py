# ----------------------------------------------------------------------
# SQL Schema Studio 0.9 - Schema Designer Models (GPLv3)
# Copyright (C) 2026 Peter Leukanič
# License: GNU GPL v3+ <https://www.gnu.org/licenses/gpl-3.0.txt>
# This is free software with NO WARRANTY.
# Feel free to distribute and modify.
# ----------------------------------------------------------------------

"""Data models for the schema designer."""

import copy

from src.config import (
    SCHEMA_TABLE_WIDTH,
    SCHEMA_TABLE_HEADER_HEIGHT,
    SCHEMA_TABLE_ROW_HEIGHT,
    SCHEMA_TABLE_BODY_PADDING,
)


class ForeignKey:
    """Represents a foreign key relationship between two tables."""

    def __init__(
        self,
        name,
        from_table,
        from_column,
        to_table,
        to_column,
        from_col_index=None,
        to_col_index=None,
        line_style="straight",
        color=(0.2, 0.4, 0.6),
        direction="forward",
    ):
        self.name = name
        self.from_table = from_table
        self.to_table = to_table
        self.from_column = from_column
        self.to_column = to_column
        self.from_col_index = from_col_index
        self.to_col_index = to_col_index
        self.line_style = line_style
        self.color = color
        self.direction = direction
        self.waypoints: list[tuple[float, float]] = []
        self._cached_path: list[tuple[float, float]] = []

    def __deepcopy__(self, memo):
        """Custom deepcopy to handle waypoints and cached path."""
        cls = self.__class__
        result = cls.__new__(cls)
        memo[id(self)] = result
        for k, v in self.__dict__.items():
            if k == "_cached_path":
                setattr(result, k, [])
            else:
                setattr(result, k, copy.deepcopy(v, memo))
        return result


class SchemaTable:
    """Represents a table on the designer canvas."""

    def __init__(self, name: str, x: float = 50, y: float = 50, color=(0.3, 0.5, 0.9)):
        self.name = name
        self.x = x
        self.y = y
        self.columns: list[TableColumn] = []
        self.schema = "public"
        self._width = SCHEMA_TABLE_WIDTH
        self._header_height = SCHEMA_TABLE_HEADER_HEIGHT
        self._row_height = SCHEMA_TABLE_ROW_HEIGHT
        self._body_padding = SCHEMA_TABLE_BODY_PADDING
        self.color = color

    def contains(self, px: float, py: float) -> bool:
        w, h = self.get_size()
        return self.x <= px <= self.x + w and self.y <= py <= self.y + h

    def get_size(self) -> tuple[float, float]:
        rows = max(len(self.columns), 1)
        return (
            self._width,
            self._header_height + rows * self._row_height + self._body_padding,
        )

    def to_sql(self) -> str:
        def quote(name):
            return f'"{name}"'

        lines = [f"CREATE TABLE {self.schema}.{quote(self.name)} ("]
        col_defs = []
        for col in self.columns:
            col_defs.append(f"    {col.to_sql()}")
        pks = [c.name for c in self.columns if c.is_primary]
        if pks:
            col_defs.append(f"    PRIMARY KEY ({', '.join(quote(c) for c in pks)})")
        lines.append(",\n".join(col_defs))
        lines.append(");")
        return "\n".join(lines)


class TableColumn:
    """Column in the schema designer."""

    def __init__(
        self,
        name: str,
        data_type: str = "integer",
        is_primary: bool = False,
        nullable: bool = True,
        length: int | None = None,
    ):
        self.name = name
        self.data_type = data_type
        self.is_primary = is_primary
        self.nullable = nullable
        self.length = length

    def to_sql(self) -> str:
        dtype = self.data_type
        if self.length:
            dtype = f"{dtype}({self.length})"
        parts = [f'"{self.name}"', dtype]
        if not self.nullable:
            parts.append("NOT NULL")
        return " ".join(parts)
