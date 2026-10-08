# ----------------------------------------------------------------------
# SQL Schema Studio 0.9.5 - DataBridge Tests (GPLv3)
# Copyright (C) 2026 Peter Leukanič
# License: GNU GPL v3+ <https://www.gnu.org/licenses/gpl-3.0.txt>
# This is free software with NO WARRANTY.
# Feel free to distribute and modify.
# ----------------------------------------------------------------------

"""Tests for DataBridge — Python ↔ JSON marshaling for Perl hooks."""

import json
from datetime import datetime, date
from decimal import Decimal

import pytest

from src.hooks.bridge import DataBridge


class TestPythonToJson:
    def test_datetime_to_iso(self):
        dt = datetime(2026, 10, 8, 14, 30, 45)
        result = DataBridge.python_to_json(dt)
        assert result == "2026-10-08T14:30:45"

    def test_date_to_iso(self):
        d = date(2026, 10, 8)
        result = DataBridge.python_to_json(d)
        assert result == "2026-10-08"

    def test_decimal_to_float(self):
        result = DataBridge.python_to_json(Decimal("123.45"))
        assert result == 123.45
        assert isinstance(result, float)

    def test_bytes_to_string(self):
        result = DataBridge.python_to_json(b"hello world")
        assert result == "hello world"

    def test_bytes_with_invalid_utf8(self):
        """Invalid UTF-8 sequences must not crash — replace instead."""
        result = DataBridge.python_to_json(b"\xff\xfe")
        assert isinstance(result, str)
        # Replacement character U+FFFD
        assert "\ufffd" in result

    def test_set_to_list(self):
        result = DataBridge.python_to_json({1, 2, 3})
        assert isinstance(result, list)
        assert sorted(result) == [1, 2, 3]

    def test_object_with_dict(self):
        class Obj:
            def __init__(self):
                self.x = 1
                self.y = "two"

        result = DataBridge.python_to_json(Obj())
        assert result == {"x": 1, "y": "two"}

    def test_primitive_passthrough(self):
        assert DataBridge.python_to_json(42) == 42
        assert DataBridge.python_to_json("str") == "str"
        assert DataBridge.python_to_json(None) is None
        assert DataBridge.python_to_json(True) is True


class TestMarshalContext:
    def test_removes_connection_pool(self):
        ctx = {"query": "SELECT 1", "connection_pool": object(), "rows": 5}
        result = DataBridge.marshal_context(ctx)
        assert "connection_pool" not in result
        assert result["query"] == "SELECT 1"
        assert result["rows"] == 5

    def test_removes_logger(self):
        ctx = {"query": "SELECT 1", "logger": object()}
        result = DataBridge.marshal_context(ctx)
        assert "logger" not in result

    def test_removes_db_connector(self):
        ctx = {"query": "SELECT 1", "db_connector": object()}
        result = DataBridge.marshal_context(ctx)
        assert "db_connector" not in result

    def test_keeps_serializable(self):
        ctx = {"a": 1, "b": "two", "c": [1, 2, 3], "d": {"nested": True}}
        result = DataBridge.marshal_context(ctx)
        assert result == ctx

    def test_non_serializable_to_string(self):
        """Objects that can't be JSON-serialized are stringified, not dropped."""
        ctx = {"obj": object()}
        result = DataBridge.marshal_context(ctx)
        assert "obj" in result
        assert isinstance(result["obj"], str)

    def test_datetime_preserved(self):
        dt = datetime(2026, 10, 8, 12, 0, 0)
        ctx = {"when": dt}
        result = DataBridge.marshal_context(ctx)
        # datetime is JSON-serializable via the default handler, so it stays
        assert result["when"] == dt


class TestJsonToPython:
    def test_dict_recursion(self):
        data = {"a": 1, "b": {"c": 2}}
        result = DataBridge.json_to_python(data)
        assert result == data

    def test_list_recursion(self):
        data = [1, [2, 3], {"x": 4}]
        result = DataBridge.json_to_python(data)
        assert result == data

    def test_primitive_passthrough(self):
        assert DataBridge.json_to_python(42) == 42
        assert DataBridge.json_to_python("str") == "str"
        assert DataBridge.json_to_python(None) is None
        assert DataBridge.json_to_python(True) is True

    def test_nested_structure(self):
        data = {
            "rows": [
                {"id": 1, "name": "Alice"},
                {"id": 2, "name": "Bob"},
            ],
            "meta": {"count": 2},
        }
        result = DataBridge.json_to_python(data)
        assert result == data
