# ----------------------------------------------------------------------
# SQL Schema Studio 0.9 - Synthetic Data Generator Hook (GPLv3)
# Copyright (C) 2026 Peter Leukanič
# License: GNU GPL v3+ <https://www.gnu.org/licenses/gpl-3.0.txt>
# This is free software with NO WARRANTY.
# Feel free to distribute and modify.
# ----------------------------------------------------------------------

"""Hook that generates synthetic test data for benchmarking.

This hook uses the Faker library to generate realistic test data
for various presets (Supermarket, Users, E-Commerce).
Supports both single-CPU and multi-CPU generation modes.
"""

from typing import Any, Dict, List

from src.hooks.base_plugin import BaseHook, HookContext, HookTrigger
from src.utils.logging import get_logger

logger = get_logger(__name__)

# Available data presets with their column definitions and parameters
PRESETS: Dict[str, Dict[str, Any]] = {
    "Supermarket": {
        "table": "supermarket",
        "columns": {
            "branch": "random_element",
            "city": "city",
            "customer_type": "random_element",
            "gender": "random_element",
            "product_line": "random_element",
            "unit_price": "pyfloat",
            "quantity": "random_int",
            "payment": "random_element",
        },
        "params": {
            "branch": {"elements": ["A", "B", "C"]},
            "customer_type": {"elements": ["Member", "Normal"]},
            "gender": {"elements": ["Male", "Female"]},
            "product_line": {"elements": ["Electronics", "Food", "Clothing"]},
            "unit_price": {"right_digits": 2, "positive": True, "min_value": 1, "max_value": 100},
            "quantity": {"min": 1, "max": 10},
            "payment": {"elements": ["Cash", "Credit Card", "E-wallet"]},
        },
    },
    "Users": {
        "table": "users",
        "columns": {
            "name": "name",
            "email": "email",
            "phone": "phone_number",
            "address": "address",
            "company": "company",
            "job": "job",
            "birth_date": "date_of_birth",
        },
        "params": {},
    },
    "E-Commerce": {
        "table": "products",
        "columns": {
            "name": "catch_phrase",
            "description": "text",
            "price": "pyfloat",
            "sku": "ean13",
            "category": "random_element",
            "stock": "random_int",
            "rating": "pyfloat",
        },
        "params": {
            "price": {"right_digits": 2, "positive": True, "min_value": 5, "max_value": 500},
            "category": {"elements": ["Electronics", "Books", "Clothing", "Food", "Sports"]},
            "stock": {"min": 0, "max": 100},
            "rating": {"right_digits": 1, "positive": True, "min_value": 1, "max_value": 5},
        },
    },
}

# SQL schema definitions for each table
TABLE_SCHEMAS: Dict[str, str] = {
    "supermarket": """
        invoice_id SERIAL PRIMARY KEY,
        branch TEXT,
        city TEXT,
        customer_type TEXT,
        gender TEXT,
        product_line TEXT,
        unit_price REAL,
        quantity INTEGER,
        payment TEXT
    """,
    "users": """
        id SERIAL PRIMARY KEY,
        name TEXT,
        email TEXT,
        phone TEXT,
        address TEXT,
        company TEXT,
        job TEXT,
        birth_date TEXT
    """,
    "products": """
        id SERIAL PRIMARY KEY,
        name TEXT,
        description TEXT,
        price REAL,
        sku TEXT,
        category TEXT,
        stock INTEGER,
        rating REAL
    """,
}


