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

    def execute_sync(self, conn_string: str, preset: str = "Supermarket", count: int = 100, drop_existing: bool = False) -> dict:
        
        """Generate synthetic data synchronously.
        
        Args:
            conn_string: PostgreSQL connection string
            preset: One of 'Supermarket', 'Users', 'E-Commerce'
            count: Number of rows to generate
        """
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

            # Drop the previous
            if drop_existing:
                cur.execute(f"DROP TABLE IF EXISTS {table_name} CASCADE")
                logger.info(f"Dropped existing table: {table_name}")
            
            # Create table
            cur.execute(f"CREATE TABLE IF NOT EXISTS {table_name} ({schema})")

            # Generate rows
            rows = []
            for _ in range(count):
                row = []
                for col_name, faker_method in columns.items():
                    col_params = params.get(col_name, {})
                    value = getattr(fake, faker_method)(**col_params)
                    row.append(value)
                rows.append(tuple(row))

            # Batch insert
            col_names = list(columns.keys())
            placeholders = ", ".join(["%s"] * len(col_names))
            col_list = ", ".join(col_names)
            
            for row in rows:
                cur.execute(
                    f"INSERT INTO {table_name} ({col_list}) VALUES ({placeholders})", row
                )

            conn.close()

            return {
                "status": "ok",
                "message": f"Generated {count} rows in {table_name} table ({preset} preset)",
                "tables_analyzed": 1,
                "recommendations_count": 1,
                "recommendations": [{
                    "table": f"public.{table_name}",
                    "priority": "INFO",
                    "action": f"Data generated ({preset})",
                    "reason": f"Added {count} synthetic records for testing",
                    "sql": f"-- {count} rows inserted into {table_name}",
                }],
            }

        except Exception as e:
            logger.error(f"Data generator failed: {e}")
            return {"status": "error", "message": str(e)}
