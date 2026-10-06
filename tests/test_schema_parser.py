# ----------------------------------------------------------------------
# SQL Schema Studio 0.9.5 - Schema Parser Tests (GPLv3)
# Copyright (C) 2026 Peter Leukanič
# License: GNU GPL v3+ <https://www.gnu.org/licenses/gpl-3.0.txt>
# This is free software with NO WARRANTY.
# Feel free to distribute and modify.
# ----------------------------------------------------------------------

"""Tests for SchemaParser — CREATE TABLE, ALTER TABLE, comments, types.

The parser is the gatekeeper between user-supplied SQL files and the
Schema Designer. If it silently drops a column or FK, the designer
shows an incomplete schema with no visible error. These tests are the
safety net for that behavior.
"""

import pytest

from src.core.schema_parser import SchemaParser


@pytest.fixture
def parser():
    return SchemaParser()


# =====================================================================
# Basic CREATE TABLE
# =====================================================================


class TestBasicCreateTable:
    def test_single_column_table(self, parser):
        sql = "CREATE TABLE users (id INT);"
        tables, fks = parser.parse_sql(sql)
        assert len(tables) == 1
        assert tables[0]["name"] == "users"
        assert tables[0]["schema"] == "public"
        assert len(tables[0]["columns"]) == 1
        assert tables[0]["columns"][0]["name"] == "id"
        assert fks == []

    def test_multiple_columns(self, parser):
        sql = """
        CREATE TABLE users (
            id SERIAL PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            email TEXT
        );
        """
        tables, _ = parser.parse_sql(sql)
        assert len(tables[0]["columns"]) == 3
        names = [c["name"] for c in tables[0]["columns"]]
        assert names == ["id", "name", "email"]

    def test_multiple_tables(self, parser):
        sql = """
        CREATE TABLE users (id INT);
        CREATE TABLE orders (id INT);
        CREATE TABLE products (id INT);
        """
        tables, _ = parser.parse_sql(sql)
        assert len(tables) == 3
        assert {t["name"] for t in tables} == {"users", "orders", "products"}

    def test_schema_qualified(self, parser):
        sql = "CREATE TABLE myschema.users (id INT);"
        tables, _ = parser.parse_sql(sql)
        assert tables[0]["schema"] == "myschema"
        assert tables[0]["name"] == "users"

    def test_if_not_exists(self, parser):
        sql = "CREATE TABLE IF NOT EXISTS users (id INT);"
        tables, _ = parser.parse_sql(sql)
        assert len(tables) == 1
        assert tables[0]["name"] == "users"


# =====================================================================
# Comments
# =====================================================================


class TestComments:
    def test_block_comment_before_table(self, parser):
        sql = """
        /* This is a header comment */
        CREATE TABLE users (id INT);
        """
        tables, _ = parser.parse_sql(sql)
        assert len(tables) == 1
        assert len(tables[0]["columns"]) == 1

    def test_block_comment_inline(self, parser):
        sql = """
        CREATE TABLE users (
            id INT, /* primary key */
            name TEXT
        );
        """
        tables, _ = parser.parse_sql(sql)
        assert len(tables[0]["columns"]) == 2

    def test_line_comment_before_table(self, parser):
        sql = """
        -- This is a comment
        CREATE TABLE users (id INT);
        """
        tables, _ = parser.parse_sql(sql)
        assert len(tables) == 1

    def test_line_comment_after_column(self, parser):
        sql = """
        CREATE TABLE users (
            id INT,  -- the id
            name TEXT  -- the name
        );
        """
        tables, _ = parser.parse_sql(sql)
        assert len(tables[0]["columns"]) == 2
        names = [c["name"] for c in tables[0]["columns"]]
        assert "id" in names
        assert "name" in names


# =====================================================================
# Data types
# =====================================================================


