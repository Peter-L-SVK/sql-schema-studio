# ----------------------------------------------------------------------
# SQL Schema Studio 0.9.5 - Test Suite (GPLv3)
# Copyright (C) 2026 Peter Leukanič
# License: GNU GPL v3+ <https://www.gnu.org/licenses/gpl-3.0.txt>
# This is free software with NO WARRANTY.
# Feel free to distribute and modify.
# ----------------------------------------------------------------------

import pytest
from src.core.query_executor import QueryExecutor
from src.core.db_connector import DatabaseConnector, ConnectionProfile


@pytest.mark.asyncio
async def test_execute_simple_query(db_with_table):
    """Test async query execution."""
    executor = QueryExecutor(db_with_table, timeout=10)
    result = await executor.execute("SELECT * FROM users ORDER BY id")
    
    assert result.success is True
    assert result.row_count == 3
    assert "name" in result.columns
    assert result.error is None


@pytest.mark.asyncio
async def test_execute_timeout():
    """Test that timeout works."""
    # ... mock connector ktorý zaspí
    pass


@pytest.mark.asyncio
async def test_execute_invalid_query(db_with_table):
    """Test that error is captured, not raised."""
    executor = QueryExecutor(db_with_table, timeout=10)
    result = await executor.execute("SELECT * FROM nonexistent_table_xyz")
    
    assert result.success is False
    assert result.error is not None
    assert "nonexistent_table_xyz" in result.error
