# ----------------------------------------------------------------------
# SQL Schema Studio 0.6 - Query History (GPLv3)
# Copyright (C) 2026 Peter Leukanič
# License: GNU GPL v3+ <https://www.gnu.org/licenses/gpl-3.0.txt>
# This is free software with NO WARRANTY.
# Feel free to distribute and modify.
# ----------------------------------------------------------------------

"""Query history stored in local SQLite database."""

import sqlite3
from pathlib import Path
from src.utils.logging import get_logger

logger = get_logger(__name__)

DB_DIR = Path.home() / ".config" / "sql-schema-studio"
DB_PATH = DB_DIR / "query_history.db"


class QueryHistory:
    """Manages query history with SQLite backend."""

    def __init__(self):
        DB_DIR.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._create_table()

    def _categorize(self, query: str) -> str:
        """Categorize query type."""
        q = query.strip().upper()
        if q.startswith("SELECT"):
            return "SELECT"
        elif q.startswith("INSERT"):
            return "INSERT"
        elif q.startswith("UPDATE"):
            return "UPDATE"
        elif q.startswith("DELETE"):
            return "DELETE"
        elif any(q.startswith(c) for c in ("CREATE", "ALTER", "DROP", "TRUNCATE")):
            return "DDL"
        else:
            return "OTHER"

    def _create_table(self):
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                query TEXT NOT NULL,
                category TEXT DEFAULT 'OTHER',
                database TEXT DEFAULT '',
                executed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                execution_time REAL DEFAULT 0,
                row_count INTEGER DEFAULT 0,
                success INTEGER DEFAULT 1
            )
        """)
        # Add category column if upgrading from older schema
        try:
            self._conn.execute("ALTER TABLE history ADD COLUMN category TEXT DEFAULT 'OTHER'")
        except:
            pass
        self._conn.commit()

    def add(
        self,
        query: str,
        database: str = "",
        execution_time: float = 0,
        row_count: int = 0,
        success: bool = True,
    ):
        try:
            category = self._categorize(query)
            self._conn.execute(
                "INSERT INTO history (query, category, database, execution_time, row_count, success) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (query.strip(), category, database, execution_time, row_count, 1 if success else 0),
            )
            self._conn.commit()
        except Exception as e:
            logger.error(f"Failed to save query history: {e}")

    def get_recent(self, limit: int = 50) -> list[dict]:
        """Get recent queries."""
        cursor = self._conn.execute(
            "SELECT id, query, category, database, executed_at, execution_time, row_count, success "
            "FROM history ORDER BY id DESC LIMIT ?",
            (limit,),
        )
        rows = cursor.fetchall()
        return [
            {
                "id": r[0],
                "query": r[1],
                "category": r[2],
                "database": r[3],
                "executed_at": r[4],
                "execution_time": r[5],
                "row_count": r[6],
                "success": bool(r[7]),
            }
            for r in rows
        ]

    def search(self, term: str, limit: int = 50) -> list[dict]:
        """Search queries containing a term."""
        cursor = self._conn.execute(
            "SELECT id, query, category, database, executed_at, execution_time, row_count, success "
            "FROM history WHERE query LIKE ? ORDER BY id DESC LIMIT ?",
            (f"%{term}%", limit),
        )
        rows = cursor.fetchall()
        return [
            {
                "id": r[0],
                "query": r[1],
                "category": r[2],
                "database": r[3],
                "executed_at": r[4],
                "execution_time": r[5],
                "row_count": r[6],
                "success": bool(r[7]),
            }
            for r in rows
        ]

    def clear(self):
        """Clear all history."""
        self._conn.execute("DELETE FROM history")
        self._conn.commit()
        logger.info("Query history cleared")

    def close(self):
        """Close the database connection."""
        self._conn.close()