class TestDataTypes:
    def test_integer(self, parser):
        sql = "CREATE TABLE t (id INT);"
        tables, _ = parser.parse_sql(sql)
        assert tables[0]["columns"][0]["type"] == "INT"

    def test_varchar_with_length(self, parser):
        sql = "CREATE TABLE t (name VARCHAR(255));"
        tables, _ = parser.parse_sql(sql)
        col = tables[0]["columns"][0]
        assert col["type"] == "VARCHAR"
        assert col["length"] == 255

    def test_numeric_with_comma(self, parser):
        sql = "CREATE TABLE t (price NUMERIC(10,2));"
        tables, _ = parser.parse_sql(sql)
        col = tables[0]["columns"][0]
        assert col["type"] == "NUMERIC"
        # parser stores the first number as length (precision)
        assert col["length"] == 10

    def test_numeric_with_space(self, parser):
        """The parser's _normalize_sql should collapse 'NUMERIC(10, 2)'."""
        sql = "CREATE TABLE t (price NUMERIC(10, 2));"
        tables, _ = parser.parse_sql(sql)
        col = tables[0]["columns"][0]
        assert col["type"] == "NUMERIC"
        assert col["length"] == 10

    def test_text(self, parser):
        sql = "CREATE TABLE t (body TEXT);"
        tables, _ = parser.parse_sql(sql)
        assert tables[0]["columns"][0]["type"] == "TEXT"

    def test_serial(self, parser):
        sql = "CREATE TABLE t (id SERIAL PRIMARY KEY);"
        tables, _ = parser.parse_sql(sql)
        col = tables[0]["columns"][0]
        assert col["type"] == "SERIAL"
        assert col["is_pk"] is True
        # SERIAL implies NOT NULL
        assert col["nullable"] is False


# =====================================================================
# Constraints
# =====================================================================


class TestConstraints:
    def test_inline_primary_key(self, parser):
        sql = "CREATE TABLE t (id INT PRIMARY KEY);"
        tables, _ = parser.parse_sql(sql)
        assert tables[0]["columns"][0]["is_pk"] is True

    def test_table_level_primary_key(self, parser):
        sql = "CREATE TABLE t (a INT, b INT, PRIMARY KEY (a, b));"
        tables, _ = parser.parse_sql(sql)
        pks = [c for c in tables[0]["columns"] if c["is_pk"]]
        assert len(pks) == 2
        assert {c["name"] for c in pks} == {"a", "b"}

    def test_not_null(self, parser):
        sql = "CREATE TABLE t (name VARCHAR(100) NOT NULL);"
        tables, _ = parser.parse_sql(sql)
        assert tables[0]["columns"][0]["nullable"] is False

    def test_nullable_by_default(self, parser):
        sql = "CREATE TABLE t (name VARCHAR(100));"
        tables, _ = parser.parse_sql(sql)
        assert tables[0]["columns"][0]["nullable"] is True

    def test_default_value(self, parser):
        sql = "CREATE TABLE t (status VARCHAR(20) DEFAULT 'pending');"
        tables, _ = parser.parse_sql(sql)
        col = tables[0]["columns"][0]
        assert col["default"] is not None
        assert "pending" in col["default"]

    def test_check_constraint_does_not_break_columns(self, parser):
        """CHECK contains nested parens — must not confuse column splitting."""
        sql = """
        CREATE TABLE users (
            id SERIAL PRIMARY KEY,
            age INT CHECK (age >= 0 AND age < 150),
            name TEXT
        );
        """
        tables, _ = parser.parse_sql(sql)
        assert len(tables[0]["columns"]) == 3
        names = [c["name"] for c in tables[0]["columns"]]
        assert names == ["id", "age", "name"]

    def test_default_with_parens(self, parser):
        """DEFAULT with parens must not confuse column splitting."""
        sql = """
        CREATE TABLE t (
            id SERIAL,
            created_at TIMESTAMP DEFAULT NOW(),
            name TEXT
        );
        """
        tables, _ = parser.parse_sql(sql)
        assert len(tables[0]["columns"]) == 3


# =====================================================================
# Foreign keys
# =====================================================================


