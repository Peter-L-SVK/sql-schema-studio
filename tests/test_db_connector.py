# ----------------------------------------------------------------------
# SQL Schema Studio 0.7 - DB Connector Tests (GPLv3)
# Copyright (C) 2026 Peter Leukanič
# License: GNU GPL v3+ <https://www.gnu.org/licenses/gpl-3.0.txt>
# This is free software with NO WARRANTY.
# Feel free to distribute and modify.
# ----------------------------------------------------------------------

"""Tests for DatabaseConnector"""

import pytest
from src.core.db_connector import DatabaseConnector, ConnectionProfile


class TestConnectionProfile:
    """ConnectionProfile dataclass tests"""

    def test_default_values(self):
        profile = ConnectionProfile(name="test")
        assert profile.name == "test"
        assert profile.host == "localhost"
        assert profile.port == 5432
        assert profile.database == "postgres"
        assert profile.username == "postgres"
        assert profile.password == ""
        assert profile.ssl_mode == "prefer"

    def test_custom_values(self):
        profile = ConnectionProfile(
            name="custom",
            host="db.example.com",
            port=5433,
            database="myapp",
            username="admin",
            password="secret",
            ssl_mode="require",
        )
        assert profile.host == "db.example.com"
        assert profile.port == 5433
        assert profile.database == "myapp"
        assert profile.ssl_mode == "require"


class TestDatabaseConnector:
    """DatabaseConnector tests"""

    def test_add_and_list_profiles(self):
        connector = DatabaseConnector()
        connector.add_profile(ConnectionProfile(name="test1"))
        connector.add_profile(ConnectionProfile(name="test2"))
        assert connector.list_profiles() == ["test1", "test2"]

    def test_get_profile(self):
        connector = DatabaseConnector()
        profile = ConnectionProfile(name="main", host="srv1")
        connector.add_profile(profile)
        retrieved = connector.get_profile("main")
        assert retrieved is not None
        assert retrieved.host == "srv1"

    def test_get_nonexistent_profile(self):
        connector = DatabaseConnector()
        assert connector.get_profile("nonexistent") is None

    def test_remove_profile(self):
        connector = DatabaseConnector()
        connector.add_profile(ConnectionProfile(name="temp"))
        connector.remove_profile("temp")
        assert "temp" not in connector.list_profiles()

    def test_connect_sync_valid(self, test_db_setup):
        """Test connection with valid credentials"""
        connector = DatabaseConnector()
        profile = ConnectionProfile(
            name="test",
            host="localhost",
            port=5432,
            database="sql_schema_studio_test",
            username="postgres",
            password="admin123",
        )
        connector.add_profile(profile)
        result = connector.connect_sync("test")
        assert result is True
        assert connector._active_profile == "test"
        connector.disconnect()

    def test_connect_sync_invalid_password(self):
        """Test connection with wrong password"""
        connector = DatabaseConnector()
        profile = ConnectionProfile(
            name="bad",
            host="localhost",
            port=5432,
            database="postgres",
            username="postgres",
            password="wrong_password_12345",
        )
        connector.add_profile(profile)
        result = connector.connect_sync("bad")
        assert result is False
        assert connector._active_profile is None

    def test_connect_sync_nonexistent_db(self):
        """Test connection to non-existent database"""
        connector = DatabaseConnector()
        profile = ConnectionProfile(
            name="ghost",
            host="localhost",
            port=5432,
            database="nonexistent_db_xyz",
            username="postgres",
            password="admin123",
        )
        connector.add_profile(profile)
        result = connector.connect_sync("ghost")
        assert result is False

    def test_disconnect(self, db_connector):
        """Test disconnect clears state"""
        assert db_connector._active_profile == "test"
        db_connector.disconnect()
        assert db_connector._active_profile is None

    def test_execute_sync_select(self, db_with_table):
        """Test SELECT query execution"""
        result = db_with_table.execute_sync("SELECT * FROM users ORDER BY id")
        assert len(result) == 3
        assert result[0]["name"] == "Alice"
        assert result[1]["email"] == "bob@example.com"

    def test_execute_sync_with_params(self, db_with_table):
        """Test parameterized query"""
        result = db_with_table.execute_sync("SELECT name, age FROM users WHERE age > %s", (28,))
        assert len(result) == 2
        names = [r["name"] for r in result]
        assert "Alice" in names
        assert "Charlie" in names

    def test_execute_sync_insert(self, db_with_table):
        """Test INSERT execution"""
        db_with_table.execute_sync(
            "INSERT INTO users (name, email, age) VALUES (%s, %s, %s)",
            ("Diana", "diana@example.com", 28),
        )
        result = db_with_table.execute_sync("SELECT * FROM users WHERE name = 'Diana'")
        assert len(result) == 1
        assert result[0]["age"] == 28

    def test_execute_sync_ddl(self, db_connector):
        """Test DDL execution returns empty"""
        result = db_connector.execute_sync("CREATE TABLE test_ddl (id INTEGER)")
        assert result == []
        # Verify table exists
        tables = db_connector.execute_sync(
            "SELECT table_name FROM information_schema.tables " "WHERE table_name = 'test_ddl'"
        )
        assert len(tables) == 1
        db_connector.execute_sync("DROP TABLE test_ddl")

    def test_execute_sync_error(self, db_connector):
        """Test query that causes an error"""
        with pytest.raises(Exception):
            db_connector.execute_sync("SELECT * FROM nonexistent_table")

    def test_get_schemas(self, db_connector):
        """Test schema listing"""
        schemas = db_connector.get_schemas()
        assert "public" in schemas
        assert "pg_catalog" not in schemas
        assert "information_schema" not in schemas

    def test_get_tables(self, db_with_table):
        """Test table listing"""
        tables = db_with_table.get_tables("public")
        table_names = [t["table_name"] for t in tables]
        assert "users" in table_names
        # Verify table type
        users = [t for t in tables if t["table_name"] == "users"][0]
        assert users["table_type"] == "BASE TABLE"
