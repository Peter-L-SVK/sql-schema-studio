# ----------------------------------------------------------------------
# SQL Schema Studio 0.6 - Test Configuration (GPLv3)
# Copyright (C) 2026 Peter Leukanič
# License: GNU GPL v3+ <https://www.gnu.org/licenses/gpl-3.0.txt>
# This is free software with NO WARRANTY.
# Feel free to distribute and modify.
# ----------------------------------------------------------------------

"""Shared test fixtures and configuration"""

import pytest
import psycopg
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.db_connector import DatabaseConnector, ConnectionProfile

# Test database settings — use a dedicated test database
TEST_DB = "sql_schema_studio_test"
TEST_USER = "postgres"
TEST_PASSWORD = "admin123"
TEST_HOST = "localhost"
TEST_PORT = 5432


@pytest.fixture(scope="session")
def test_db_setup():
    """Create test database once per session, drop at end"""
    # Connect to default postgres database to create test db
    conn = psycopg.connect(
        f"host={TEST_HOST} port={TEST_PORT} "
        f"dbname=postgres user={TEST_USER} password={TEST_PASSWORD}"
    )
    conn.autocommit = True

    # Drop if exists from previous run
    conn.execute(f"DROP DATABASE IF EXISTS {TEST_DB}")
    conn.execute(f"CREATE DATABASE {TEST_DB}")
    conn.close()

    yield

    # Teardown
    conn = psycopg.connect(
        f"host={TEST_HOST} port={TEST_PORT} "
        f"dbname=postgres user={TEST_USER} password={TEST_PASSWORD}"
    )
    conn.autocommit = True
    conn.execute(f"DROP DATABASE IF EXISTS {TEST_DB}")
    conn.close()


@pytest.fixture
def db_connector(test_db_setup):
    """Create a connected DatabaseConnector"""
    connector = DatabaseConnector()
    profile = ConnectionProfile(
        name="test",
        host=TEST_HOST,
        port=TEST_PORT,
        database=TEST_DB,
        username=TEST_USER,
        password=TEST_PASSWORD,
    )
    connector.add_profile(profile)
    connector.connect_sync("test")
    yield connector
    connector.disconnect()


@pytest.fixture
def db_with_table(db_connector):
    """Create a test table with sample data"""
    db_connector.execute_sync("""
        CREATE TABLE users (
            id SERIAL PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            email VARCHAR(200) UNIQUE,
            age INTEGER,
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)

    db_connector.execute_sync("""
        INSERT INTO users (name, email, age) VALUES
        ('Alice', 'alice@example.com', 30),
        ('Bob', 'bob@example.com', 25),
        ('Charlie', 'charlie@example.com', 35)
    """)

    yield db_connector

    db_connector.execute_sync("DROP TABLE IF EXISTS users CASCADE")