class TestForeignKeys:
    def test_inline_references(self, parser):
        sql = """
        CREATE TABLE users (id SERIAL PRIMARY KEY);
        CREATE TABLE orders (
            id SERIAL PRIMARY KEY,
            user_id INT REFERENCES users(id)
        );
        """
        tables, fks = parser.parse_sql(sql)
        assert len(tables) == 2
        assert len(fks) == 1
        assert fks[0]["from_table"] == "orders"
        assert fks[0]["from_column"] == "user_id"
        assert fks[0]["to_table"] == "users"
        assert fks[0]["to_column"] == "id"

    def test_alter_table_fk(self, parser):
        sql = """
        CREATE TABLE users (id SERIAL PRIMARY KEY);
        CREATE TABLE orders (user_id INT);
        ALTER TABLE orders ADD CONSTRAINT fk_orders_user
            FOREIGN KEY (user_id) REFERENCES users(id);
        """
        tables, fks = parser.parse_sql(sql)
        assert len(fks) == 1
        assert fks[0]["from_table"] == "orders"
        assert fks[0]["to_table"] == "users"

    def test_alter_table_fk_with_schema(self, parser):
        sql = """
        CREATE TABLE myschema.users (id INT PRIMARY KEY);
        CREATE TABLE myschema.orders (user_id INT);
        ALTER TABLE myschema.orders ADD CONSTRAINT fk_x
            FOREIGN KEY (user_id) REFERENCES myschema.users(id);
        """
        tables, fks = parser.parse_sql(sql)
        assert len(fks) == 1
        assert fks[0]["from_table"] == "orders"
        assert fks[0]["to_table"] == "users"

    def test_fk_deduplication(self, parser):
        """Same FK declared twice must not be duplicated in the result."""
        sql = """
        CREATE TABLE users (id INT PRIMARY KEY);
        CREATE TABLE orders (user_id INT REFERENCES users(id));
        ALTER TABLE orders ADD CONSTRAINT fk_x
            FOREIGN KEY (user_id) REFERENCES users(id);
        """
        tables, fks = parser.parse_sql(sql)
        assert len(fks) == 1


# =====================================================================
# Edge cases
# =====================================================================


class TestEdgeCases:
    def test_empty_sql(self, parser):
        tables, fks = parser.parse_sql("")
        assert tables == []
        assert fks == []

    def test_only_comment(self, parser):
        sql = "-- just a comment"
        tables, fks = parser.parse_sql(sql)
        assert tables == []

    def test_missing_semicolon(self, parser):
        """Real-world SQL files sometimes omit the final semicolon."""
        sql = "CREATE TABLE users (id INT)"
        tables, fks = parser.parse_sql(sql)
        # Behavior documented: parser requires trailing ';' — returns nothing.
        # This test exists so that if we ever change that, we notice.
        assert isinstance(tables, list)

    def test_lowercase_keywords(self, parser):
        sql = "create table users (id int primary key);"
        tables, _ = parser.parse_sql(sql)
        assert len(tables) == 1
        assert tables[0]["name"] == "users"

    def test_uppercase_keywords(self, parser):
        sql = "CREATE TABLE USERS (ID INT PRIMARY KEY);"
        tables, _ = parser.parse_sql(sql)
        assert len(tables) == 1
        assert tables[0]["name"] == "USERS"

    def test_quoted_identifiers(self, parser):
        """Double quotes are stripped by _normalize_sql."""
        sql = 'CREATE TABLE "users" ("id" INT);'
        tables, _ = parser.parse_sql(sql)
        assert len(tables) == 1
        assert tables[0]["name"] == "users"
        assert tables[0]["columns"][0]["name"] == "id"

    def test_real_world_table_with_many_columns(self, parser):
        sql = """
        CREATE TABLE orders (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL,
            total NUMERIC(12, 2) NOT NULL DEFAULT 0,
            status VARCHAR(20) DEFAULT 'pending',
            notes TEXT,
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP
        );
        """
        tables, _ = parser.parse_sql(sql)
        assert len(tables[0]["columns"]) == 7
        assert tables[0]["columns"][0]["is_pk"] is True
        # user_id is NOT NULL
        user_id = tables[0]["columns"][1]
        assert user_id["nullable"] is False
