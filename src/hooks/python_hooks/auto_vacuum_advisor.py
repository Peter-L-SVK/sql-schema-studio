# ----------------------------------------------------------------------
# SQL Schema Studio 0.8 - Auto-Vacuum Advisor Hook (GPLv3)
# Copyright (C) 2026 Peter Leukanič
# License: GNU GPL v3+ <https://www.gnu.org/licenses/gpl-3.0.txt>
# This is free software with NO WARRANTY.
# Feel free to distribute and modify.
# ----------------------------------------------------------------------

"""Hook that analyzes table bloat and recommends vacuum timing."""

from src.hooks.base_plugin import BaseHook, HookContext, HookTrigger
from src.utils.logging import get_logger

logger = get_logger(__name__)


class Plugin(BaseHook):
    """Auto-vacuum advisor hook — analyzes table bloat from pg_stat_user_tables."""

    def get_metadata(self):
        return {
            "name": "Auto-Vacuum Advisor",
            "version": "1.0.0",
            "author": "SQL Schema Studio",
            "description": "Analyzes table bloat and recommends vacuum timing",
            "triggers": [HookTrigger.SCHEDULED_INTERVAL.value],
        }
    
    async def execute(self, context: HookContext) -> dict:
        """Abstract method — required by BaseHook. Delegates to execute_sync."""
        conn_string = context.data.get("conn_string", "")
        return self.execute_sync(conn_string)

    def execute_sync(self, conn_string: str) -> dict:
        """Synchronous version — analyzes table bloat from pg_stat_user_tables."""
        import psycopg
        from datetime import datetime

        try:
            conn = psycopg.connect(conn_string)
            cur = conn.cursor()

            cur.execute("""
    SELECT 
        schemaname,
        relname AS tablename,
        n_live_tup,
        n_dead_tup,
        CASE WHEN n_live_tup > 0 
            THEN round(100.0 * n_dead_tup / n_live_tup, 1)
            ELSE 0 END AS dead_ratio,
        last_vacuum,
        last_autovacuum,
        autovacuum_count,
        n_tup_ins + n_tup_upd + n_tup_del AS total_activity
    FROM pg_stat_user_tables
    ORDER BY n_dead_tup DESC
""")

            rows = cur.fetchall()
            columns = [desc[0] for desc in cur.description]
            stats = [dict(zip(columns, row)) for row in rows]
            conn.close()

            recommendations = []
            for row in stats:
                table_name = f"{row['schemaname']}.{row['tablename']}"
                dead_ratio = float(row["dead_ratio"])

                if dead_ratio > 50:
                    priority, action = "CRITICAL", "VACUUM FULL ANALYZE"
                    reason = f"Extreme bloat ({dead_ratio}% dead tuples)"
                elif dead_ratio > 20:
                    priority, action = "HIGH", "VACUUM ANALYZE"
                    reason = f"Significant bloat ({dead_ratio}% dead tuples)"
                elif dead_ratio > 10:
                    priority, action = "MEDIUM", "VACUUM ANALYZE"
                    reason = f"Moderate bloat ({dead_ratio}% dead tuples)"
                elif dead_ratio > 5:
                    priority, action = "LOW", "ANALYZE"
                    reason = f"Mild bloat ({dead_ratio}% dead tuples)"
                else:
                    continue

                last_vacuum = row["last_vacuum"]
                if last_vacuum:
                    days_since = (datetime.now() - last_vacuum).days
                    reason += f", last vacuumed {days_since} days ago"

                recommendations.append({
                    "table": table_name,
                    "dead_ratio": dead_ratio,
                    "dead_tuples": row["n_dead_tup"],
                    "live_tuples": row["n_live_tup"],
                    "action": action,
                    "priority": priority,
                    "reason": reason,
                    "sql": f"{action} {table_name};",
                    "last_vacuum": str(last_vacuum) if last_vacuum else "never",
                })

            return {
                "status": "ok",
                "tables_analyzed": len(stats),
                "recommendations_count": len(recommendations),
                "recommendations": recommendations,
            }

        except Exception as e:
            logger.error(f"Auto-vacuum advisor failed: {e}")
            return {"status": "error", "message": str(e)}
