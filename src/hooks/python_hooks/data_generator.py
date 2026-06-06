# ----------------------------------------------------------------------
# SQL Schema Studio 0.9 - Synthetic Data Generator Hook (GPLv3)
# Copyright (C) 2026 Peter Leukanič
# License: GNU GPL v3+ <https://www.gnu.org/licenses/gpl-3.0.txt>
# This is free software with NO WARRANTY.
# Feel free to distribute and modify.
# ----------------------------------------------------------------------

"""Hook that generates synthetic test data for benchmarking."""

import time
import threading
from datetime import datetime
from src.hooks.base_plugin import BaseHook, HookContext, HookTrigger
from src.utils.logging import get_logger

logger = get_logger(__name__)

# Default schema for synthetic supermarket data
TABLE_SCHEMA = """
    invoice_id SERIAL PRIMARY KEY,
    branch TEXT,
    city TEXT,
    customer_type TEXT,
    gender TEXT,
    product_line TEXT,
    unit_price REAL,
    quantity INTEGER,
    payment TEXT
"""


class Plugin(BaseHook):
    """Synthetic data generator for testing and benchmarking."""

    def get_metadata(self):
        return {
            "name": "Synthetic Data Generator",
            "version": "1.0.0",
            "author": "SQL Schema Studio",
            "description": "Generates synthetic supermarket data for testing hooks and performance",
            "triggers": [HookTrigger.SCHEDULED_INTERVAL.value],
        }

    async def execute(self, context: HookContext) -> dict:
        """Abstract method — delegates to execute_sync."""
        conn_string = context.data.get("conn_string", "")
        return self.execute_sync(conn_string)

    def execute_sync(self, conn_string: str) -> dict:
        """Generate synthetic data synchronously."""
        import psycopg
        from faker import Faker

        try:
            fake = Faker()
            conn = psycopg.connect(conn_string)
            conn.autocommit = True
            cur = conn.cursor()

            # Create table if not exists
            cur.execute(f"""
                CREATE TABLE IF NOT EXISTS supermarket (
                    {TABLE_SCHEMA}
                )
            """)

            # Generate rows
            rows = []
            count = 100  # Default: 100 rows per run
            for _ in range(count):
                rows.append((
                    fake.random_element(["A", "B", "C"]),
                    fake.city(),
                    fake.random_element(["Member", "Normal"]),
                    fake.random_element(["Male", "Female"]),
                    fake.random_element(["Electronics", "Food", "Clothing"]),
                    round(fake.random_number(digits=2) + fake.random.random(), 2),
                    fake.random_int(1, 10),
                    fake.random_element(["Cash", "Credit Card", "E-wallet"]),
                ))

            # Batch insert
            for row in rows:
                cur.execute(
                    "INSERT INTO supermarket (branch, city, customer_type, gender, "
                    "product_line, unit_price, quantity, payment) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)", row
                )

            conn.close()

            return {
                "status": "ok",
                "message": f"Generated {count} rows in supermarket table",
                "tables_analyzed": 1,
                "recommendations_count": 0,
                "recommendations": [{
                    "table": "public.supermarket",
                    "priority": "INFO",
                    "action": "Data generated",
                    "reason": f"Added {count} synthetic supermarket records for testing",
                    "sql": f"-- {count} rows inserted into supermarket",
                }],
            }

        except Exception as e:
            logger.error(f"Data generator failed: {e}")
            return {"status": "error", "message": str(e)}
