# ----------------------------------------------------------------------
# SQL Schema Studio 0.9 - Schema Designer Package (GPLv3)
# Copyright (C) 2026 Peter Leukanič
# License: GNU GPL v3+ <https://www.gnu.org/licenses/gpl-3.0.txt>
# This is free software with NO WARRANTY.
# Feel free to distribute and modify.
# ----------------------------------------------------------------------

"""Schema designer package — visual database schema editing."""

from src.ui.schema_designer.models import ForeignKey, SchemaTable, TableColumn
from src.ui.schema_designer.designer import SchemaDesigner

__all__ = ["SchemaDesigner", "ForeignKey", "SchemaTable", "TableColumn"]
