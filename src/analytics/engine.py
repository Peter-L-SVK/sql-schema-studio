# ----------------------------------------------------------------------
# SQL Schema Studio 0.9 - Polars Analytics Engine (GPLv3)
# Copyright (C) 2026 Peter Leukanič
# License: GNU GPL v3+ <https://www.gnu.org/licenses/gpl-3.0.txt>
# This is free software with NO WARRANTY.
# Feel free to distribute and modify.
# ----------------------------------------------------------------------

"""Fast analytics engine using Polars DataFrame library."""

from __future__ import annotations

from typing import Optional

import polars as pl

from src.utils.logging import get_logger

logger = get_logger(__name__)


class AnalyticsEngine:
    """Fast analytics engine using Polars instead of pandas.

    Polars is written in Rust, uses Arrow memory layout, and is
    significantly faster than pandas for large datasets while
    using less memory.
    """

    def __init__(self, db_connector):
        self._db = db_connector

    def table_stats_safe(self, schema: str, table: str) -> dict:
        """Get table statistics with safe defaults for all keys.

        Use this when calling from UI code that doesn't want to handle
        missing keys. Always returns all expected keys with defaults.
        """
        try:
            df = self.query_to_df(f'SELECT * FROM {schema}."{table}"')

            if df.is_empty():
                return {
                    "row_count": 0,
                    "column_count": 0,
                    "columns": [],
                    "estimated_size_mb": 0,
                    "null_percentages": {},
                }

            return {
                "row_count": len(df),
                "column_count": len(df.columns),
                "columns": df.columns,
                "estimated_size_mb": round(df.estimated_size() / (1024 * 1024), 2),
                "null_percentages": {
                    c: round(df[c].null_count() / len(df) * 100, 2) if len(df) > 0 else 0
                    for c in df.columns
                },
            }
        except Exception as e:
            logger.error(f"table_stats_safe failed for {schema}.{table}: {e}")
            return {
                "row_count": 0,
                "column_count": 0,
                "columns": [],
                "estimated_size_mb": 0,
                "null_percentages": {},
                "error": str(e),
            }

    def query_to_df(self, query: str, params: tuple | None = None) -> pl.DataFrame:
        """Execute SQL query and return Polars DataFrame.

        Args:
            query: SQL query string.
            params: Optional query parameters.

        Returns:
            Polars DataFrame with query results.
        """
        results = self._db.execute_sync(query, params)
        if not results:
            return pl.DataFrame()
        return pl.DataFrame(results)

    def table_stats(self, schema: str, table: str) -> dict:
        """Get comprehensive table statistics.

        Returns:
            Dict with row_count, columns, null_counts, distinct_counts,
            memory_usage, and column types.
        """
        df = self.query_to_df(f'SELECT * FROM {schema}."{table}"')

        if df.is_empty():
            return {"row_count": 0, "columns": [], "empty": True}

        return {
            "row_count": len(df),
            "column_count": len(df.columns),
            "columns": df.columns,
            "dtypes": {c: str(df[c].dtype) for c in df.columns},
            "null_counts": {c: df[c].null_count() for c in df.columns},
            "null_percentages": {
                c: round(df[c].null_count() / len(df) * 100, 2) if len(df) > 0 else 0
                for c in df.columns
            },
            "estimated_size_bytes": df.estimated_size(),
            "estimated_size_mb": round(df.estimated_size() / (1024 * 1024), 2),
        }

    def column_profile(self, schema: str, table: str, column: str) -> dict:
        """Get detailed profile for a single column.

        Returns:
            Dict with min, max, mean, median, std, unique count,
            null count, and top values.
        """
        df = self.query_to_df(f'SELECT "{column}" FROM {schema}."{table}"')

        if df.is_empty():
            return {"empty": True}

        col = df[column]
        profile = {
            "name": column,
            "dtype": str(col.dtype),
            "count": len(col),
            "null_count": col.null_count(),
            "null_percentage": round(col.null_count() / len(col) * 100, 2) if len(col) > 0 else 0,
            "unique_count": col.n_unique(),
        }

        # Numeric statistics
        if col.dtype in (pl.Int64, pl.Float64, pl.Int32, pl.Float32):
            profile.update(
                {
                    "min": col.min(),
                    "max": col.max(),
                    "mean": round(col.mean(), 2) if col.mean() is not None else None,
                    "median": col.median(),
                    "std": round(col.std(), 2) if col.std() is not None else None,
                    "sum": col.sum(),
                }
            )

        # String statistics
        if col.dtype == pl.Utf8:
            lengths = col.str.len_chars()
            profile.update(
                {
                    "min_length": lengths.min(),
                    "max_length": lengths.max(),
                    "mean_length": round(lengths.mean(), 1) if lengths.mean() is not None else None,
                    "empty_count": col.str.len_chars().eq(0).sum(),
                }
            )

        # Top values
        if col.n_unique() > 0 and col.n_unique() <= 100:
            value_counts = col.value_counts().sort("count", descending=True).head(10)
            profile["top_values"] = value_counts.to_dict(as_series=False)

        return profile

    def compare_tables(self, schema: str, table1: str, table2: str) -> dict:
        """Compare two tables for schema and data differences.

        Returns:
            Dict with schema_diff, row_count_diff, and column_diffs.
        """
        t1_cols = self._get_columns(schema, table1)
        t2_cols = self._get_columns(schema, table2)

        t1_names = {c["column_name"] for c in t1_cols}
        t2_names = {c["column_name"] for c in t2_cols}

        return {
            "table1": f"{schema}.{table1}",
            "table2": f"{schema}.{table2}",
            "table1_columns": len(t1_cols),
            "table2_columns": len(t2_cols),
            "columns_only_in_table1": list(t1_names - t2_names),
            "columns_only_in_table2": list(t2_names - t1_names),
            "common_columns": list(t1_names & t2_names),
        }

    def correlation_matrix(self, schema: str, table: str) -> Optional[pl.DataFrame]:
        """Calculate correlation matrix for numeric columns.

        Returns:
            Polars DataFrame with correlation values, or None if no numeric columns.
        """
        df = self.query_to_df(f'SELECT * FROM {schema}."{table}"')
        if df.is_empty():
            return None

        numeric_cols = [
            c for c in df.columns if df[c].dtype in (pl.Int64, pl.Float64, pl.Int32, pl.Float32)
        ]

        if len(numeric_cols) < 2:
            return None

        return df[numeric_cols].corr()

    def export_to_csv(self, df: pl.DataFrame, path: str) -> None:
        """Export DataFrame to CSV file."""
        df.write_csv(path)
        logger.info(f"Exported {len(df)} rows to {path}")

    def export_to_json(self, df: pl.DataFrame, path: str) -> None:
        """Export DataFrame to JSON file."""
        df.write_json(path)
        logger.info(f"Exported {len(df)} rows to {path}")

    def export_to_parquet(self, df: pl.DataFrame, path: str) -> None:
        """Export DataFrame to Parquet file (fast binary format)."""
        df.write_parquet(path)
        logger.info(f"Exported {len(df)} rows to {path}")

    # =====================================================================
    # Helpers
    # =====================================================================

    def _get_columns(self, schema: str, table: str) -> list[dict]:
        """Get column information for a table."""
        return self._db.execute_sync(
            """SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_schema = %s AND table_name = %s
            ORDER BY ordinal_position""",
            (schema, table),
        )
