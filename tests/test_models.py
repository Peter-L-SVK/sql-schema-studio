# ----------------------------------------------------------------------
# SQL Schema Studio 0.2 - Model Tests (GPLv3)
# Copyright (C) 2026 Peter Leukanič
# License: GNU GPL v3+ <https://www.gnu.org/licenses/gpl-3.0.txt>
# This is free software with NO WARRANTY.
# Feel free to distribute and modify.
# ----------------------------------------------------------------------

"""Tests for data models"""

from src.models.table import Table
from src.models.column import Column
from src.models.relationship import Relationship


class TestColumn:
    """Column model tests"""

    def test_basic_column(self):
        col = Column(name="id", data_type="integer")
        assert col.name == "id"
        assert col.data_type == "integer"
        assert col.nullable is True
        assert col.is_primary_key is False

    def test_not_null_column(self):
        col = Column(name="email", data_type="varchar", nullable=False, length=255)
        assert col.nullable is False
        assert col.length == 255

    def test_primary_key_column(self):
        col = Column(name="id", data_type="serial", is_primary_key=True)
        assert col.is_primary_key is True

    def test_to_sql_simple(self):
        col = Column(name="name", data_type="text")
        sql = col.to_sql()
        assert "name" in sql
        assert "TEXT" in sql

    def test_to_sql_full(self):
        col = Column(
            name="email",
            data_type="varchar",
            nullable=False,
            default="'noemail@example.com'",
            is_unique=True,
            length=100,
        )
        sql = col.to_sql()
        assert "VARCHAR(100)" in sql
        assert "NOT NULL" in sql
        assert "DEFAULT 'noemail@example.com'" in sql
        assert "UNIQUE" in sql


class TestTable:
    """Table model tests"""

    def test_empty_table(self):
        table = Table(name="products")
        assert table.name == "products"
        assert table.schema == "public"
        assert len(table.columns) == 0

    def test_add_column(self):
        table = Table(name="users")
        col = Column(name="id", data_type="serial", is_primary_key=True)
        table.add_column(col)
        assert len(table.columns) == 1
        assert table.primary_key == ["id"]

    def test_get_column(self):
        table = Table(name="users")
        table.add_column(Column(name="id", data_type="integer"))
        table.add_column(Column(name="email", data_type="varchar"))

        col = table.get_column("email")
        assert col is not None
        assert col.data_type == "varchar"

        assert table.get_column("nonexistent") is None

    def test_to_sql(self):
        table = Table(name="users", comment="User accounts")
        table.add_column(Column(name="id", data_type="serial", is_primary_key=True))
        table.add_column(Column(name="username", data_type="varchar", nullable=False, length=50))
        table.add_column(Column(name="email", data_type="varchar", length=255))

        sql = table.to_sql()
        assert "CREATE TABLE public.users" in sql
        assert "PRIMARY KEY (id)" in sql
        assert "VARCHAR(50) NOT NULL" in sql
        assert "COMMENT ON TABLE public.users IS 'User accounts'" in sql


class TestRelationship:
    """Relationship model tests"""

    def test_basic_fk(self):
        rel = Relationship(
            name="fk_user_orders",
            source_table="orders",
            source_columns=["user_id"],
            target_table="users",
            target_columns=["id"],
        )
        assert rel.source_table == "orders"
        assert rel.target_table == "users"
        assert rel.on_delete == "NO ACTION"

    def test_cascade_delete(self):
        rel = Relationship(
            name="fk_cascade",
            source_table="items",
            source_columns=["order_id"],
            target_table="orders",
            target_columns=["id"],
            on_delete="CASCADE",
        )
        sql = rel.to_sql()
        assert "ON DELETE CASCADE" in sql
        assert 'ALTER TABLE "public"."items"' in sql
        assert 'ADD CONSTRAINT "fk_cascade"' in sql

    def test_custom_schemas(self):
        rel = Relationship(
            name="fk_cross_schema",
            source_table="logs",
            source_columns=["user_id"],
            target_table="users",
            target_columns=["id"],
            source_schema="audit",
            target_schema="public",
        )
        sql = rel.to_sql()
        assert '"audit"."logs"' in sql
        assert '"public"."users"' in sql
