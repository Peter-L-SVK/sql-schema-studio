# ----------------------------------------------------------------------
# SQL Schema Studio 0.8 - Auto-Vacuum Advisor Hook (GPLv3)
# Copyright (C) 2026 Peter Leukanič
# License: GNU GPL v3+ <https://www.gnu.org/licenses/gpl-3.0.txt>
# This is free software with NO WARRANTY.
# Feel free to distribute and modify.
# ----------------------------------------------------------------------

"""Hook that analyzes table bloat, tracks history, and predicts vacuum timing."""

import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from src.hooks.base_plugin import BaseHook, HookContext, HookTrigger
from src.utils.logging import get_logger

logger = get_logger(__name__)

# History storage
HISTORY_DIR = Path.home() / ".config" / "sql-schema-studio" / "vacuum_history"
HISTORY_DIR.mkdir(parents=True, exist_ok=True)
MAX_HISTORY_DAYS = 90  # Keep 90 days of history


class Plugin(BaseHook):
    """Auto-vacuum advisor with historical tracking and ML predictions."""

    def get_metadata(self):
        return {
            "name": "Auto-Vacuum Advisor",
            "version": "1.1.0",
            "author": "SQL Schema Studio",
            "description": "Analyzes table bloat, tracks history, and predicts optimal vacuum timing",
            "triggers": [HookTrigger.SCHEDULED_INTERVAL.value],
        }

    async def execute(self, context: HookContext) -> dict:
        """Abstract method — required by BaseHook. Delegates to execute_sync."""
        conn_string = context.data.get("conn_string", "")
        return self.execute_sync(conn_string)

    def _load_history(self, table_name: str) -> List[Dict]:
        """Load historical data for a specific table."""
        history_file = HISTORY_DIR / f"{table_name.replace('.', '_')}.json"
        if not history_file.exists():
            return []
        
        try:
            with open(history_file, "r") as f:
                data = json.load(f)
            # Filter by age
            cutoff = datetime.now() - timedelta(days=MAX_HISTORY_DAYS)
            return [h for h in data if datetime.fromisoformat(h["timestamp"]) > cutoff]
        except Exception as e:
            logger.warning(f"Failed to load history for {table_name}: {e}")
            return []

    def _save_history(self, table_name: str, snapshot: Dict):
        """Save current snapshot to history."""
        history_file = HISTORY_DIR / f"{table_name.replace('.', '_')}.json"
        
        try:
            # Load existing history
            history = self._load_history(table_name)
            
            # Add new snapshot
            history.append({
                "timestamp": datetime.now().isoformat(),
                "dead_tuples": snapshot["n_dead_tup"],
                "live_tuples": snapshot["n_live_tup"],
                "dead_ratio": snapshot["dead_ratio"],
                "total_activity": snapshot.get("total_activity", 0),
            })
            
            # Keep only last MAX_HISTORY_DAYS
            cutoff = datetime.now() - timedelta(days=MAX_HISTORY_DAYS)
            history = [h for h in history if datetime.fromisoformat(h["timestamp"]) > cutoff]
            
            # Save
            with open(history_file, "w") as f:
                json.dump(history, f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save history for {table_name}: {e}")

    def _predict_bloat_growth(self, history: List[Dict]) -> Tuple[Optional[float], Optional[int]]:
        """Predict when dead tuple ratio will reach critical levels.
        
        Returns:
            (expected_growth_rate_per_day, days_until_critical)
        """
        if len(history) < 3:
            return None, None
        
        try:
            # Try to import scikit-learn for better prediction
            from sklearn.linear_model import LinearRegression
            import numpy as np
            
            # Prepare data
            days = []
            ratios = []
            start_date = datetime.fromisoformat(history[0]["timestamp"])
            
            for h in history:
                days.append((datetime.fromisoformat(h["timestamp"]) - start_date).days)
                ratios.append(h["dead_ratio"])
            
            if len(days) < 2:
                return None, None
            
            # Linear regression
            X = np.array(days).reshape(-1, 1)
            y = np.array(ratios)
            model = LinearRegression()
            model.fit(X, y)
            
            growth_rate = model.coef_[0]  # % per day
            current_ratio = ratios[-1]
            
            # Days until 50% (critical)
            if growth_rate > 0:
                days_until_critical = max(0, int((50 - current_ratio) / growth_rate))
            else:
                days_until_critical = None
            
            return growth_rate, days_until_critical
            
        except ImportError:
            # Fallback to simple linear approximation without sklearn
            logger.debug("scikit-learn not available, using simple prediction")
            
            if len(history) < 5:
                return None, None
            
            # Simple average growth
            growth_rates = []
            for i in range(1, len(history)):
                prev_ratio = history[i-1]["dead_ratio"]
                curr_ratio = history[i]["dead_ratio"]
                
                # Parse timestamps
                prev_date = datetime.fromisoformat(history[i-1]["timestamp"])
                curr_date = datetime.fromisoformat(history[i]["timestamp"])
                days_diff = max(1, (curr_date - prev_date).days)
                
                growth_rates.append((curr_ratio - prev_ratio) / days_diff)
            
            if not growth_rates:
                return None, None
            
            avg_growth = sum(growth_rates) / len(growth_rates)
            current_ratio = history[-1]["dead_ratio"]
            
            if avg_growth > 0:
                days_until_critical = max(0, int((50 - current_ratio) / avg_growth))
            else:
                days_until_critical = None
            
            return avg_growth, days_until_critical

    def _estimate_space_waste(self, conn_string: str, schema: str, table: str, dead_ratio: float) -> str:
        """Estimate how much space would be reclaimed by VACUUM."""
        try:
            import psycopg
            conn = psycopg.connect(conn_string)
            cur = conn.cursor()
            
            cur.execute("""
                SELECT 
                    pg_size_pretty(pg_total_relation_size(%s)) as total_size,
                    pg_size_pretty(pg_table_size(%s)) as table_size,
                    pg_size_pretty(pg_indexes_size(%s)) as indexes_size
            """, (f"{schema}.{table}", f"{schema}.{table}", f"{schema}.{table}"))
            
            row = cur.fetchone()
            conn.close()
            
            if row and dead_ratio > 0:
                total_size = row[0]
                return f"~{int(dead_ratio)}% of {total_size} potentially reclaimable"
            return "Unknown"
        except Exception:
            return "Unknown"

    def _check_autovacuum_config(self, conn_string: str) -> List[Dict]:
        """Check autovacuum configuration."""
        try:
            import psycopg
            conn = psycopg.connect(conn_string)
            cur = conn.cursor()
            
            cur.execute("""
                SELECT name, setting, unit, short_desc
                FROM pg_settings
                WHERE name LIKE 'autovacuum%'
                ORDER BY name
            """)
            
            config = []
            for row in cur.fetchall():
                config.append({
                    "name": row[0],
                    "setting": row[1],
                    "unit": row[2] or "",
                    "description": row[3][:100] if row[3] else "",
                })
            
            conn.close()
            return config
        except Exception as e:
            logger.warning(f"Failed to check autovacuum config: {e}")
            return []

    def execute_sync(self, conn_string: str) -> dict:
        """Synchronous version — analyzes table bloat from pg_stat_user_tables."""
        import psycopg
        from datetime import datetime

        try:
            conn = psycopg.connect(conn_string)
            cur = conn.cursor()

            # Odstránili sme podmienku n_live_tup + n_dead_tup > 1000
            # Teraz analyzuje VŠETKY tabuľky
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
                FROM pg_stat_all_tables
                WHERE schemaname NOT LIKE 'pg_%' 
                  AND schemaname != 'information_schema'
                ORDER BY n_dead_tup DESC
            """)
            
            rows = cur.fetchall()
            
            if not rows:
                conn.close()
                return {
                    "status": "ok",
                    "message": "No user tables found",
                    "tables_analyzed": 0,
                    "recommendations_count": 0,
                    "recommendations": [],
                }
            
            if not cur.description:
                conn.close()
                return {"status": "error", "message": "Query returned no column data"}
            
            columns = [desc[0] for desc in cur.description]
            stats = [dict(zip(columns, row)) for row in rows]
            conn.close()

            recommendations = []
            
            for row in stats:
                table_name = f"{row['schemaname']}.{row['tablename']}"
                
                # Ak je tabuľka prázdna, preskočíme (ale započítame do analyzed)
                if row['n_live_tup'] == 0 and row['n_dead_tup'] == 0:
                    continue
                    
                dead_ratio = float(row["dead_ratio"])

                # Určenie priority a akcie
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
                    # Žiadna akcia potrebná, ale stále analyzujeme tabuľku
                    continue

                # Pridať info o poslednom vacuum
                last_vacuum = row["last_vacuum"]
                if last_vacuum:
                    now_naive = datetime.now().replace(tzinfo=None)
                    last_vacuum_naive = last_vacuum.replace(tzinfo=None)
                    days_since = (now_naive - last_vacuum_naive).days
                    reason += f", last vacuumed {days_since} days ago"
                else:
                    reason += ", never vacuumed"
                    
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
                "message": f"Analyzed {len(stats)} tables, found {len(recommendations)} issues",
                "tables_analyzed": len(stats),
                "recommendations_count": len(recommendations),
                "recommendations": recommendations,
            }

        except Exception as e:
            logger.error(f"Auto-vacuum advisor failed: {e}")
            return {
                "status": "error", 
                "message": str(e),
                "tables_analyzed": 0,
                "recommendations_count": 0,
                "recommendations": []
            }
