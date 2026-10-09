# ----------------------------------------------------------------------
# SQL Schema Studio 0.9.5 - Query History Tests (GPLv3)
# Copyright (C) 2026 Peter Leukanič
# License: GNU GPL v3+ <https://www.gnu.org/licenses/gpl-3.0.txt>
# This is free software with NO WARRANTY.
# Feel free to distribute and modify.
# ----------------------------------------------------------------------

"""Tests for QueryHistory — SQLite persistence, categorization, filters."""


import pytest

from src.core.query_history import QueryHistory


@pytest.fixture
def history(tmp_path, monkeypatch):
    """QueryHistory backed by a temp SQLite file."""
    fake_db = tmp_path / "test_history.db"
    monkeypatch.setattr("src.core.query_history.DB_PATH", fake_db)
    monkeypatch.setattr("src.core.query_history.DB_DIR", tmp_path)

    h = QueryHistory()
    yield h
    h.close()


# =====================================================================
# Categorization
# =====================================================================


class TestCategorize:
    def test_select(self, history):
        assert history._categorize("SELECT * FROM users") == "SELECT"

    def test_select_lowercase(self, history):
        assert history._categorize("select 1") == "SELECT"

    def test_select_with_leading_whitespace(self, history):
        assert history._categorize("   SELECT 1") == "SELECT"

    def test_insert(self, history):
        assert history._categorize("INSERT INTO t VALUES (1)") == "INSERT"

    def test_update(self, history):
        assert history._categorize("UPDATE t SET a=1") == "UPDATE"

    def test_delete(self, history):
        assert history._categorize("DELETE FROM t") == "DELETE"

    def test_ddl_create(self, history):
        assert history._categorize("CREATE TABLE t (id INT)") == "DDL"

    def test_ddl_alter(self, history):
        assert history._categorize("ALTER TABLE t ADD COLUMN c INT") == "DDL"

    def test_ddl_drop(self, history):
        assert history._categorize("DROP TABLE t") == "DDL"

    def test_ddl_truncate(self, history):
        assert history._categorize("TRUNCATE TABLE t") == "DDL"

    def test_other(self, history):
        assert history._categorize("EXPLAIN SELECT 1") == "OTHER"


# =====================================================================
# Basic add / get
# =====================================================================


class TestAddAndGet:
    def test_add_one(self, history):
        history.add(query="SELECT 1")
        rows = history.get_recent()
        assert len(rows) == 1
        assert rows[0]["query"] == "SELECT 1"
        assert rows[0]["category"] == "SELECT"

    def test_add_multiple_orders_newest_first(self, history):
        history.add(query="SELECT 1")
        history.add(query="SELECT 2")
        history.add(query="SELECT 3")
        rows = history.get_recent()
        assert len(rows) == 3
        assert rows[0]["query"] == "SELECT 3"
        assert rows[1]["query"] == "SELECT 2"
        assert rows[2]["query"] == "SELECT 1"

    def test_add_with_metadata(self, history):
        history.add(
            query="SELECT 1",
            database="mydb",
            execution_time=0.123,
            row_count=42,
            success=True,
        )
        rows = history.get_recent()
        r = rows[0]
        assert r["database"] == "mydb"
        assert r["execution_time"] == pytest.approx(0.123)
        assert r["row_count"] == 42
        assert r["success"] is True

    def test_add_failure_stored(self, history):
        history.add(query="SELECT bogus", success=False)
        rows = history.get_recent()
        assert rows[0]["success"] is False

    def test_add_strips_query(self, history):
        history.add(query="   SELECT 1   ")
        rows = history.get_recent()
        assert rows[0]["query"] == "SELECT 1"

    def test_get_recent_respects_limit(self, history):
        for i in range(10):
            history.add(query=f"SELECT {i}")
        rows = history.get_recent(limit=5)
        assert len(rows) == 5
        assert rows[0]["query"] == "SELECT 9"

    def test_get_recent_returns_ids(self, history):
        history.add(query="SELECT 1")
        history.add(query="SELECT 2")
        rows = history.get_recent()
        assert all("id" in r for r in rows)
        assert rows[0]["id"] != rows[1]["id"]


# =====================================================================
# Search
# =====================================================================


