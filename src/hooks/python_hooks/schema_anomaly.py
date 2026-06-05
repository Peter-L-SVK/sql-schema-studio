# ----------------------------------------------------------------------
# SQL Schema Studio 0.8 - Schema Anomaly Detector Hook (GPLv3)
# Copyright (C) 2026 Peter Leukanič
# License: GNU GPL v3+ <https://www.gnu.org/licenses/gpl-3.0.txt>
# This is free software with NO WARRANTY.
# Feel free to distribute and modify.
# ----------------------------------------------------------------------

"""Hook that detects poor schema design patterns."""

from src.hooks.base_plugin import BaseHook, HookContext, HookTrigger
from src.utils.logging import get_logger

logger = get_logger(__name__)


class Plugin(BaseHook):
    """Schema anomaly detection hook."""

    def get_metadata(self):
        return {
            "name": "Schema Anomaly Detector",
            "version": "1.1.0",
            "author": "SQL Schema Studio",
            "description": "Detect poor schema design patterns and missing constraints",
            "triggers": [HookTrigger.SCHEMA_CHANGED.value],
        }

    async def execute(self, context: HookContext) -> dict:
        """Abstract method — delegates to execute_sync."""
        conn_string = context.data.get("conn_string", "")
        return self.execute_sync(conn_string)

    def execute_sync(self, conn_string: str) -> dict:
        """Detect schema anomalies synchronously."""
        import psycopg

        try:
            conn = psycopg.connect(conn_string)
            cur = conn.cursor()

            anomalies = []
            tables_analyzed = set()

            # 1. Detect tables without primary keys
            cur.execute("""
                SELECT table_schema, table_name
                FROM information_schema.tables
                WHERE table_schema NOT LIKE 'pg_%'
                  AND table_schema != 'information_schema'
                  AND table_type = 'BASE TABLE'
                  AND (table_schema, table_name) NOT IN (
                      SELECT table_schema, table_name
                      FROM information_schema.table_constraints
                      WHERE constraint_type = 'PRIMARY KEY'
                  )
                ORDER BY table_schema, table_name
            """)

            for row in cur.fetchall():
                table = f"{row[0]}.{row[1]}"
                tables_analyzed.add(table)
                anomalies.append(
                    {
                        "table": table,
                        "priority": "HIGH",
                        "action": "Add primary key",
                        "reason": "Missing primary key - table cannot be properly indexed or replicated",
                        "sql": f"ALTER TABLE {row[0]}.{row[1]} ADD COLUMN id SERIAL PRIMARY KEY;",
                    }
                )

            # 2. Detect columns named *_id without foreign keys
            cur.execute("""
                SELECT
                    c.table_schema,
                    c.table_name,
                    c.column_name,
                    c.data_type
                FROM information_schema.columns c
                WHERE c.table_schema NOT LIKE 'pg_%'
                  AND c.table_schema != 'information_schema'
                  AND c.column_name LIKE '%_id'
                  AND c.column_name != 'id'
                  AND (c.table_schema, c.table_name, c.column_name) NOT IN (
                      SELECT
                          kcu.table_schema,
                          kcu.table_name,
                          kcu.column_name
                      FROM information_schema.key_column_usage kcu
                      JOIN information_schema.table_constraints tc
                        ON kcu.constraint_name = tc.constraint_name
                      WHERE tc.constraint_type = 'FOREIGN KEY'
                  )
                ORDER BY c.table_schema, c.table_name, c.column_name
            """)

            for row in cur.fetchall():
                table = f"{row[0]}.{row[1]}"
                column = row[2]
                tables_analyzed.add(table)
                anomalies.append(
                    {
                        "table": table,
                        "priority": "MEDIUM",
                        "action": "Add foreign key constraint",
                        "reason": f"Column '{column}' looks like a foreign key but has no FK constraint - data integrity at risk",
                        "sql": f"-- Find referenced table first, then add FK:\n-- ALTER TABLE {table} ADD CONSTRAINT fk_{row[1]}_{column} FOREIGN KEY ({column}) REFERENCES ? (id);",
                    }
                )

            # 3. Detect tables without any indexes (excluding PK)
            cur.execute("""
                SELECT table_schema, table_name
                FROM information_schema.tables t
                WHERE t.table_schema NOT LIKE 'pg_%'
                  AND t.table_schema != 'information_schema'
                  AND t.table_type = 'BASE TABLE'
                  AND (t.table_schema, t.table_name) NOT IN (
                      SELECT schemaname, tablename
                      FROM pg_indexes
                      WHERE schemaname NOT LIKE 'pg_%'
                        AND indexname NOT LIKE '%_pkey'
                  )
                ORDER BY t.table_schema, t.table_name
            """)

            for row in cur.fetchall():
                table = f"{row[0]}.{row[1]}"
                tables_analyzed.add(table)
                anomalies.append(
                    {
                        "table": table,
                        "priority": "LOW",
                        "action": "Add indexes on frequently queried columns",
                        "reason": "No indexes found (besides primary key) -may cause full table scans and performance issues",
                        "sql": f"-- Review query patterns and add indexes on {table}\n-- Example: CREATE INDEX idx_{row[1]}_column ON {table} (column);",
                    }
                )

            # 4. Detect VARCHAR without length
            cur.execute("""
                SELECT table_schema, table_name, column_name, data_type
                FROM information_schema.columns
                WHERE table_schema NOT LIKE 'pg_%'
                  AND table_schema != 'information_schema'
                  AND data_type IN ('character varying', 'varchar')
                  AND character_maximum_length IS NULL
                ORDER BY table_schema, table_name, column_name
            """)

            for row in cur.fetchall():
                table = f"{row[0]}.{row[1]}"
                column = row[2]
                tables_analyzed.add(table)
                anomalies.append(
                    {
                        "table": table,
                        "priority": "LOW",
                        "action": "Specify VARCHAR length limit",
                        "reason": f"Column '{column}' is VARCHAR without length limit - can allow excessively long values",
                        "sql": f"ALTER TABLE {table} ALTER COLUMN {column} TYPE VARCHAR(255);",
                    }
                )

            # 5. Detect foreign key columns that are nullable (should be NOT NULL)
            cur.execute("""
                SELECT
                    c.table_schema,
                    c.table_name,
                    c.column_name
                FROM information_schema.columns c
                WHERE c.table_schema NOT LIKE 'pg_%'
                  AND c.table_schema != 'information_schema'
                  AND c.column_name LIKE '%_id'
                  AND c.is_nullable = 'YES'
                  AND c.column_name != 'id'
                  AND EXISTS (
                      SELECT 1 FROM information_schema.key_column_usage kcu
                      JOIN information_schema.table_constraints tc
                        ON kcu.constraint_name = tc.constraint_name
                      WHERE tc.constraint_type = 'FOREIGN KEY'
                        AND kcu.table_schema = c.table_schema
                        AND kcu.table_name = c.table_name
                        AND kcu.column_name = c.column_name
                  )
                ORDER BY c.table_schema, c.table_name, c.column_name
            """)

            for row in cur.fetchall():
                table = f"{row[0]}.{row[1]}"
                column = row[2]
                tables_analyzed.add(table)
                anomalies.append(
                    {
                        "table": table,
                        "priority": "MEDIUM",
                        "action": "Add NOT NULL constraint",
                        "reason": f"Foreign key column '{column}' is nullable - references should never be NULL",
                        "sql": f"ALTER TABLE {table} ALTER COLUMN {column} SET NOT NULL;",
                    }
                )

            # 6. Detect foreign keys without indexes (performance critical!)
            cur.execute("""
                SELECT DISTINCT
                    tc.table_schema,
                    tc.table_name,
                    kcu.column_name
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                    ON tc.constraint_name = kcu.constraint_name
                WHERE tc.constraint_type = 'FOREIGN KEY'
                  AND tc.table_schema NOT LIKE 'pg_%'
                  AND tc.table_schema != 'information_schema'
                  AND NOT EXISTS (
                      SELECT 1 FROM pg_indexes pi
                      WHERE pi.schemaname = tc.table_schema
                        AND pi.tablename = tc.table_name
                        AND pi.indexdef LIKE '%' || kcu.column_name || '%'
                        AND pi.indexname NOT LIKE '%_pkey'
                  )
                ORDER BY tc.table_schema, tc.table_name, kcu.column_name
            """)

            for row in cur.fetchall():
                table = f"{row[0]}.{row[1]}"
                column = row[2]
                tables_analyzed.add(table)
                anomalies.append(
                    {
                        "table": table,
                        "priority": "HIGH",
                        "action": "Add index on foreign key column",
                        "reason": f"Foreign key column '{column}' has no index - JOINs and DELETE/UPDATE operations will be slow",
                        "sql": f"CREATE INDEX idx_{row[1]}_{column} ON {row[0]}.{row[1]} ({column});",
                    }
                )

            # 7. Detect tables with high dead tuple ratio (bloat)
            cur.execute("""
                SELECT
                    schemaname,
                    relname AS tablename,
                    n_dead_tup,
                    n_live_tup,
                    round(100.0 * n_dead_tup / NULLIF(n_live_tup + n_dead_tup, 0), 2) as dead_ratio
                FROM pg_stat_user_tables
                WHERE n_dead_tup > 1000
                   OR (n_live_tup + n_dead_tup) > 10000
                ORDER BY dead_ratio DESC
                LIMIT 20
            """)

            for row in cur.fetchall():
                table = f"{row[0]}.{row[1]}"
                tables_analyzed.add(table)
                dead_ratio = row[4]

                priority = "HIGH" if dead_ratio > 30 else "MEDIUM" if dead_ratio > 15 else "LOW"
                anomalies.append(
                    {
                        "table": table,
                        "priority": priority,
                        "action": "Run VACUUM to reclaim space and update statistics",
                        "reason": f"{dead_ratio}% dead tuples ({row[2]:,} dead, {row[3]:,} live) - wasted space and slow queries",
                        "sql": f"VACUUM (VERBOSE, ANALYZE) {row[0]}.{row[1]};",
                    }
                )

            # 8. Detect tables without comments (documentation)
            cur.execute("""
                SELECT
                    c.table_schema,
                    c.table_name
                FROM information_schema.tables c
                WHERE c.table_schema NOT LIKE 'pg_%'
                  AND c.table_schema != 'information_schema'
                  AND c.table_type = 'BASE TABLE'
                  AND (c.table_schema, c.table_name) NOT IN (
                      SELECT
                          schemaname,
                          tablename
                      FROM pg_tables
                      WHERE obj_description((schemaname||'.'||tablename)::regclass) IS NOT NULL
                  )
                ORDER BY c.table_schema, c.table_name
                LIMIT 20
            """)

            for row in cur.fetchall():
                table = f"{row[0]}.{row[1]}"
                tables_analyzed.add(table)
                anomalies.append(
                    {
                        "table": table,
                        "priority": "LOW",
                        "action": "Add table comment for documentation",
                        "reason": "Table has no description - makes schema harder to understand",
                        "sql": f"COMMENT ON TABLE {table} IS 'Description of what this table stores';",
                    }
                )

            # 9. Detect columns that allow NULL but probably shouldn't
            cur.execute("""
                SELECT
                    c.table_schema,
                    c.table_name,
                    c.column_name,
                    c.data_type
                FROM information_schema.columns c
                WHERE c.table_schema NOT LIKE 'pg_%'
                  AND c.table_schema != 'information_schema'
                  AND c.is_nullable = 'YES'
                  AND c.column_name IN ('name', 'title', 'email', 'username', 'created_at', 'updated_at')
                  AND NOT EXISTS (
                      SELECT 1 FROM information_schema.key_column_usage kcu
                      WHERE kcu.column_name = c.column_name
                  )
                ORDER BY c.table_schema, c.table_name, c.column_name
                LIMIT 20
            """)

            for row in cur.fetchall():
                table = f"{row[0]}.{row[1]}"
                column = row[2]
                tables_analyzed.add(table)
                anomalies.append(
                    {
                        "table": table,
                        "priority": "LOW",
                        "action": "Consider adding NOT NULL constraint",
                        "reason": f"Column '{column}' probably should not be NULL based on its name",
                        "sql": f"ALTER TABLE {table} ALTER COLUMN {column} SET NOT NULL;",
                    }
                )

            conn.close()

            # Count unique tables
            unique_tables = len(tables_analyzed)

            # Sort anomalies by priority (HIGH -> MEDIUM -> LOW)
            priority_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
            anomalies.sort(key=lambda x: priority_order.get(x.get("priority", "LOW"), 3))

            return {
                "status": "ok",
                "message": f"Analyzed {unique_tables} tables, found {len(anomalies)} anomalies",
                "tables_analyzed": unique_tables,
                "recommendations_count": len(anomalies),
                "recommendations": anomalies[:50],  # Limit to 50 recommendations
            }

        except Exception as e:
            logger.error(f"Schema anomaly detector failed: {e}", exc_info=True)
            return {
                "status": "error",
                "message": str(e),
                "tables_analyzed": 0,
                "recommendations_count": 0,
                "recommendations": [],
            }
