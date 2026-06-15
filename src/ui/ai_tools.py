# ----------------------------------------------------------------------
# SQL Schema Studio 0.9 - AI Tools (GPLv3)
# Copyright (C) 2026 Peter Leukanič
# License: GNU GPL v3+ <https://www.gnu.org/licenses/gpl-3.0.txt>
# This is free software with NO WARRANTY.
# Feel free to distribute and modify.
# ----------------------------------------------------------------------

"""AI-powered analysis tools for database optimization."""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

from src.utils.logging import get_logger

logger = get_logger(__name__)


class AIToolsPopover:
    """AI Tools popover menu with 9 analysis tools."""

    def __init__(self, window):
        self._window = window

    def create(self) -> Gtk.Popover:
        """Create the popover menu with all analysis tools."""
        popover = Gtk.Popover()
        popover.set_has_arrow(True)

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        vbox.set_margin_top(4)
        vbox.set_margin_bottom(4)
        vbox.set_margin_start(4)
        vbox.set_margin_end(4)

        items = [
            ("Index Advisor", self._run_index_advisor,
             "Recommend missing indexes based on FKs and naming patterns"),
            ("Missing FKs", self._run_missing_fk_detector,
             "Find columns ending with _id that lack foreign keys"),
            ("Duplicate Rows", self._run_duplicate_detector,
             "Detect duplicate data across all tables"),
            ("Unused Indexes", self._run_unused_indexes,
             "Find indexes with zero scans that can be removed"),
            ("Slow Queries", self._run_slow_queries_analysis,
             "Find slow queries that might benefit from indexes"),
            ("Table Growth", self._run_table_growth_analysis,
             "Analyze table sizes, dead rows, and vacuum status"),
            ("Column Statistics", self._run_column_statistics,
             "Show min, max, null %, and unique % for all columns"),
            ("Query Analyzer", self._run_query_analyzer,
             "Analyze table statistics using Polars engine"),
            ("Performance Insights", self._run_performance_insights,
             "Database performance overview with cache hit ratio"),
        ]

        for label, callback, tooltip in items:
            btn = Gtk.Button(label=label)
            btn.set_tooltip_text(tooltip)
            btn.set_halign(Gtk.Align.FILL)
            btn.set_has_frame(False)
            btn.add_css_class("flat")
            btn.connect("clicked", lambda b, cb=callback: cb())
            vbox.append(btn)

        popover.set_child(vbox)
        return popover

    # =====================================================================
    # Helpers
    # =====================================================================

    def _check_connected(self) -> bool:
        """Check if connected to database. Shows status message if not."""
        window = self._window
        if not window.db_connector or not window.db_connector.is_connected:
            window.statusbar.set_message("Not connected to database")
            return False
        return True

    # =====================================================================
    # 1. Index Advisor
    # =====================================================================

    def _run_index_advisor(self):
        """Recommend missing indexes based on foreign keys and naming patterns.
        
        Checks for:
        - Foreign key columns without indexes (HIGH priority)
        - Columns ending with _id (MEDIUM priority)
        - Date columns often used in range queries (MEDIUM priority)
        - Status/type/category columns used in WHERE clauses (LOW priority)
        """
        if not self._check_connected():
            return
        window = self._window
        try:
            from src.analytics.index_advisor import IndexAdvisor
            advisor = IndexAdvisor()
            recommendations = advisor.analyze_all_tables(window.db_connector)
            sql_lines = ["-- AI Index Advisor Recommendations\n"]
            for table, recs in recommendations.items():
                sql_lines.append(f"-- Table: {table}")
                for r in recs:
                    sql_lines.append(f"-- {r['reason']} [{r['priority']}]")
                    sql_lines.append(r["sql"])
                    sql_lines.append("")
            window.editor.set_text("\n".join(sql_lines))
            total = sum(len(r) for r in recommendations.values())
            cols = ["Table", "Recommendations"]
            rows = [[t, str(len(r))] for t, r in recommendations.items()]
            window.results.show_query_result(cols, rows, 0)
            window.statusbar.set_message(
                f"Found {total} index recommendations across {len(recommendations)} tables"
            )
        except Exception as e:
            logger.error(f"Index Advisor failed: {e}")
            window.statusbar.set_message(f"Index Advisor failed: {e}")

    # =====================================================================
    # 2. Missing FK Detector
    # =====================================================================

    def _run_missing_fk_detector(self):
        """Detect columns ending with _id that lack foreign key constraints.
        
        Searches for columns matching *_id pattern that have no FK constraint,
        and suggests the likely referenced table (e.g., user_id -> users.id).
        """
        if not self._check_connected():
            return
        window = self._window
        try:
            results = window.db_connector.execute_sync("""
                SELECT c.table_schema, c.table_name, c.column_name
                FROM information_schema.columns c
                WHERE c.column_name LIKE '%_id'
                  AND c.table_schema = 'public'
                  AND NOT EXISTS (
                    SELECT 1 FROM information_schema.key_column_usage kcu
                    JOIN information_schema.table_constraints tc
                      ON kcu.constraint_name = tc.constraint_name
                    WHERE tc.constraint_type = 'FOREIGN KEY'
                      AND kcu.table_schema = c.table_schema
                      AND kcu.table_name = c.table_name
                      AND kcu.column_name = c.column_name
                  )
                ORDER BY c.table_name, c.column_name
            """)
            if results:
                cols = ["Schema", "Table", "Column", "Suggested FK"]
                rows = []
                for r in results:
                    suggested = r["column_name"].replace("_id", "") + "s"
                    rows.append([r["table_schema"], r["table_name"], r["column_name"],
                                 f"{suggested}.id"])
                window.results.show_query_result(cols, rows, 0)
                window.statusbar.set_message(f"Found {len(rows)} missing foreign keys")
            else:
                window.results.show_text("No missing foreign keys detected.")
        except Exception as e:
            logger.error(f"Missing FK detection failed: {e}")
            window.statusbar.set_message(f"Missing FK detection failed: {e}")

    # =====================================================================
    # 3. Duplicate Detector
    # =====================================================================

    def _run_duplicate_detector(self):
        """Find duplicate rows across all tables using Polars engine.
        
        Checks each table for completely identical rows and reports
        the count and percentage of duplicates found.
        """
        if not self._check_connected():
            return
        window = self._window
        try:
            from src.analytics.engine import AnalyticsEngine
            engine = AnalyticsEngine(window.db_connector)
            tables = window.db_connector.get_tables("public")
            cols = ["Table", "Total Rows", "Duplicates", "% Duplicate"]
            rows = []
            for table in tables:
                name = table["table_name"]
                df = engine.query_to_df(f"SELECT * FROM public.\"{name}\"")
                if df.is_empty():
                    continue
                total = len(df)
                dup_count = df.is_duplicated().sum()
                if dup_count > 0:
                    rows.append([name, str(total), str(dup_count),
                                 f"{dup_count/total*100:.1f}%"])
            if rows:
                window.results.show_query_result(cols, rows, 0)
                window.statusbar.set_message(f"Found duplicates in {len(rows)} tables")
            else:
                window.results.show_text("No duplicate rows found.")
        except Exception as e:
            logger.error(f"Duplicate detection failed: {e}")
            window.statusbar.set_message(f"Duplicate detection failed: {e}")

    # =====================================================================
    # 4. Unused Indexes
    # =====================================================================

    def _run_unused_indexes(self):
        """Find indexes with zero scans that can potentially be removed.
        
        Queries pg_stat_user_indexes for indexes that have never been used
        by the query planner, ordered by size (largest first).
        """
        if not self._check_connected():
            return
        window = self._window
        try:
            results = window.db_connector.execute_sync("""
                SELECT schemaname, relname AS tablename, indexrelname AS indexname,
                       idx_scan, idx_tup_read, idx_tup_fetch
                FROM pg_stat_user_indexes
                WHERE idx_scan = 0
                ORDER BY pg_relation_size(indexrelid) DESC
            """)
            if results:
                cols = ["Schema", "Table", "Index", "Scans", "Tuples Read"]
                rows = [[r["schemaname"], r["tablename"], r["indexname"],
                         str(r["idx_scan"]), str(r["idx_tup_read"])]
                        for r in results]
                window.results.show_query_result(cols, rows, 0)
                window.statusbar.set_message(f"Found {len(rows)} unused indexes")
            else:
                window.results.show_text("All indexes are being used.")
        except Exception as e:
            logger.error(f"Unused indexes detection failed: {e}")
            window.statusbar.set_message(f"Unused indexes detection failed: {e}")

    # =====================================================================
    # 5. Slow Queries Analysis
    # =====================================================================

    def _run_slow_queries_analysis(self):
        """Find slow queries using pg_stat_statements or pg_stat_activity.
    
        First tries pg_stat_statements (more detailed).
        Falls back to pg_stat_activity for currently running queries.
        """
        if not self._check_connected():
            return
        window = self._window
        try:
            # Try pg_stat_statements first
            try:
                window.db_connector.execute_sync(
                    "CREATE EXTENSION IF NOT EXISTS pg_stat_statements"
                )
                use_statements = True
            except Exception:
                use_statements = False

            if use_statements:
                results = window.db_connector.execute_sync("""
                SELECT query, calls,
                       round(total_exec_time::numeric, 2) AS total_ms,
                       round(mean_exec_time::numeric, 2) AS avg_ms,
                       rows, shared_blks_hit, shared_blks_read
                FROM pg_stat_statements
                WHERE mean_exec_time > 10
                ORDER BY total_exec_time DESC LIMIT 20
                """)
            else:
                # Fallback: currently running queries
                results = window.db_connector.execute_sync("""
                SELECT query,
                       1 AS calls,
                       round(extract(epoch from now() - query_start) * 1000, 2) AS total_ms,
                       round(extract(epoch from now() - query_start) * 1000, 2) AS avg_ms,
                       0 AS rows, 0 AS shared_blks_hit, 0 AS shared_blks_read
                FROM pg_stat_activity
                WHERE state = 'active' AND query NOT LIKE '%pg_stat%'
                ORDER BY query_start LIMIT 20
                """)

            if results:
                cols = ["Query", "Calls", "Total ms", "Avg ms", "Rows", "Cache Hit"]
                rows = []
                for r in results:
                    query = r["query"]
                    if len(query) > 80:
                        query = query[:80] + "..."
                    rows.append([query, str(r["calls"]), str(r["total_ms"]),
                                 str(r["avg_ms"]), str(r["rows"]), "N/A"])
                window.results.show_query_result(cols, rows, 0)
                window.statusbar.set_message(f"Found {len(rows)} queries")
            else:
                window.results.show_text("No slow queries found.")
        except Exception as e:
            logger.error(f"Slow queries analysis failed: {e}")
            window.results.show_text(
                "Could not analyze queries.\n\n"
                "For full query statistics, install pg_stat_statements:\n"
                "  sudo dnf install postgresql-contrib\n"
                "  CREATE EXTENSION pg_stat_statements;"
            )

    # =====================================================================
    # 6. Table Growth Analysis
    # =====================================================================

    def _run_table_growth_analysis(self):
        """Analyze table sizes, dead rows, and vacuum status.
        
        Shows total size, data size, index size, row counts,
        dead row ratio, and last vacuum/analyze timestamps.
        """
        if not self._check_connected():
            return
        window = self._window
        try:
            from src.analytics.engine import AnalyticsEngine
            engine = AnalyticsEngine(window.db_connector)

            results = engine.query_to_df("""
                SELECT 
                    schemaname || '.' || tablename AS table_name,
                    pg_total_relation_size(schemaname||'.'||tablename) AS total_bytes,
                    pg_relation_size(schemaname||'.'||tablename) AS data_bytes,
                    pg_indexes_size(schemaname||'.'||tablename) AS index_bytes,
                    n_live_tup AS row_count,
                    n_dead_tup AS dead_rows,
                    CASE WHEN n_live_tup > 0 
                        THEN round(n_dead_tup::numeric / n_live_tup * 100, 1)
                        ELSE 0 END AS dead_ratio,
                    last_vacuum,
                    last_autovacuum,
                    last_analyze
                FROM pg_stat_user_tables
                ORDER BY total_bytes DESC
                LIMIT 20
            """)

            if not results.is_empty():
                cols = ["Table", "Total", "Data", "Indexes", "Rows",
                        "Dead %", "Last Vacuum"]
                rows = []
                for r in results.iter_rows():
                    last_vac = r[8] or r[7] or r[9]
                    rows.append([
                        r[0],
                        f"{r[1]/1024/1024:.1f} MB" if r[1] else "0",
                        f"{r[2]/1024/1024:.1f} MB" if r[2] else "0",
                        f"{r[3]/1024/1024:.1f} MB" if r[3] else "0",
                        str(r[4] or 0),
                        f"{r[6]}%" if r[6] else "0%",
                        str(last_vac) if last_vac else "Never",
                    ])
                window.results.show_query_result(cols, rows, 0)
                window.statusbar.set_message(
                    f"Analyzed {len(rows)} tables"
                )
        except Exception as e:
            logger.error(f"Table growth analysis failed: {e}")
            window.statusbar.set_message(f"Table growth analysis failed: {e}")

    # =====================================================================
    # 7. Column Statistics
    # =====================================================================

    def _run_column_statistics(self):
        """Show detailed column statistics using Polars engine.
        
        For each column displays: data type, row count, null percentage,
        unique value percentage, and min/max values.
        Limited to first 10 tables to avoid memory issues.
        """
        if not self._check_connected():
            return
        window = self._window
        try:
            from src.analytics.engine import AnalyticsEngine
            engine = AnalyticsEngine(window.db_connector)
            tables = window.db_connector.get_tables("public")

            cols = ["Table", "Column", "Type", "Rows", "Null %",
                    "Unique %", "Min", "Max"]
            rows = []

            for table in tables[:10]:
                name = table["table_name"]
                df = engine.query_to_df(
                    f"SELECT * FROM public.\"{name}\" LIMIT 1000"
                )
                if df.is_empty():
                    continue

                for col in df.columns:
                    null_pct = (df[col].null_count() / len(df) * 100
                                if len(df) > 0 else 0)
                    unique_pct = (df[col].n_unique() / len(df) * 100
                                  if len(df) > 0 else 0)

                    col_min = df[col].min()
                    col_max = df[col].max()

                    rows.append([
                        name, col, str(df[col].dtype), str(len(df)),
                        f"{null_pct:.1f}%",
                        f"{unique_pct:.1f}%",
                        str(col_min)[:20] if col_min is not None else "-",
                        str(col_max)[:20] if col_max is not None else "-",
                    ])

            if rows:
                window.results.show_query_result(cols, rows, 0)
                window.statusbar.set_message(
                    f"Analyzed {min(len(tables), 10)} tables, {len(rows)} columns"
                )
        except Exception as e:
            logger.error(f"Column statistics failed: {e}")
            window.statusbar.set_message(f"Column statistics failed: {e}")

    # =====================================================================
    # 8. Query Analyzer
    # =====================================================================

    def _run_query_analyzer(self):
        """Analyze table statistics using Polars engine.
        
        Shows row counts, column counts, estimated sizes,
        and highlights columns with >50% NULL values.
        """
        if not self._check_connected():
            return
        window = self._window
        try:
            from src.analytics.engine import AnalyticsEngine
            engine = AnalyticsEngine(window.db_connector)
            tables = window.db_connector.get_tables("public")
            cols = ["Table", "Rows", "Columns", "Size (MB)", "Null Issues"]
            rows = []
            for table in tables:
                name = table["table_name"]
                stats = engine.table_stats_safe("public", name)
                null_issues = sum(
                    1 for pct in stats.get("null_percentages", {}).values()
                    if pct > 50
                )
                rows.append([
                    name,
                    f"{stats['row_count']:,}",
                    str(stats['column_count']),
                    str(stats['estimated_size_mb']),
                    f"{null_issues} cols >50% NULL" if null_issues > 0 else "OK",
                ])
            window.results.show_query_result(cols, rows, 0)
            total_rows = sum(int(r[1].replace(",", "")) for r in rows)
            window.statusbar.set_message(
                f"Analyzed {len(tables)} tables | Total rows: {total_rows:,}"
            )
        except Exception as e:
            logger.error(f"Query Analyzer failed: {e}")
            window.statusbar.set_message(f"Analysis failed: {e}")

    # =====================================================================
    # 9. Performance Insights
    # =====================================================================

    def _run_performance_insights(self):
        """Show database performance overview.
        
        Displays active connections, commit/rollback counts,
        cache hit ratio, and top 10 largest tables.
        """
        if not self._check_connected():
            return
        window = self._window
        try:
            from src.analytics.engine import AnalyticsEngine
            engine = AnalyticsEngine(window.db_connector)

            # Get database-level statistics
            db_stats = engine.query_to_df(
                "SELECT datname, numbackends, xact_commit, xact_rollback, "
                "blks_read, blks_hit "
                "FROM pg_stat_database WHERE datname = current_database()"
            )

            # Get table sizes
            table_sizes = engine.query_to_df(
                "SELECT tablename, "
                "pg_total_relation_size(schemaname||'.'||tablename) as size_bytes "
                "FROM pg_tables WHERE schemaname = 'public' "
                "ORDER BY size_bytes DESC LIMIT 10"
            )

            summary_cols = ["Metric", "Value"]
            summary_rows = []

            if not db_stats.is_empty():
                row = db_stats.row(0)
                summary_rows.append(["Active Connections", str(row[1])])
                summary_rows.append(["Commits", f"{row[2]:,}"])
                summary_rows.append(["Rollbacks", f"{row[3]:,}"])
                if (row[4] + row[5]) > 0:
                    cache_pct = row[5] / (row[4] + row[5]) * 100
                    summary_rows.append(["Cache Hit Ratio", f"{cache_pct:.1f}%"])

            if not table_sizes.is_empty():
                summary_rows.append(["", ""])
                summary_rows.append(["--- Top Tables ---", ""])
                for r in table_sizes.iter_rows():
                    summary_rows.append(
                        [r[0], f"{r[1]/1024/1024:.1f} MB"]
                    )

            window.results.show_query_result(summary_cols, summary_rows, 0)
            window.statusbar.set_message("Performance insights generated")
        except Exception as e:
            logger.error(f"Performance Insights failed: {e}")
            window.statusbar.set_message(f"Insights failed: {e}")
