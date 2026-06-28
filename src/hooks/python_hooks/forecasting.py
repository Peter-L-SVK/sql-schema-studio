# ----------------------------------------------------------------------
# SQL Schema Studio - Forecasting Hook (GPLv3)
# Copyright (C) 2026 Peter Leukanič
# License: GNU GPL v3+ <https://www.gnu.org/licenses/gpl-3.0.txt>
# This is free software with NO WARRANTY.
# Feel free to distribute and modify.
# ----------------------------------------------------------------------

"""Smart Excel-like predictive functions for data scientists."""

from typing import Any, Dict

import numpy as np
import polars as pl

from src.hooks.base_plugin import BaseHook, HookContext


class ForecastingHook(BaseHook):
    """Predictive analytics: trend forecast, moving average, anomaly detection.

    Trigger: QUERY_EXECUTED — run forecasting on query results.
    """

    def get_metadata(self) -> Dict[str, Any]:
        return {
            "name": "Forecasting",
            "version": "0.9.0",
            "author": "Peter Leukanič",
            "description": "Excel-like predictive functions: trend, moving average, "
            "exponential smoothing, percentile bands, anomaly detection",
            "triggers": ["query.executed"],
        }

    async def execute(self, context: HookContext) -> Dict[str, Any]:
        """Route to the requested forecasting function based on context data."""
        df = context.data.get("dataframe")
        if df is None:
            return {"error": "No Polars DataFrame in context"}

        func = str(context.data.get("function", "trend_forecast"))
        col = context.data.get("column")
        x_col = context.data.get("x_column")
        params = context.data.get("params", {})

        try:
            if func == "trend_forecast":
                if not x_col or not col:
                    return {"error": "x_column and column required for trend_forecast"}
                return trend_forecast(df, str(x_col), str(col), **params)
            elif func == "moving_average":
                if not col:
                    return {"error": "column required for moving_average"}
                result = moving_average(df, str(col), **params)
                return {"dataframe": result}
            elif func == "exponential_forecast":
                if not col:
                    return {"error": "column required for exponential_forecast"}
                result = exponential_forecast(df, str(col), **params)
                return {"dataframe": result}
            elif func == "percentile_bands":
                if not col:
                    return {"error": "column required for percentile_bands"}
                return percentile_bands(df, str(col))
            elif func == "anomaly_detect":
                if not col:
                    return {"error": "column required for anomaly_detect"}
                result = anomaly_detect(df, str(col), **params)
                return {"dataframe": result}
            else:
                return {"error": f"Unknown function: {func}"}
        except Exception as e:
            return {"error": str(e)}

    def execute_sync(self, conn_string: str) -> Dict[str, Any]:
        """Sync entry point — query the DB and run forecasting.

        Called by Hook Manager when user clicks Run with an active
        database connection.
        """
        import psycopg2

        try:
            conn = psycopg2.connect(conn_string)
        except Exception as e:
            return {"error": f"Connection failed: {e}"}

        try:
            cur = conn.cursor()

            # Find user tables with numeric columns
            cur.execute("""
                SELECT table_schema, table_name, column_name, data_type
                FROM information_schema.columns
                WHERE table_schema NOT IN ('pg_catalog', 'information_schema')
                  AND data_type IN ('integer', 'bigint', 'smallint',
                                    'numeric', 'real', 'double precision', 'money')
                ORDER BY table_schema, table_name, ordinal_position
            """)
            rows = cur.fetchall()
            if not rows:
                return {"error": "No numeric columns found in any table"}

            # Use the first numeric column found
            schema, table, column, dtype = rows[0]
            qualified = f'{schema}."{table}"'

            # Count rows
            cur.execute(f"SELECT COUNT(*) FROM {qualified}")
            row_count = cur.fetchone()[0]

            # Fetch the column data
            cur.execute(f'SELECT "{column}" FROM {qualified} WHERE "{column}" IS NOT NULL')
            data = cur.fetchall()

            if not data:
                return {"error": f"No data in {qualified}.{column}"}

            df = pl.DataFrame(data, schema={column: pl.Float64}, orient="row")

            result: Dict[str, Any] = {
                "table": qualified,
                "column": column,
                "type": dtype,
                "row_count": row_count,
                "percentiles": percentile_bands(df, column),
            }

            if len(data) >= 3:
                result["trend"] = trend_forecast(df, column, column, periods=3)

            anomaly_df = anomaly_detect(df, column)
            result["anomalies"] = anomaly_df.filter(pl.col(f"{column}_anomaly")).height

            return result

        except Exception as e:
            return {"error": str(e)}
        finally:
            conn.close()


