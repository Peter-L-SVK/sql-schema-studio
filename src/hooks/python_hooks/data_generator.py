# ----------------------------------------------------------------------
# SQL Schema Studio 0.9 - Synthetic Data Generator Hook (GPLv3)
# Copyright (C) 2026 Peter Leukanič
# License: GNU GPL v3+ <https://www.gnu.org/licenses/gpl-3.0.txt>
# This is free software with NO WARRANTY.
# Feel free to distribute and modify.
# ----------------------------------------------------------------------

"""Hook that generates synthetic test data for benchmarking."""

from src.hooks.base_plugin import BaseHook, HookContext, HookTrigger
from src.utils.logging import get_logger

logger = get_logger(__name__)

# Available data presets
PRESETS = {
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

TABLE_SCHEMAS = {
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
    """Synthetic data generator for testing and benchmarking."""

    def get_metadata(self):
        return {
            "name": "Synthetic Data Generator",
            "version": "1.0.0",
            "author": "SQL Schema Studio",
            "description": "Generates synthetic data for testing hooks and performance. Supports multiple presets: Supermarket, Users, E-Commerce.",
            "triggers": [HookTrigger.SCHEDULED_INTERVAL.value],
        }

    async def execute(self, context: HookContext) -> dict:
        """Abstract method — delegates to execute_sync."""
        conn_string = context.data.get("conn_string", "")
        preset = context.data.get("preset", "Supermarket")
        count = context.data.get("count", 100)
        return self.execute_sync(conn_string, preset, count)

    def execute_sync(
        self,
        conn_string: str,
        preset: str = "Supermarket",
        count: int = 100,
        drop_existing: bool = False,
        use_multi_cpu: bool = False,
    ) -> dict:
        """Generate synthetic data synchronously."""
        import psycopg
        from faker import Faker

        try:
            if preset not in PRESETS:
                return {"status": "error", "message": f"Unknown preset: {preset}"}

            preset_config = PRESETS[preset]
            table_name = preset_config["table"]
            columns = preset_config["columns"]
            params = preset_config["params"]
            schema = TABLE_SCHEMAS[table_name]

            fake = Faker()
            conn = psycopg.connect(conn_string)
            conn.autocommit = True
            cur = conn.cursor()

            # Create table
            if drop_existing:
                cur.execute(f"DROP TABLE IF EXISTS {table_name} CASCADE")
            cur.execute(f"CREATE TABLE IF NOT EXISTS {table_name} ({schema})")

            if use_multi_cpu and count > 1000:
                # Multi-CPU mode — split work across processes
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
                            list(columns.keys()),
                            preset,
                            end - start,
                        )
                    )

                total = sum(f.result() for f in futures)
                conn.close()
            else:
                # Single-CPU mode
                col_names = list(columns.keys())
                placeholders = ", ".join(["%s"] * len(col_names))
                col_list = ", ".join(col_names)

                for _ in range(count):
                    row = tuple(
                        getattr(fake, columns[col])(**params.get(col, {})) for col in col_names
                    )
                    cur.execute(
                        f"INSERT INTO {table_name} ({col_list}) VALUES ({placeholders})", row
                    )
                total = count
                conn.close()

            return {
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

        except Exception as e:
            logger.error(f"Data generator failed: {e}")
            return {"status": "error", "message": str(e)}


def _generate_chunk(
    conn_string: str, table_name: str, col_names: list, preset: str, count: int
) -> int:
    """Generate a chunk of data in a separate process."""
    import psycopg
    from faker import Faker

    preset_config = PRESETS[preset]
    columns = preset_config["columns"]
    params = preset_config["params"]
    fake = Faker()

    conn = psycopg.connect(conn_string)
    conn.autocommit = True
    cur = conn.cursor()

    placeholders = ", ".join(["%s"] * len(col_names))
    col_list = ", ".join(col_names)

    for _ in range(count):
        row = tuple(getattr(fake, columns[col])(**params.get(col, {})) for col in col_names)
        cur.execute(f"INSERT INTO {table_name} ({col_list}) VALUES ({placeholders})", row)

    conn.close()
    return count
