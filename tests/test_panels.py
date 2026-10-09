# ----------------------------------------------------------------------
# SQL Schema Studio 0.9.5 - Results Panel Tests (GPLv3)
# Copyright (C) 2026 Peter Leukanič
# License: GNU GPL v3+ <https://www.gnu.org/licenses/gpl-3.0.txt>
# This is free software with NO WARRANTY.
# Feel free to distribute and modify.
# ----------------------------------------------------------------------

"""Tests for ResultsPanel.format_data_type().

The GUI parts of ResultsPanel need a display and are covered by manual
testing. This file tests only the static helper that has no GTK deps.
"""

from src.ui.results.panels import ResultsPanel


class TestFormatDataType:
    # --- Simple types (no parameters) ---

    def test_integer(self):
        assert ResultsPanel.format_data_type("integer") == "integer"

    def test_bigint(self):
        assert ResultsPanel.format_data_type("bigint") == "bigint"

    def test_text(self):
        assert ResultsPanel.format_data_type("text") == "text"

    def test_boolean(self):
        assert ResultsPanel.format_data_type("boolean") == "boolean"

    def test_date(self):
        assert ResultsPanel.format_data_type("date") == "date"

    # --- Types with length ---

    def test_varchar_with_length(self):
        assert ResultsPanel.format_data_type("character varying", length=50) == "varchar(50)"

    def test_char_with_length(self):
        assert ResultsPanel.format_data_type("character", length=10) == "char(10)"

    def test_varchar_basic(self):
        assert ResultsPanel.format_data_type("varchar", length=255) == "varchar(255)"

    # --- Types with precision/scale ---

    def test_numeric_with_precision_and_scale(self):
        result = ResultsPanel.format_data_type("numeric", precision=10, scale=2)
        assert result == "numeric(10,2)"

    def test_numeric_with_precision_only(self):
        result = ResultsPanel.format_data_type("numeric", precision=10)
        assert result == "numeric(10)"

    def test_decimal_with_precision(self):
        result = ResultsPanel.format_data_type("decimal", precision=8, scale=3)
        assert result == "decimal(8,3)"

    # --- Verbose PostgreSQL type shortening ---

    def test_timestamp_without_time_zone(self):
        assert ResultsPanel.format_data_type("timestamp without time zone") == "timestamp"

    def test_timestamp_with_time_zone(self):
        assert ResultsPanel.format_data_type("timestamp with time zone") == "timestamptz"

    def test_time_without_time_zone(self):
        assert ResultsPanel.format_data_type("time without time zone") == "time"

    def test_time_with_time_zone(self):
        assert ResultsPanel.format_data_type("time with time zone") == "timetz"

    def test_double_precision(self):
        assert ResultsPanel.format_data_type("double precision") == "double"

    # --- Length takes priority over precision ---

    def test_length_wins_over_precision(self):
        """If both are given, length wins (matches the code's if/elif)."""
        result = ResultsPanel.format_data_type("numeric", length=10, precision=8, scale=2)
        assert result == "numeric(10)"

    # --- Unknown types pass through ---

    def test_unknown_type_unchanged(self):
        assert ResultsPanel.format_data_type("my_custom_type") == "my_custom_type"

    def test_unknown_type_with_length(self):
        assert ResultsPanel.format_data_type("my_type", length=20) == "my_type(20)"

    # --- Edge cases ---

    def test_zero_scale(self):
        """scale=0 is falsy — should fall through to precision-only path."""
        result = ResultsPanel.format_data_type("numeric", precision=10, scale=0)
        assert result == "numeric(10)"

    def test_none_values_ignored(self):
        """All None params → base type only."""
        result = ResultsPanel.format_data_type("integer", length=None, precision=None, scale=None)
        assert result == "integer"
