# ----------------------------------------------------------------------
# SQL Schema Studio - Column Model (GPLv3)
# Copyright (C) 2026 Peter Leukanič
# License: GNU GPL v3+ <https://www.gnu.org/licenses/gpl-3.0.txt>
# This is free software with NO WARRANTY.
# Feel free to distribute and modify.
# ----------------------------------------------------------------------

"""
Column model representation
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional


@dataclass
class Column:
    """Represents a database column"""

    name: str
    data_type: str = "integer"
    nullable: bool = True
    default: Optional[str] = None
    is_primary_key: bool = False
    is_unique: bool = False
    comment: Optional[str] = None
    length: Optional[int] = None
    precision: Optional[int] = None
    scale: Optional[int] = None

    def to_sql(self) -> str:
        """Generate column definition SQL"""
        parts = [self.name]

        # Data type with modifiers
        dtype = self.data_type.upper()
        if self.length:
            dtype = f"{dtype}({self.length})"
        elif self.precision is not None:
            if self.scale is not None:
                dtype = f"{dtype}({self.precision}, {self.scale})"
            else:
                dtype = f"{dtype}({self.precision})"

        parts.append(dtype)

        if not self.nullable:
            parts.append("NOT NULL")

        if self.default:
            parts.append(f"DEFAULT {self.default}")

        if self.is_unique:
            parts.append("UNIQUE")

        return " ".join(parts)