class Plugin(BaseHook):
    """Synthetic data generator for testing and benchmarking.

    This hook generates realistic test data using the Faker library.
    It supports multiple presets and can use multiple CPU cores for
    large data generation tasks.
    """

    def get_metadata(self) -> Dict[str, Any]:
        """Return hook metadata for the plugin system."""
        return {
            "name": "Synthetic Data Generator",
            "version": "1.0.0",
            "author": "SQL Schema Studio",
            "description": "Generates synthetic data for testing hooks and performance.",
            "triggers": str(HookTrigger.SCHEDULED_INTERVAL.value),  # Zmeň na str
        }

    async def execute(self, context: HookContext) -> Dict[str, Any]:
        """Execute the hook asynchronously.

        Args:
            context: Hook context containing:
                - conn_string: Database connection string
                - preset: Data preset name (Supermarket, Users, E-Commerce)
                - count: Number of rows to generate
                - drop_existing: Whether to drop existing table
                - use_multi_cpu: Whether to use multiple CPU cores
        """
        conn_string = context.data.get("conn_string", "")
        preset = context.data.get("preset", "Supermarket")
        count = context.data.get("count", 100)
        drop_existing = context.data.get("drop_existing", False)
        use_multi_cpu = context.data.get("use_multi_cpu", False)
        return self.execute_sync(conn_string, preset, count, drop_existing, use_multi_cpu)

    def execute_sync(
        self,
        conn_string: str,
        preset: str = "Supermarket",
        count: int = 100,
        drop_existing: bool = False,
        use_multi_cpu: bool = False,
    ) -> Dict[str, Any]:
        """Generate synthetic data synchronously.

        This is the main entry point for data generation. It connects to the
        database, creates the table if needed, and inserts synthetic data.

        Args:
            conn_string: PostgreSQL connection string
            preset: Name of the data preset to use
            count: Number of rows to generate
            drop_existing: If True, drop and recreate the table
            use_multi_cpu: If True, use multiple CPU cores for generation

        Returns:
            Dict with status, message, and recommendations
        """
        import psycopg
        from faker import Faker

        try:
            # Validate preset
            if preset not in PRESETS:
                return {"status": "error", "message": f"Unknown preset: {preset}"}

            # Get preset configuration
            preset_config = PRESETS[preset]
            table_name: str = preset_config["table"]
            columns: Dict[str, str] = preset_config["columns"]
            params: Dict[str, Any] = preset_config.get("params", {})
            schema: str = TABLE_SCHEMAS[table_name]

            fake = Faker()
            conn = psycopg.connect(conn_string)
            conn.autocommit = True
            cur = conn.cursor()

            # Create table if requested
            if drop_existing:
                cur.execute(f"DROP TABLE IF EXISTS {table_name} CASCADE")
            cur.execute(f"CREATE TABLE IF NOT EXISTS {table_name} ({schema})")

            # Get column names as a list
            col_names: List[str] = list(columns.keys())

            # Multi-CPU mode for large datasets
            if use_multi_cpu and count > 1000:
                from src.hooks.python_hooks.data_generator import _generate_chunk as worker
                from src.core.worker_pool import get_pool

                pool = get_pool()
                workers = pool._max_workers
                chunk_size = count // workers
                futures = []
                for i in range(workers):
                    start = i * chunk_size
                    end = start + chunk_size if i < workers - 1 else count
                    futures.append(
                        pool.submit(
                            worker,
                            conn_string,
                            table_name,
                            col_names,
                            preset,
                            end - start,
                        )
                    )

                total = sum(f.result() for f in futures)
                conn.close()
            else:
                # Single-CPU mode
                placeholders = ", ".join(["%s"] * len(col_names))
                col_list = ", ".join(col_names)

                for _ in range(count):
                    # Build row using column definitions
                    row: List[Any] = []
                    for col in col_names:
                        faker_method = columns[col]
                        params_for_col = params.get(col, {})
                        # Get the faker method and call it with parameters
                        method = getattr(fake, faker_method)
                        if params_for_col:
                            row.append(method(**params_for_col))
                        else:
                            row.append(method())

                    cur.execute(
                        f"INSERT INTO {table_name} ({col_list}) VALUES ({placeholders})", tuple(row)
                    )
                total = count
                conn.close()

            # Build the result dictionary with explicit type annotation for the whole dict
            result: Dict[str, Any] = {
                "status": "ok",
                "message": f"Generated {total} rows in {table_name} table ({preset} preset)"
                + (" [multi-CPU]" if use_multi_cpu else ""),
                "tables_analyzed": 1,
                "recommendations_count": 1,
                "recommendations": [
                    {
                        "table": f"public.{table_name}",
                        "priority": "INFO",
                        "action": f"Data generated ({preset})",
                        "reason": f"Added {total} synthetic records for testing",
                        "sql": f"-- {total} rows inserted into {table_name}",
                    }
                ],
            }

            return result

        except Exception as e:
            logger.error(f"Data generator failed: {e}")
            return {"status": "error", "message": str(e)}


def _generate_chunk(
    conn_string: str, table_name: str, col_names: List[str], preset: str, count: int
) -> int:
    """Generate a chunk of data in a separate process.

    This function is designed to be called by ProcessPoolExecutor for
    parallel data generation across multiple CPU cores.

    Args:
        conn_string: PostgreSQL connection string
        table_name: Name of the table to insert into
        col_names: List of column names
        preset: Name of the data preset
        count: Number of rows to generate

    Returns:
        Number of rows successfully inserted
    """
    import psycopg
    from faker import Faker

    # Get preset configuration
    preset_config = PRESETS[preset]
    columns: Dict[str, str] = preset_config["columns"]
    params: Dict[str, Any] = preset_config.get("params", {})
    fake = Faker()

    conn = psycopg.connect(conn_string)
    conn.autocommit = True
    cur = conn.cursor()

    placeholders = ", ".join(["%s"] * len(col_names))
    col_list = ", ".join(col_names)

    for _ in range(count):
        # Build row using column definitions
        row: List[Any] = []
        for col in col_names:
            faker_method = columns[col]
            params_for_col = params.get(col, {})
            # Get the faker method and call it with parameters
            method = getattr(fake, faker_method)
            if params_for_col:
                row.append(method(**params_for_col))
            else:
                row.append(method())

        cur.execute(f"INSERT INTO {table_name} ({col_list}) VALUES ({placeholders})", tuple(row))

    conn.close()
    return count
