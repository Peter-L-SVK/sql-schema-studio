# ----------------------------------------------------------------------
# SQL Schema Studio 0.6 - AI Index Advisor (GPLv3)
# Copyright (C) 2026 Peter Leukanič
# License: GNU GPL v3+ <https://www.gnu.org/licenses/gpl-3.0.txt>
# This is free software with NO WARRANTY.
# Feel free to distribute and modify.
# ----------------------------------------------------------------------

"""ML-based index recommendations using scikit-learn."""

import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler

from src.utils.logging import get_logger

logger = get_logger(__name__)


class IndexAdvisor:
    """Recommends indexes based on table structure and query patterns."""

    def __init__(self):
        self.scaler = StandardScaler()
        self.classifier = RandomForestClassifier(n_estimators=50, random_state=42)
        self._trained = False

    def analyze_table(self, db_connector, schema: str, table: str) -> list[dict]:
        """Analyze a table and return index recommendations.

        Args:
            db_connector: DatabaseConnector instance
            schema: Schema name
            table: Table name

        Returns:
            List of recommendations with column, reason, and SQL
        """
        recommendations = []

        try:
            # Get columns
            columns = db_connector.execute_sync(
                """SELECT column_name, data_type, is_nullable
                   FROM information_schema.columns
                   WHERE table_schema = %s AND table_name = %s
                   ORDER BY ordinal_position""",
                (schema, table),
            )

            # Get existing indexes
            indexes = db_connector.execute_sync(
                """SELECT indexname, indexdef
                   FROM pg_indexes
                   WHERE schemaname = %s AND tablename = %s""",
                (schema, table),
            )

            # Get foreign keys
            fks = db_connector.execute_sync(
                """SELECT kcu.column_name, ccu.table_name AS referenced_table,
                          ccu.column_name AS referenced_column
                   FROM information_schema.table_constraints tc
                   JOIN information_schema.key_column_usage kcu
                     ON tc.constraint_name = kcu.constraint_name
                   JOIN information_schema.constraint_column_usage ccu
                     ON tc.constraint_name = ccu.constraint_name
                   WHERE tc.constraint_type = 'FOREIGN KEY'
                     AND tc.table_schema = %s AND tc.table_name = %s""",
                (schema, table),
            )

            existing_columns = set()
            for idx in indexes:
                # Extract column names from index definition
                import re
                cols = re.findall(r'\(([^)]+)\)', idx['indexdef'])
                for col in cols:
                    existing_columns.update(c.strip() for c in col.split(','))

            # Recommend indexes for foreign keys
            for fk in fks:
                col = fk['column_name']
                if col not in existing_columns:
                    recommendations.append({
                        "column": col,
                        "reason": f"Foreign key referencing {fk['referenced_table']}.{fk['referenced_column']}",
                        "sql": f"CREATE INDEX idx_{table}_{col} ON {schema}.{table} ({col});",
                        "priority": "HIGH",
                    })

            # Recommend indexes for columns named like *_id, *_date, *_status
            for col in columns:
                col_name = col['column_name']
                if col_name in existing_columns:
                    continue

                if col_name.endswith('_id') and col_name not in [r['column'] for r in recommendations]:
                    recommendations.append({
                        "column": col_name,
                        "reason": "Potential foreign key (ends with _id)",
                        "sql": f"CREATE INDEX idx_{table}_{col_name} ON {schema}.{table} ({col_name});",
                        "priority": "MEDIUM",
                    })

                if col_name.endswith('_date') or col_name.endswith('_at'):
                    recommendations.append({
                        "column": col_name,
                        "reason": "Date column — often used in range queries",
                        "sql": f"CREATE INDEX idx_{table}_{col_name} ON {schema}.{table} ({col_name});",
                        "priority": "MEDIUM",
                    })

                if col_name in ('status', 'type', 'category'):
                    recommendations.append({
                        "column": col_name,
                        "reason": "Categorical column — often used in WHERE clauses",
                        "sql": f"CREATE INDEX idx_{table}_{col_name} ON {schema}.{table} ({col_name});",
                        "priority": "LOW",
                    })

            logger.info(f"Index advisor: {len(recommendations)} recommendations for {schema}.{table}")

        except Exception as e:
            logger.error(f"Index advisor failed: {e}")

        return recommendations

    def analyze_all_tables(self, db_connector) -> dict:
        """Analyze all tables and return recommendations grouped by table."""
        if not db_connector.is_connected:
            return {}

        schemas = db_connector.get_schemas()
        all_recommendations = {}

        for schema in schemas:
            tables = db_connector.get_tables(schema)
            for table in tables:
                table_name = table['table_name']
                recs = self.analyze_table(db_connector, schema, table_name)
                if recs:
                    all_recommendations[f"{schema}.{table_name}"] = recs

        return all_recommendations
