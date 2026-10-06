# ----------------------------------------------------------------------
# SQL Schema Studio 0.9.5 - Schema Cache Tests (GPLv3)
# Copyright (C) 2026 Peter Leukanič
# License: GNU GPL v3+ <https://www.gnu.org/licenses/gpl-3.0.txt>
# This is free software with NO WARRANTY.
# Feel free to distribute and modify.
# ----------------------------------------------------------------------

"""Tests for SchemaCache — TTL, invalidation, thread safety."""

import threading
import time
from unittest.mock import patch

import pytest

from src.core.schema_cache import SchemaCache


class TestBasicOperations:
    def test_get_missing_returns_none(self):
        cache = SchemaCache()
        assert cache.get("public", "users") is None

    def test_put_then_get_round_trip(self):
        cache = SchemaCache()
        data = [{"column_name": "id", "data_type": "integer"}]
        cache.put("public", "users", data)
        assert cache.get("public", "users") == data

    def test_put_overwrites_existing(self):
        cache = SchemaCache()
        cache.put("public", "users", [{"a": 1}])
        cache.put("public", "users", [{"a": 2}])
        assert cache.get("public", "users") == [{"a": 2}]

    def test_empty_list_is_a_valid_value(self):
        """An empty column list must be cached — it means 'no columns'."""
        cache = SchemaCache()
        cache.put("public", "empty", [])
        assert cache.get("public", "empty") == []

    def test_schema_and_table_are_case_sensitive(self):
        cache = SchemaCache()
        cache.put("public", "users", [{"a": 1}])
        assert cache.get("Public", "users") is None
        assert cache.get("public", "Users") is None


class TestTTL:
    def test_entry_expires_after_ttl(self):
        cache = SchemaCache(ttl_seconds=1)
        cache.put("public", "users", [{"a": 1}])

        # Save the real timestamp BEFORE patching time.time — inside the
        # patch block, time.time() would return the mock itself.
        real_now = time.time()

        with patch("src.core.schema_cache.time.time", return_value=real_now + 2):
            assert cache.get("public", "users") is None

    def test_entry_valid_before_ttl(self):
        cache = SchemaCache(ttl_seconds=300)
        cache.put("public", "users", [{"a": 1}])
        assert cache.get("public", "users") == [{"a": 1}]

    def test_expired_entry_is_pruned_from_cache(self):
        cache = SchemaCache(ttl_seconds=1)
        cache.put("public", "users", [{"a": 1}])

        real_now = time.time()

        with patch("src.core.schema_cache.time.time", return_value=real_now + 2):
            cache.get("public", "users")  # triggers pruning
        assert cache.size() == 0


class TestInvalidation:
    def test_invalidate_removes_one_entry(self):
        cache = SchemaCache()
        cache.put("public", "users", [{"a": 1}])
        cache.put("public", "orders", [{"b": 2}])
        cache.invalidate("public", "users")
        assert cache.get("public", "users") is None
        assert cache.get("public", "orders") == [{"b": 2}]

    def test_invalidate_missing_key_is_noop(self):
        cache = SchemaCache()
        cache.invalidate("public", "nonexistent")

    def test_invalidate_schema_clears_all_in_schema(self):
        cache = SchemaCache()
        cache.put("public", "users", [{"a": 1}])
        cache.put("public", "orders", [{"b": 2}])
        cache.put("audit", "logs", [{"c": 3}])
        cache.invalidate_schema("public")
        assert cache.get("public", "users") is None
        assert cache.get("public", "orders") is None
        assert cache.get("audit", "logs") == [{"c": 3}]

    def test_invalidate_all_clears_everything(self):
        cache = SchemaCache()
        cache.put("public", "users", [{"a": 1}])
        cache.put("audit", "logs", [{"b": 2}])
        cache.invalidate_all()
        assert cache.size() == 0
        assert cache.get("public", "users") is None
        assert cache.get("audit", "logs") is None

    def test_clear_is_alias_for_invalidate_all(self):
        cache = SchemaCache()
        cache.put("public", "users", [{"a": 1}])
        cache.clear()
        assert cache.size() == 0


class TestSize:
    def test_size_empty(self):
        cache = SchemaCache()
        assert cache.size() == 0

    def test_size_counts_entries(self):
        cache = SchemaCache()
        cache.put("public", "a", [1])
        cache.put("public", "b", [2])
        cache.put("audit", "c", [3])
        assert cache.size() == 3

    def test_size_prunes_expired_entries(self):
        cache = SchemaCache(ttl_seconds=1)
        cache.put("public", "a", [1])
        cache.put("public", "b", [2])

        real_now = time.time()

        with patch("src.core.schema_cache.time.time", return_value=real_now + 2):
            assert cache.size() == 0


class TestThreadSafety:
    def test_concurrent_put_and_get(self):
        cache = SchemaCache()
        errors: list[Exception] = []

        def worker(thread_id: int):
            try:
                for i in range(100):
                    cache.put("public", f"t{thread_id}_{i}", [{"i": i}])
                    cache.get("public", f"t{thread_id}_{i}")
                    cache.invalidate("public", f"t{thread_id}_{i}")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"Thread errors: {errors}"
        assert cache.size() == 0


class TestArbitraryValues:
    def test_arbitrary_dict_value(self):
        cache = SchemaCache()
        cache.put("public", "meta", {"rows": 1234, "size": "10MB"})
        assert cache.get("public", "meta") == {"rows": 1234, "size": "10MB"}

    def test_none_value_stored_and_returned(self):
        cache = SchemaCache()
        cache.put("public", "ghost", None)
        assert cache.get("public", "ghost") is None
