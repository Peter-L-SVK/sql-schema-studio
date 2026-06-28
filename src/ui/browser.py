# ----------------------------------------------------------------------
# SQL Schema Studio 0.9 - Database Browser (GPLv3)
# Copyright (C) 2026 Peter Leukanič
# License: GNU GPL v3+ <https://www.gnu.org/licenses/gpl-3.0.txt>
# This is free software with NO WARRANTY.
# Feel free to distribute and modify.
# ----------------------------------------------------------------------

from __future__ import annotations

from src.utils.logging import get_logger

logger = get_logger(__name__)

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, Gdk
from src.config import EXCLUDED_SCHEMAS, BROWSER_PANEL_WIDTH
from src.utils.gtk_helpers import run_async


class DatabaseBrowser(Gtk.Box):
    """Left panel showing database objects in a tree"""

    def __init__(self, window):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self._window = window
        self._refreshing = False
        self.set_size_request(BROWSER_PANEL_WIDTH, -1)
        self.add_css_class("sidebar")

        # Header with refresh
        header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        header_box.add_css_class("panel-header")

        label = Gtk.Label(label="Browser")
        label.set_halign(Gtk.Align.START)
        label.set_hexpand(True)
        header_box.append(label)

        btn_refresh = Gtk.Button.new_from_icon_name("view-refresh-symbolic")
        btn_refresh.set_tooltip_text("Refresh")
        btn_refresh.connect("clicked", lambda b: self.refresh())
        header_box.append(btn_refresh)

        self.append(header_box)

        # Tree view
        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)

        # Store: icon, name, type, schema, visible (for filtering)
        self._store = Gtk.TreeStore(str, str, str, str, bool)
        self._all_items = []  # Cache for filtering: (iter, name, type, schema)

        self._tree = Gtk.TreeView(model=self._store)
        self._tree.add_css_class("db-browser")
        self._tree.set_headers_visible(False)
        self._tree.set_enable_search(True)
        self._tree.set_search_column(1)

        # Drag source — allow dragging table names to schema designer
        drag_source = Gtk.DragSource()
        drag_source.set_actions(Gdk.DragAction.COPY)
        drag_source.connect("prepare", self._on_drag_prepare)
        self._tree.add_controller(drag_source)

        # Icon column
        icon_renderer = Gtk.CellRendererText()
        icon_col = Gtk.TreeViewColumn("", icon_renderer, text=0)
        icon_col.set_min_width(30)
        self._tree.append_column(icon_col)

        # Name column
        name_renderer = Gtk.CellRendererText()
        name_col = Gtk.TreeViewColumn("Name", name_renderer, text=1)
        name_col.set_expand(True)
        self._tree.append_column(name_col)

        # Left-click handling
        click = Gtk.GestureClick()
        click.connect("pressed", self._on_clicked)
        self._tree.add_controller(click)

        # Right-click context menu
        right_click = Gtk.GestureClick()
        right_click.set_button(3)  # right mouse button
        right_click.connect("pressed", self._on_right_click)
        self._tree.add_controller(right_click)

        # Selection
        selection = self._tree.get_selection()
        selection.connect("changed", self._on_selection_changed)

        scroll.set_child(self._tree)
        self.append(scroll)

        # Filter entry at bottom
        filter_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        filter_box.add_css_class("panel-header")

        filter_icon = Gtk.Image.new_from_icon_name("edit-find-symbolic")
        filter_box.append(filter_icon)

        self._filter_entry = Gtk.Entry()
        self._filter_entry.set_placeholder_text("Filter objects...")
        self._filter_entry.set_hexpand(True)
        self._filter_entry.connect("changed", self._on_filter_changed)
        filter_box.append(self._filter_entry)

        # Clear filter button
        btn_clear = Gtk.Button.new_from_icon_name("edit-clear-symbolic")
        btn_clear.set_tooltip_text("Clear filter")
        btn_clear.connect("clicked", self._on_clear_filter)
        filter_box.append(btn_clear)

        self.append(filter_box)

    # ------------------------------------------------------------------
    # Right-click context menu — forecasting
    # ------------------------------------------------------------------

    def _on_right_click(self, gesture, n_press, x, y):
        """Show context menu on right-click."""
        result = self._tree.get_path_at_pos(int(x), int(y))
        if not result:
            return

        path, col, cx, cy = result
        tree_iter = self._store.get_iter(path)
        item_type = self._store.get_value(tree_iter, 2)

        if item_type not in ("BASE TABLE", "VIEW"):
            return

        schema = self._store.get_value(tree_iter, 3)
        table = self._store.get_value(tree_iter, 1)

        popover = Gtk.Popover()
        popover.set_parent(self._tree)
        popover.set_has_arrow(True)
        popover.set_pointing_to(
            Gdk.Rectangle()
        )  # position handled by set_offset or set_pointing_to

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)

        header = Gtk.Label()
        header.set_markup(f"<b>Analyze: {schema}.{table}</b>")
        header.set_halign(Gtk.Align.START)
        header.set_margin_start(8)
        header.set_margin_end(8)
        header.set_margin_top(6)
        header.set_margin_bottom(6)
        vbox.append(header)

        sep = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        vbox.append(sep)

        for func_id, label, icon in [
            ("percentile_bands", "📊 Percentile Bands", "dialog-information-symbolic"),
            ("trend_forecast", "📈 Trend Forecast", "go-up-symbolic"),
            ("anomaly_detect", "🔍 Anomaly Detection", "edit-find-symbolic"),
            ("moving_average", "📉 Moving Average", "go-previous-symbolic"),
            ("exponential_forecast", "🔄 Exp. Smoothing", "view-refresh-symbolic"),
        ]:
            btn = Gtk.Button(label=label, halign=Gtk.Align.FILL)
            btn.set_has_frame(False)
            btn.set_margin_start(4)
            btn.set_margin_end(4)
            btn.connect(
                "clicked",
                lambda b, fid=func_id: self._run_forecast(schema, table, fid, popover),
            )
            vbox.append(btn)

        popover.set_child(vbox)
        popover.popup()

    def _run_forecast(self, schema, table, func_id, popover):
        """Run a forecasting function on the selected table and show results."""
        popover.popdown()

        db = self._window.db_connector
        if not db.is_connected:
            self._window.statusbar.set_connection("⚠ Not connected to database")
            return

        self._window.statusbar.set_connection(
            f"⏳ Running {func_id.replace('_', ' ')} on {schema}.{table}..."
        )

        conn_string = db._get_conn_string()

        def do_analysis():
            try:
                import psycopg2

                conn = psycopg2.connect(conn_string)
                cur = conn.cursor()

                # Find first numeric column
                cur.execute(
                    """
                    SELECT column_name, data_type
                    FROM information_schema.columns
                    WHERE table_schema = %s AND table_name = %s
                      AND data_type IN ('integer', 'bigint', 'smallint',
                                        'numeric', 'real', 'double precision', 'money')
                    ORDER BY ordinal_position
                    LIMIT 1
                    """,
                    (schema, table),
                )
                row = cur.fetchone()
                if not row:
                    conn.close()
                    return {"error": f"No numeric columns found in {schema}.{table}"}

                column, dtype = row
                qualified = f'{schema}."{table}"'

                cur.execute(f'SELECT "{column}" FROM {qualified} WHERE "{column}" IS NOT NULL')
                data = [r[0] for r in cur.fetchall()]
                conn.close()

                if not data:
                    return {"error": f"No non-NULL values in {qualified}.{column}"}

                import polars as pl

                df = pl.DataFrame({column: data}, schema={column: pl.Float64})

                return {
                    "schema": schema,
                    "table": table,
                    "column": column,
                    "dtype": dtype,
                    "row_count": len(data),
                    "func_id": func_id,
                    "df": df,
                    "data": data,
                }
            except Exception as e:
                return {"error": str(e)}

        def on_loaded(result):
            if "error" in result:
                self._window.results.show_text(f"Forecast Error\n{'─' * 50}\n{result['error']}")
                self._window.statusbar.set_connection("❌ Forecast failed")
                return

            import polars as pl

            column = result["column"]
            df = result["df"]
            func_id = result["func_id"]
            qualified = f"{result['schema']}.{result['table']}"

            try:
                from src.hooks.python_hooks.forecasting import (
                    anomaly_detect,
                    exponential_forecast,
                    moving_average,
                    percentile_bands,
                    trend_forecast,
                )

                if func_id == "percentile_bands":
                    bands = percentile_bands(df, column)
                    text = f"Percentile Bands: {qualified}.{column}\n" f"{'─' * 50}\n"
                    for k, v in bands.items():
                        text += f"  {k:<6}: {v:>14.4f}\n"

                elif func_id == "trend_forecast":
                    # Add row index as x-axis when only one column exists
                    idx_col = "_row_idx"
                    df_with_idx = df.with_columns(
                        pl.Series(idx_col, range(1, df.height + 1), dtype=pl.Float64)
                    )
                    t = trend_forecast(df_with_idx, idx_col, column, periods=5)
                    text = (
                        f"Trend Forecast: {qualified}.{column}\n"
                        f"{'─' * 50}\n"
                        f"  Slope:      {t['slope']:>14.4f}\n"
                        f"  Intercept:  {t['intercept']:>14.4f}\n"
                        f"  R²:         {t['r_squared']:>14.4f}\n\n"
                        f"  Next 5 predictions:\n"
                    )
                    for i, p in enumerate(t["predictions"]):
                        text += f"    Period {i + 1}: {p:>12.4f}\n"

                elif func_id == "anomaly_detect":
                    adf = anomaly_detect(df, column)
                    anom = adf.filter(pl.col(f"{column}_anomaly")).height
                    total = result["row_count"]
                    text = (
                        f"Anomaly Detection: {qualified}.{column}\n"
                        f"{'─' * 50}\n"
                        f"  Method:      IQR (1.5×)\n"
                        f"  Total rows:  {total}\n"
                        f"  Anomalies:   {anom}\n"
                        f"  Rate:        {anom / total * 100:.2f}%\n"
                    )

                elif func_id == "moving_average":
                    madf = moving_average(df, column, window=7)
                    text = (
                        f"Moving Average (7-period): {qualified}.{column}\n"
                        f"{'─' * 70}\n"
                        f"  {'Original':>14}  {'MA(7)':>14}\n"
                        f"  {'─' * 14}  {'─' * 14}\n"
                    )
                    for r in madf.tail(10).rows():
                        orig = r[0] if r[0] is not None else 0.0
                        ma = r[1] if r[1] is not None else float("nan")
                        text += f"  {orig:>14.4f}  {ma:>14.4f}\n"

                elif func_id == "exponential_forecast":
                    efdf = exponential_forecast(df, column, span=12)
                    text = (
                        f"Exponential Smoothing (span=12): {qualified}.{column}\n"
                        f"{'─' * 70}\n"
                        f"  {'Original':>14}  {'ETS(12)':>14}\n"
                        f"  {'─' * 14}  {'─' * 14}\n"
                    )
                    for r in efdf.tail(10).rows():
                        orig = r[0] if r[0] is not None else 0.0
                        ets = r[1] if r[1] is not None else float("nan")
                        text += f"  {orig:>14.4f}  {ets:>14.4f}\n"

                self._window.results.show_text(text)
                self._window.statusbar.set_connection(
                    f"✅ {func_id.replace('_', ' ')}: {qualified}.{column}"
                )

            except Exception as e:
                self._window.results.show_text(f"Forecast Error\n{'─' * 50}\n{str(e)}")
                self._window.statusbar.set_connection("❌ Forecast failed")

        run_async(do_analysis, on_loaded)

    # ------------------------------------------------------------------
    # Refresh / filter / tree management
    # ------------------------------------------------------------------

    def refresh(self):
        """Reload all objects from database"""
        if self._refreshing:
            return
        self._refreshing = True

        self._store.clear()
        self._all_items.clear()

        db = self._window.db_connector

        if not db.is_connected:
            self._store.append(None, ["📁", "No Connection", "", "", True])
            self._refreshing = False
            return

        root = self._store.append(None, ["🖥", db.active_profile_name, "server", "", True])
        self._all_items.append((root, db.active_profile_name, "server", ""))

        active_name = db.active_profile_name

        def load_all():
            if self._window.db_connector.active_profile_name != active_name:
                return None

            try:
                results = db.execute_sync(
                    "SELECT schema_name FROM information_schema.schemata "
                    "WHERE schema_name != ALL(%s) "
                    "ORDER BY CASE WHEN schema_name = 'public' THEN 0 "
                    "ELSE 1 END, schema_name",
                    (list(EXCLUDED_SCHEMAS),),
                )
                schemas = [r["schema_name"] for r in results]

                all_data = []
                for s in schemas:
                    tables = db.execute_sync(
                        "SELECT table_name, table_type "
                        "FROM information_schema.tables "
                        "WHERE table_schema = %s "
                        "ORDER BY table_name",
                        (s,),
                    )
                    all_data.append((s, tables))

                return all_data
            except Exception as e:
                logger.error(f"Browser load error: {e}")
                return None

        def on_loaded(all_data):
            self._refreshing = False
            if all_data is None:
                return
            if self._store.iter_n_children(None) == 0:
                return

            root_iter = self._store.get_iter_first()
            if not root_iter:
                return

            for s, tables in all_data:
                schema_iter = self._store.append(root_iter, ["📂", s, "schema", s, True])
                self._all_items.append((schema_iter, s, "schema", s))

                for table in tables:
                    icon = "📋" if table["table_type"] == "BASE TABLE" else "👁"
                    table_iter = self._store.append(
                        schema_iter,
                        [icon, table["table_name"], table["table_type"], s, True],
                    )
                    self._all_items.append(
                        (table_iter, table["table_name"], table["table_type"], s)
                    )

                if s == "public":
                    path = self._store.get_path(schema_iter)
                    if path:
                        self._tree.expand_row(path, False)

            root_path = self._store.get_path(root_iter)
            if root_path:
                self._tree.expand_row(root_path, False)

        run_async(load_all, on_loaded)

    def clear(self):
        self._store.clear()
        self._all_items.clear()
        self._store.append(None, ["📁", "No Connection", "", "", True])

    def _on_filter_changed(self, entry):
        """Filter tree items by name"""
        search = entry.get_text().lower().strip()

        self._store.clear()

        if not search:
            self._rebuild_tree(self._all_items)
            return

        filtered = []
        matching_schemas = set()

        for item in self._all_items:
            tree_iter, name, itype, schema = item

            if itype == "server":
                filtered.append(item)
                continue

            if search in name.lower():
                if itype == "schema":
                    filtered.append(item)
                    matching_schemas.add(name)
                elif itype in ("BASE TABLE", "VIEW"):
                    if schema in matching_schemas:
                        filtered.append(item)

        self._rebuild_tree(filtered)

    def _rebuild_tree(self, items):
        """Rebuild tree from cached items list"""
        self._store.clear()

        for tree_iter, name, itype, schema in items:
            if itype == "server":
                self._store.append(None, [self._get_icon(itype), name, itype, schema, True])
            elif itype == "schema":
                root = self._store.get_iter_first()
                if root:
                    self._store.append(root, [self._get_icon(itype), name, itype, schema, True])
            elif itype in ("BASE TABLE", "VIEW"):
                root = self._store.get_iter_first()
                if root:
                    parent = None
                    child = self._store.iter_children(root)
                    while child:
                        if (
                            self._store.get_value(child, 1) == schema
                            and self._store.get_value(child, 2) == "schema"
                        ):
                            parent = child
                            break
                        child = self._store.iter_next(child)

                    if parent:
                        self._store.append(
                            parent,
                            [self._get_icon(itype), name, itype, schema, True],
                        )

        self._tree.expand_all()
        root = self._store.get_iter_first()
        if root:
            self._tree.collapse_row(self._store.get_path(root))

    def _get_icon(self, itype):
        icons = {
            "server": "🖥",
            "schema": "📂",
            "BASE TABLE": "📋",
            "VIEW": "👁",
        }
        return icons.get(itype, "📄")

    def _find_parent_iter(self, schema):
        return self._store.get_iter_first()

    def _find_schema_iter(self, schema_name):
        root = self._store.get_iter_first()
        if not root:
            return None

        child = self._store.iter_children(root)
        while child:
            if (
                self._store.get_value(child, 1) == schema_name
                and self._store.get_value(child, 2) == "schema"
            ):
                return child
            child = self._store.iter_next(child)

        return self._store.append(root, ["📂", schema_name, "schema", schema_name, True])

    def _on_clear_filter(self, button):
        self._filter_entry.set_text("")

    def _on_clicked(self, gesture, n_press, x, y):
        result = self._tree.get_path_at_pos(int(x), int(y))
        if not result:
            return

        path, col, cx, cy = result
        tree_iter = self._store.get_iter(path)

        item_type = self._store.get_value(tree_iter, 2)
        item_name = self._store.get_value(tree_iter, 1)
        schema = self._store.get_value(tree_iter, 3)

        if n_press == 2 and item_type in ("BASE TABLE", "VIEW"):
            query = f"SELECT * FROM {schema}.{item_name} LIMIT 100;"
            self._window.editor.set_text(query)
            self._window._on_run_clicked()
        elif item_type in ("BASE TABLE", "VIEW"):
            self._show_structure(schema, item_name)

    def _on_selection_changed(self, selection):
        model, tree_iter = selection.get_selected()
        if tree_iter:
            name = model.get_value(tree_iter, 1)
            itype = model.get_value(tree_iter, 2)
            self._window.statusbar.set_connection(f"Selected: {name} ({itype})")

    def _show_structure(self, schema, table):
        db = self._window.db_connector

        def get_cols():
            return db.execute_sync(
                """
                SELECT column_name, data_type, is_nullable,
                       character_maximum_length
                FROM information_schema.columns
                WHERE table_schema = %s AND table_name = %s
                ORDER BY ordinal_position
            """,
                (schema, table),
            )

        def display(columns):
            if not columns:
                return
            text = f"Table: {schema}.{table}\n{'─' * 50}\n"
            for col in columns:
                dtype = col["data_type"]
                if col["character_maximum_length"]:
                    dtype += f"({col['character_maximum_length']})"
                null = "NULL" if col["is_nullable"] == "YES" else "NOT NULL"
                text += f"  {col['column_name']:<25} {dtype:<18} {null}\n"

            self._window.results.show_text(text)

        run_async(get_cols, display)

    def _on_drag_prepare(self, source, x, y):
        model, tree_iter = self._tree.get_selection().get_selected()
        if not tree_iter:
            return None

        item_type = self._store.get_value(tree_iter, 2)
        if item_type not in ("BASE TABLE", "VIEW"):
            return None

        schema = self._store.get_value(tree_iter, 3)
        table_name = self._store.get_value(tree_iter, 1)

        return Gdk.ContentProvider.new_for_value(f"{schema}.{table_name}")
