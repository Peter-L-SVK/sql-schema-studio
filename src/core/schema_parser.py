# ----------------------------------------------------------------------
# SQL Schema Studio 0.9 - Schema Parser (GPLv3)
# Copyright (C) 2026 Peter Leukanič
# License: GNU GPL v3+ <https://www.gnu.org/licenses/gpl-3.0.txt>
# This is free software with NO WARRANTY.
# Feel free to distribute and modify.
# ----------------------------------------------------------------------

"""Parse SQL schemas."""

import re

from src.utils.logging import get_logger

logger = get_logger(__name__)


class SchemaParser:
    """Parse CREATE TABLE and ALTER TABLE statements from SQL text.

    Handles real-world production schemas including:
    - Inline comments (-- and /* */)
    - DEFAULT values with parentheses
    - CHECK constraints with complex expressions
    - Self-referencing tables
    - Composite primary and foreign keys
    - NUMERIC(precision, scale) without spaces
    - SERIAL types
    """

    def parse_sql(self, sql_text: str) -> tuple[list[dict], list[dict]]:
        """Parse SQL text and return (tables, foreign_keys)."""
        clean_text = self._remove_comments(sql_text)
        clean_text = self._normalize_sql(clean_text)

        tables = []
        foreign_keys = []
        table_bodies = {}

        # Extract CREATE TABLE statements
        for match in self._find_create_tables(clean_text):
            table_info = self._parse_create_table_robust(match)
            if table_info:
                tables.append(table_info)
                table_bodies[table_info["name"]] = match[2]

        # Extract ALTER TABLE foreign keys
        for match in self._find_alter_tables(clean_text):
            fk = self._parse_alter_table_fk(match)
            if fk:
                foreign_keys.append(fk)

        # Extract inline REFERENCES
        for table_name, body in table_bodies.items():
            inline_fks = self._parse_inline_references_robust(table_name, body)
            foreign_keys.extend(inline_fks)

        # Deduplicate FKs
        seen = set()
        unique_fks = []
        for fk in foreign_keys:
            key = f"{fk['from_table']}.{fk['from_column']}->{fk['to_table']}.{fk['to_column']}"
            if key not in seen:
                seen.add(key)
                unique_fks.append(fk)

        logger.info(f"Parsed {len(tables)} tables and {len(unique_fks)} FKs")
        return tables, unique_fks

    # =====================================================================
    # Text cleaning
    # =====================================================================

    def _remove_comments(self, sql: str) -> str:
        """Remove SQL comments (both -- and /* */ style)."""
        # Remove block comments /* ... */
        sql = re.sub(r"/\*.*?\*/", "", sql, flags=re.DOTALL)
        # Remove line comments -- ... (but not inside strings)
        sql = re.sub(r"--[^\n]*", "", sql)
        return sql

    def _normalize_sql(self, sql: str) -> str:
        """Normalize SQL for easier parsing.

        - Remove double quotes around identifiers
        - Collapse multiple spaces
        - Normalize parentheses spacing for NUMERIC(x,y)
        """
        # Remove quotes (keep original if needed via separate map)
        sql = sql.replace('"', "")
        # Collapse whitespace
        sql = re.sub(r"\s+", " ", sql)
        # Fix NUMERIC(10, 2) -> NUMERIC(10,2) for consistent parsing
        sql = re.sub(r"(\w+)\s*\(\s*(\d+)\s*,\s*(\d+)\s*\)", r"\1(\2,\3)", sql)
        return sql.strip()

    # =====================================================================
    # CREATE TABLE parsing
    # =====================================================================

    def _find_create_tables(self, sql: str) -> list[tuple[str, ...]]:
        """Find all CREATE TABLE statement bodies.

        Returns list of (schema, table_name, body) tuples.
        """
        pattern = re.compile(
            r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?" r"(?:(\w+)\.)?(\w+)\s*\((.*?)\)\s*;",
            re.IGNORECASE | re.DOTALL,
        )
        return pattern.findall(sql)

    def _parse_create_table_robust(self, match: tuple[str, ...]) -> dict | None:
        """Parse a CREATE TABLE match robustly.

        Args:
        match: Tuple of (schema, table_name, body) from regex.
        """
        try:
            schema = match[0] or "public"
            table_name = match[1]
            body = match[2]

            columns = self._parse_columns_robust(body)

            # Find primary key
            pk_match = re.search(r"PRIMARY\s+KEY\s*\(([^)]+)\)", body, re.IGNORECASE)
            if pk_match:
                pk_cols = [c.strip().strip('"') for c in pk_match.group(1).split(",")]
                for col in columns:
                    if col["name"] in pk_cols:
                        col["is_pk"] = True

            return {
                "name": table_name,
                "schema": schema,
                "columns": columns,
            }
        except Exception as e:
            logger.warning(
                f"Failed to parse CREATE TABLE {match[1] if len(match) > 1 else '?'}: {e}"
            )
            return None

    def _parse_columns_robust(self, body: str) -> list[dict]:
        """Parse column definitions handling complex constraints."""
        columns = []

        for line in self._split_columns_robust(body):
            col = self._parse_column_line_robust(line)
            if col:
                columns.append(col)

        return columns

    def _split_columns_robust(self, body: str) -> list[str]:
        """Split table body into individual column/constraint lines.

        Handles nested parentheses in DEFAULT, CHECK, and function calls.
        """
        lines = []
        current: list[str] = []
        depth = 0
        in_string = False

        for char in body:
            if char == "'" and not in_string:
                in_string = True
            elif char == "'" and in_string:
                in_string = False

            if not in_string:
                if char == "(":
                    depth += 1
                elif char == ")":
                    depth -= 1
                elif char == "," and depth == 0:
                    lines.append("".join(current).strip())
                    current = []
                    continue

            current.append(char)

        if current:
            lines.append("".join(current).strip())

        return lines

    def _parse_column_line_robust(self, line: str) -> dict | None:
        """Parse a single column definition handling complex types."""
        line = line.strip()
        if not line:
            return None

        # Skip pure constraint lines
        upper = line.upper().strip()
        skip_patterns = (
            "PRIMARY KEY",
            "FOREIGN KEY",
            "CONSTRAINT",
            "UNIQUE",
            "CHECK",
            "EXCLUDE",
        )
        if upper.startswith(skip_patterns) and "(" in upper:
            return None

        # Try to extract column name and type
        # Pattern: column_name TYPE[(params)] [constraints...]
        match = re.match(
            r"(\w+)\s+"
            r"(\w+(?:\(\d+(?:,\d+)?\))?)"  # TYPE or TYPE(N) or TYPE(N,M)
            r"(.*)",
            line,
            re.IGNORECASE,
        )

        if not match:
            return None

        col_name = match.group(1)
        col_type_raw = match.group(2)
        rest = match.group(3).upper()

        # Parse type and length
        col_type = col_type_raw
        length = None
        type_match = re.match(r"(\w+)\s*\((\d+)(?:,(\d+))?\)", col_type_raw, re.IGNORECASE)
        if type_match:
            col_type = type_match.group(1)
            length = int(type_match.group(2))

        # Detect constraints
        is_pk = "PRIMARY KEY" in rest
        nullable = "NOT NULL" not in rest
        is_serial = col_type.upper() in ("SERIAL", "BIGSERIAL", "SMALLSERIAL")

        # Auto-set PK properties for SERIAL
        if is_serial:
            nullable = False
            # SERIAL columns are often PKs

        # Extract DEFAULT value
        default = None
        default_match = re.search(r"DEFAULT\s+(.+?)(?:\s*,\s*|\s*$)", line, re.IGNORECASE)
        if default_match:
            default = default_match.group(1).strip()

        return {
            "name": col_name,
            "type": col_type,
            "nullable": nullable,
            "is_pk": is_pk,
            "default": default,
            "length": length,
        }

    # =====================================================================
    # ALTER TABLE FOREIGN KEY parsing
    # =====================================================================

    def _find_alter_tables(self, sql: str) -> list[tuple[str, ...]]:
        """Find all ALTER TABLE ... FOREIGN KEY statements."""
        pattern = re.compile(
            r"ALTER\s+TABLE\s+(?:ONLY\s+)?"
            r"(?:(\w+)\.)?(\w+)\s+"
            r"ADD\s+CONSTRAINT\s+(\w+)\s+"
            r"FOREIGN\s+KEY\s*\(([^)]+)\)\s*"
            r"REFERENCES\s+(?:(\w+)\.)?(\w+)\s*\(([^)]+)\)"
            r"(?:\s*ON\s+DELETE\s+\w+)?"
            r"(?:\s*ON\s+UPDATE\s+\w+)?",
            re.IGNORECASE,
        )
        return pattern.findall(sql)

    def _parse_alter_table_fk(self, match: tuple[str, ...]) -> dict | None:
        """Parse ALTER TABLE FOREIGN KEY match."""
        try:
            _table = match[1]
            constraint_name = match[2]
            fk_column = match[3].strip().strip('"')
            ref_table = match[5]
            ref_column = match[6].strip().strip('"')

            return {
                "name": constraint_name,
                "from_table": _table,
                "from_column": fk_column,
                "to_table": ref_table,
                "to_column": ref_column,
            }
        except Exception as e:
            logger.warning(f"Failed to parse ALTER TABLE FK: {e}")
            return None

    # =====================================================================
    # Inline REFERENCES parsing
    # =====================================================================

    def _parse_inline_references_robust(self, table_name: str, body: str) -> list[dict]:
        """Parse inline REFERENCES from CREATE TABLE body.

        Handles: column_name TYPE REFERENCES table(column)
        """
        fks = []

        # Pattern: column_name TYPE [NOT NULL] REFERENCES table(column)
        pattern = re.compile(
            r"(\w+)\s+\w+(?:\(\d+(?:,\d+)?\))?\s*"
            r"(?:NOT\s+NULL\s+)?"
            r"REFERENCES\s+(\w+)\s*\((\w+)\)",
            re.IGNORECASE,
        )

        for ref_match in pattern.finditer(body):
            fks.append(
                {
                    "name": f"fk_{table_name}_{ref_match.group(2)}",
                    "from_table": table_name,
                    "from_column": ref_match.group(1),
                    "to_table": ref_match.group(2),
                    "to_column": ref_match.group(3),
                }
            )

        return fks
