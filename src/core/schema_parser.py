# ----------------------------------------------------------------------
# SQL Schema Studio 0.6 - Schema Parser (GPLv3)
# Copyright (C) 2026 Peter Leukanič
# License: GNU GPL v3+ <https://www.gnu.org/licenses/gpl-3.0.txt>
# This is free software with NO WARRANTY.
# Feel free to distribute and modify.
# ----------------------------------------------------------------------

"""Parse SQL schemas using sqlparse with regex fallback."""

import re
import sqlparse
from sqlparse.tokens import Keyword

from src.utils.logging import get_logger

logger = get_logger(__name__)


class SchemaParser:
    """Parse CREATE TABLE and ALTER TABLE statements from SQL text."""

    def parse_sql(self, sql_text: str) -> tuple[list[dict], list[dict]]:
        """Parse SQL text and return (tables, foreign_keys).

        Each table dict: {name, schema, columns: [{name, type, nullable, default, is_pk}]}
        Each FK dict: {name, from_table, from_column, to_table, to_column}
        """
        # Remove quotes for easier parsing, but keep original for display
        clean_text = sql_text.replace('"', "")

        tables = []
        foreign_keys = []

        statements = sqlparse.split(clean_text)
        for stmt in statements:
            if not stmt.strip():
                continue

            parsed = sqlparse.parse(stmt)[0]

            if self._is_create_table(parsed):
                table = self._parse_create_table(parsed)
                if table:
                    tables.append(table)

            elif self._is_alter_table_fk(parsed):
                fk = self._parse_alter_table_fk(parsed)
                if fk:
                    foreign_keys.append(fk)

        # Also try regex for inline REFERENCES in CREATE TABLE
        fks_from_inline = self._parse_inline_references(sql_text)
        foreign_keys.extend(fks_from_inline)

        logger.info(f"Parsed {len(tables)} tables and {len(foreign_keys)} FKs")
        return tables, foreign_keys

    def _is_create_table(self, parsed) -> bool:
        """Check if statement is CREATE TABLE."""
        if not parsed.get_type() == "CREATE":
            return False
        return True

    def _is_alter_table_fk(self, parsed) -> bool:
        """Check if statement is ALTER TABLE ... ADD CONSTRAINT ... FOREIGN KEY."""
        text = str(parsed).upper()
        return "ALTER TABLE" in text and "FOREIGN KEY" in text

    def _parse_create_table(self, parsed) -> dict | None:
        """Extract table info from CREATE TABLE statement."""
        try:
            # Get table name from tokens
            tokens = [t for t in parsed.tokens if not t.is_whitespace]
            table_name = None
            table_schema = "public"

            for i, token in enumerate(tokens):
                if token.match(Keyword, "TABLE"):
                    # Next non-whitespace token should be the name
                    for j in range(i + 1, len(tokens)):
                        if tokens[j].is_whitespace:
                            continue
                        name_token = str(tokens[j])
                        if "." in name_token:
                            parts = name_token.split(".")
                            table_schema = parts[0]
                            table_name = parts[1]
                        else:
                            table_name = name_token.strip("()")
                        break
                    break

            if not table_name:
                return None

            # Extract columns from the body
            body = self._extract_create_body(str(parsed))
            columns = self._parse_columns(body)

            pk_match = re.search(r"PRIMARY\s+KEY\s*\(([^)]+)\)", body, re.IGNORECASE)
            if pk_match:
                pk_cols = [c.strip().strip('"') for c in pk_match.group(1).split(",")]
                for col in columns:
                    if col["name"] in pk_cols:
                        col["is_pk"] = True

            return {
                "name": table_name,
                "schema": table_schema,
                "columns": columns,
            }
        except Exception as e:
            logger.warning(f"Failed to parse CREATE TABLE: {e}")
            return None

    def _extract_create_body(self, sql: str) -> str:
        """Extract the column definitions from CREATE TABLE."""
        match = re.search(r"\((.*)\)", sql, re.DOTALL)
        if match:
            return match.group(1)
        return ""

    def _parse_columns(self, body: str) -> list[dict]:
        """Parse column definitions from table body."""
        columns = []

        for line in self._split_columns(body):
            col = self._parse_column_line(line)
            if col:
                columns.append(col)

        return columns

    def _split_columns(self, body: str) -> list[str]:
        """Split table body into individual column/constraint lines."""
        # Handle nested parentheses in DEFAULT values and CHECK constraints
        lines = []
        current: list[str] = []
        depth = 0

        for char in body:
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

    def _parse_column_line(self, line: str) -> dict | None:
        """Parse a single column definition."""
        line = line.strip()
        if not line:
            return None

        # Skip constraint lines
        upper = line.upper().strip()
        if upper.startswith(
            ("PRIMARY KEY", "FOREIGN KEY", "CONSTRAINT", "UNIQUE", "CHECK", "EXCLUDE")
        ):
            return None

        parts = line.split()
        if len(parts) < 2:
            return None

        col_name = parts[0].strip('"')
        col_type = parts[1].strip('"').strip(",")

        # Extract length from type like varchar(255)
        length = None
        type_match = re.match(r"(\w+)\s*\((\d+)\)", col_type)
        if type_match:
            col_type = type_match.group(1)
            length = int(type_match.group(2))

        # Detect constraints
        is_pk = "PRIMARY KEY" in upper
        nullable = "NOT NULL" not in upper
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

    def _parse_alter_table_fk(self, parsed) -> dict | None:
        """Parse ALTER TABLE ... ADD CONSTRAINT ... FOREIGN KEY."""
        text = str(parsed)

        match = re.search(
            r"ALTER\s+TABLE\s+(\w+)\.?(\w+)?\s+"
            r"ADD\s+CONSTRAINT\s+(\w+)\s+"
            r"FOREIGN\s+KEY\s*\((\w+)\)\s+"
            r"REFERENCES\s+(\w+)\.?(\w+)?\s*\((\w+)\)",
            text,
            re.IGNORECASE,
        )

        if match:
            return {
                "name": match.group(3),
                "from_table": match.group(2) or match.group(1),
                "from_column": match.group(4),
                "to_table": match.group(6) or match.group(5),
                "to_column": match.group(7),
            }
        return None

    def _parse_inline_references(self, sql_text: str) -> list[dict]:
        """Parse inline REFERENCES in CREATE TABLE bodies."""
        fks = []
        pattern = re.compile(
            r"CREATE\s+TABLE\s+(?:\w+\.)?(\w+)\s*\((.*?)\);", re.IGNORECASE | re.DOTALL
        )

        for match in pattern.finditer(sql_text):
            table_name = match.group(1)
            body = match.group(2)

            ref_pattern = re.compile(
                r"(\w+)\s+\w+(?:\(\d+(?:,\d+)?\))?\s+NOT\s+NULL\s+REFERENCES\s+(\w+)\s*\((\w+)\)",
                re.IGNORECASE,
            )

            for ref_match in ref_pattern.finditer(body):
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