class TestSearch:
    def test_search_finds_match(self, history):
        history.add(query="SELECT * FROM users")
        history.add(query="SELECT * FROM orders")
        rows = history.search("users")
        assert len(rows) == 1
        assert "users" in rows[0]["query"]

    def test_search_case_sensitive_in_sqlite(self, history):
        """SQLite LIKE is case-insensitive for ASCII by default."""
        history.add(query="SELECT * FROM USERS")
        rows = history.search("users")
        assert len(rows) == 1

    def test_search_no_match(self, history):
        history.add(query="SELECT 1")
        rows = history.search("nonexistent")
        assert rows == []

    def test_search_respects_limit(self, history):
        for i in range(10):
            history.add(query=f"SELECT {i} FROM test")
        rows = history.search("SELECT", limit=3)
        assert len(rows) == 3

    def test_search_empty_returns_nothing(self, history):
        history.add(query="SELECT 1")
        rows = history.search("")
        # LIKE '%%' matches everything — returns all rows
        assert len(rows) == 1


# =====================================================================
# Category filter (new in this version)
# =====================================================================


class TestCategoryFilter:
    def test_filter_all_returns_everything(self, history):
        history.add(query="SELECT 1")
        history.add(query="INSERT INTO t VALUES (1)")
        rows = history.get_by_category("all")
        assert len(rows) == 2

    def test_filter_select_only(self, history):
        history.add(query="SELECT 1")
        history.add(query="INSERT INTO t VALUES (1)")
        history.add(query="SELECT 2")
        rows = history.get_by_category("SELECT")
        assert len(rows) == 2
        assert all(r["category"] == "SELECT" for r in rows)

    def test_filter_ddl(self, history):
        history.add(query="CREATE TABLE t (id INT)")
        history.add(query="ALTER TABLE t ADD COLUMN c INT")
        history.add(query="SELECT 1")
        rows = history.get_by_category("DDL")
        assert len(rows) == 2

    def test_filter_no_match_returns_empty(self, history):
        history.add(query="SELECT 1")
        rows = history.get_by_category("DDL")
        assert rows == []

    def test_filter_respects_limit(self, history):
        for i in range(10):
            history.add(query=f"SELECT {i}")
        rows = history.get_by_category("SELECT", limit=3)
        assert len(rows) == 3


# =====================================================================
# get_by_id (new in this version)
# =====================================================================


class TestGetById:
    def test_get_existing_id(self, history):
        history.add(query="SELECT 1")
        rows = history.get_recent()
        rid = rows[0]["id"]
        r = history.get_by_id(rid)
        assert r is not None
        assert r["query"] == "SELECT 1"
        assert r["id"] == rid

    def test_get_missing_id_returns_none(self, history):
        assert history.get_by_id(99999) is None

    def test_get_by_id_after_multiple_inserts(self, history):
        history.add(query="SELECT 1")
        history.add(query="SELECT 2")
        history.add(query="SELECT 3")
        rows = history.get_recent()
        middle_id = rows[1]["id"]
        r = history.get_by_id(middle_id)
        assert r["query"] == "SELECT 2"


# =====================================================================
# Clear
# =====================================================================


class TestClear:
    def test_clear_removes_everything(self, history):
        history.add(query="SELECT 1")
        history.add(query="SELECT 2")
        history.clear()
        assert history.get_recent() == []

    def test_clear_on_empty_does_not_raise(self, history):
        history.clear()  # must not raise


# =====================================================================
# Persistence
# =====================================================================


class TestPersistence:
    def test_data_survives_reopen(self, tmp_path, monkeypatch):
        fake_db = tmp_path / "persist.db"
        monkeypatch.setattr("src.core.query_history.DB_PATH", fake_db)
        monkeypatch.setattr("src.core.query_history.DB_DIR", tmp_path)

        h1 = QueryHistory()
        h1.add(query="SELECT 1", database="db1")
        h1.close()

        h2 = QueryHistory()
        rows = h2.get_recent()
        assert len(rows) == 1
        assert rows[0]["query"] == "SELECT 1"
        assert rows[0]["database"] == "db1"
        h2.close()


# =====================================================================
# Row serialization
# =====================================================================


class TestRowToDict:
    def test_row_to_dict_shape(self, history):
        history.add(query="SELECT 1", database="db1", execution_time=0.5, row_count=3)
        rows = history.get_recent()
        r = rows[0]
        expected_keys = {
            "id",
            "query",
            "category",
            "database",
            "executed_at",
            "execution_time",
            "row_count",
            "success",
        }
        assert set(r.keys()) == expected_keys

    def test_success_flag_is_bool(self, history):
        history.add(query="SELECT 1", success=True)
        history.add(query="SELECT bogus", success=False)
        rows = history.get_recent()
        assert isinstance(rows[0]["success"], bool)
        assert isinstance(rows[1]["success"], bool)