# ---------------------------------------------------------------------------
# Core forecasting functions
# ---------------------------------------------------------------------------


def trend_forecast(df: pl.DataFrame, x_col: str, y_col: str, periods: int = 5) -> dict:
    """Linear TREND forecast (like Excel TREND function).

    Returns predicted y values for next `periods` steps.
    """
    x = df[x_col].to_numpy().astype(float)
    y = df[y_col].to_numpy().astype(float)

    coeffs = np.polyfit(x, y, 1)

    next_x = np.arange(x[-1] + 1, x[-1] + periods + 1)
    predicted = np.polyval(coeffs, next_x)

    return {
        "slope": float(coeffs[0]),
        "intercept": float(coeffs[1]),
        "predictions": predicted.tolist(),
        "r_squared": _r_squared(x, y, coeffs),
    }


def moving_average(df: pl.DataFrame, col: str, window: int = 7) -> pl.DataFrame:
    """Rolling moving average (like Excel AVERAGE with OFFSET)."""
    return df.with_columns(pl.col(col).rolling_mean(window_size=window).alias(f"{col}_ma{window}"))


def exponential_forecast(df: pl.DataFrame, col: str, span: int = 12) -> pl.DataFrame:
    """Exponential smoothing forecast (like Excel FORECAST.ETS)."""
    return df.with_columns(pl.col(col).ewm_mean(span=span, adjust=False).alias(f"{col}_ets"))


def percentile_bands(df: pl.DataFrame, col: str) -> dict:
    """Percentile bands for outlier detection."""
    p10 = float(df[col].quantile(0.10))  # type: ignore[arg-type]
    p25 = float(df[col].quantile(0.25))  # type: ignore[arg-type]
    p50 = float(df[col].median())  # type: ignore[arg-type]
    p75 = float(df[col].quantile(0.75))  # type: ignore[arg-type]
    p90 = float(df[col].quantile(0.90))  # type: ignore[arg-type]

    return {
        "p10": p10,
        "p25": p25,
        "p50": p50,
        "p75": p75,
        "p90": p90,
        "iqr": p75 - p25,
    }


def anomaly_detect(df: pl.DataFrame, col: str, method: str = "iqr") -> pl.DataFrame:
    """Detect anomalies using IQR or z-score method."""
    if method == "iqr":
        q1 = float(df[col].quantile(0.25))  # type: ignore[arg-type]
        q3 = float(df[col].quantile(0.75))  # type: ignore[arg-type]
        iqr = q3 - q1
        lower = q1 - 1.5 * iqr
        upper = q3 + 1.5 * iqr
        return df.with_columns(
            pl.when((pl.col(col) < lower) | (pl.col(col) > upper))
            .then(True)
            .otherwise(False)
            .alias(f"{col}_anomaly")
        )
    else:  # z-score
        mean = float(df[col].mean())  # type: ignore[arg-type]
        std = float(df[col].std())  # type: ignore[arg-type]
        return df.with_columns(
            pl.when(pl.col(col).sub(mean).abs() > 3 * std)
            .then(True)
            .otherwise(False)
            .alias(f"{col}_anomaly")
        )


def _r_squared(x, y, coeffs):
    y_pred = np.polyval(coeffs, x)
    ss_res = np.sum((y - y_pred) ** 2)
    ss_tot = np.sum((y - np.mean(y)) ** 2)
    return 1 - (ss_res / ss_tot)
