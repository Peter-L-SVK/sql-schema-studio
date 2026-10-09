# ----------------------------------------------------------------------
# SQL Schema Studio 0.9.5 - Query History Dialog (GPLv3)
# Copyright (C) 2026 Peter Leukanič
# License: GNU GPL v3+ <https://www.gnu.org/licenses/gpl-3.0.txt>
# This is free software with NO WARRANTY.
# Feel free to distribute and modify.
# ----------------------------------------------------------------------

"""Query history dialog with search and category filter."""

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

from src.utils.gtk_helpers import set_margin
from src.utils.logging import get_logger

logger = get_logger(__name__)


class QueryHistoryDialog(Gtk.Window):
    """Dialog showing query history with search and category filter."""

    def __init__(self, parent, query_history, on_select=None):
        super().__init__(
            title="Query History",
            transient_for=parent,
            modal=False,
        )
        self._history = query_history
        self._on_select = on_select
        self.set_default_size(750, 500)

        # Parallel list — full query text for each row in _list_store.
        # Indexed by row position so _on_load doesn't need to search the DB.
        self._full_queries: list[str] = []
        self._history_ids: list[int] = []

        self._build_ui()
        self._load_history()

    # ==================================================================
    # UI
    # ==================================================================

    def _build_ui(self):
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        set_margin(main_box, 12)

        # --- Filter row ---
        filter_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)

        filter_box.append(Gtk.Label(label="Category:"))

        self._category_combo = Gtk.ComboBoxText()
        self._category_combo.append("all", "All")
        self._category_combo.append("SELECT", "SELECT")
        self._category_combo.append("INSERT", "INSERT")
        self._category_combo.append("UPDATE", "UPDATE")
        self._category_combo.append("DELETE", "DELETE")
        self._category_combo.append("DDL", "DDL")
        self._category_combo.append("OTHER", "Other")
        self._category_combo.set_active_id("all")
        self._category_combo.connect("changed", lambda c: self._load_history())
        filter_box.append(self._category_combo)

        self._search_entry = Gtk.Entry()
        self._search_entry.set_placeholder_text("Search queries...")
        self._search_entry.set_hexpand(True)
        self._search_entry.connect("changed", self._on_search_changed)
        filter_box.append(self._search_entry)

        btn_clear = Gtk.Button(label="Clear History")
        btn_clear.add_css_class("destructive-action")
        btn_clear.connect("clicked", self._on_clear)
        filter_box.append(btn_clear)

        main_box.append(filter_box)

        # --- History list ---
        # Columns: date, time, query (display), row_count, category
        self._list_store = Gtk.ListStore(str, str, str, str, str)
        self._tree = Gtk.TreeView(model=self._list_store)
        self._tree.set_headers_visible(True)

        # Date
        date_renderer = Gtk.CellRendererText()
        date_col = Gtk.TreeViewColumn("Date", date_renderer, text=0)
        date_col.set_min_width(100)
        self._tree.append_column(date_col)

        # Time
        time_renderer = Gtk.CellRendererText()
        time_col = Gtk.TreeViewColumn("Time", time_renderer, text=1)
        time_col.set_min_width(70)
        self._tree.append_column(time_col)

        # Category
        cat_renderer = Gtk.CellRendererText()
        cat_col = Gtk.TreeViewColumn("Type", cat_renderer, text=4)
        cat_col.set_min_width(70)
        self._tree.append_column(cat_col)

        # Query (expands to fill)
        query_renderer = Gtk.CellRendererText()
        query_renderer.set_property("ellipsize", 3)  # END
        query_col = Gtk.TreeViewColumn("Query", query_renderer, text=2)
        query_col.set_expand(True)
        self._tree.append_column(query_col)

        # Rows
        rows_renderer = Gtk.CellRendererText()
        rows_col = Gtk.TreeViewColumn("Rows", rows_renderer, text=3)
        rows_col.set_min_width(60)
        self._tree.append_column(rows_col)

        # Double-click also loads to editor
        self._tree.connect("row-activated", lambda *_: self._on_load(None))

        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)
        scroll.set_child(self._tree)
        main_box.append(scroll)

        # --- Status label ---
        self._status_label = Gtk.Label()
        self._status_label.set_halign(Gtk.Align.START)
        self._status_label.set_margin_start(4)
        main_box.append(self._status_label)

        # --- Buttons ---
        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        button_box.set_halign(Gtk.Align.END)

        btn_refresh_entry = Gtk.Button(label="Refresh Entry")
        btn_refresh_entry.set_tooltip_text(
            "Re-save the selected query to the history database. Useful "
            "for old entries pushed out of the recent-queries window."
        )
        btn_refresh_entry.connect("clicked", self._on_refresh_entry)
        button_box.append(btn_refresh_entry)

        btn_load = Gtk.Button(label="Load to Editor")
        btn_load.add_css_class("suggested-action")
        btn_load.connect("clicked", self._on_load)
        button_box.append(btn_load)

        btn_close = Gtk.Button(label="Close")
        btn_close.connect("clicked", lambda b: self.close())
        button_box.append(btn_close)

        main_box.append(button_box)
        self.set_child(main_box)

    # ==================================================================
    # Load / filter
    # ==================================================================

    def _load_history(self):
        """Reload the list store using the current category filter and search."""
        self._list_store.clear()
        self._full_queries.clear()
        self._history_ids.clear()

        search = self._search_entry.get_text().strip()
        category = self._category_combo.get_active_id() or "all"

        # Fetch from DB — search takes precedence over category filter.
        # We fetch a large window so the filter has enough to work with.
        if search:
            rows = self._history.search(search, limit=1000)
            # Apply category filter in-memory (search doesn't support it)
            if category != "all":
                rows = [r for r in rows if r.get("category", "OTHER") == category]
        else:
            rows = self._history.get_by_category(category, limit=1000)

        for r in rows:
            date_str = r["executed_at"][:10] if r["executed_at"] else ""
            time_str = (
                r["executed_at"][11:19] if r["executed_at"] and len(r["executed_at"]) > 11 else ""
            )
            query_display = r["query"][:100] + "..." if len(r["query"]) > 100 else r["query"]
            row_count = str(r["row_count"])
            cat = r.get("category", "OTHER")

            self._list_store.append([date_str, time_str, query_display, row_count, cat])
            self._full_queries.append(r["query"])
            self._history_ids.append(r["id"])

        # Update status
        self._status_label.set_text(f"{len(rows)} entries")

    def _on_search_changed(self, entry):
        """Debounce-less filter — the DB is fast enough for SQLite."""
        self._load_history()

    # ==================================================================
    # Actions
    # ==================================================================

    def _get_selected_index(self) -> int | None:
        """Return the list-store row index of the current selection."""
        selection = self._tree.get_selection()
        model, tree_iter = selection.get_selected()
        if tree_iter is None:
            return None
        path = model.get_path(tree_iter)
        return path.get_indices()[0]

    def _on_load(self, button):
        """Load the selected query into the editor."""
        idx = self._get_selected_index()
        if idx is None:
            self._status_label.set_text("⚠ Nothing selected")
            return

        if not (0 <= idx < len(self._full_queries)):
            self._status_label.set_text("⚠ Selection out of range")
            return

        query = self._full_queries[idx]
        logger.info(f"Loading query from history (index {idx}): {query[:80]}...")

        if self._on_select:
            self._on_select(query)
            self.close()
        else:
            self._status_label.set_text("⚠ No editor callback configured")

    def _on_refresh_entry(self, button):
        """Re-save the selected query to the history database.

        Useful when the visible entry refers to a query that has been
        pushed out of the recent-queries window (get_recent returns only
        the newest N entries). Re-adding creates a fresh row with the
        current timestamp, so the entry becomes retrievable again.
        """
        idx = self._get_selected_index()
        if idx is None:
            self._status_label.set_text("⚠ Nothing selected")
            return

        if not (0 <= idx < len(self._full_queries)):
            self._status_label.set_text("⚠ Selection out of range")
            return

        query = self._full_queries[idx]

        self._history.add(
            query=query,
            database="(restored from history)",
            execution_time=0.0,
            row_count=0,
            success=True,
        )

        logger.info(f"Refreshed history entry (index {idx}): {query[:80]}...")
        self._load_history()
        self._status_label.set_text("✓ Refreshed entry")

    def _on_clear(self, button):
        """Clear all history with a confirmation dialog."""
        dialog = Gtk.AlertDialog()
        dialog.set_message("Clear all query history?")
        dialog.set_detail("This cannot be undone.")
        dialog.set_buttons(["Cancel", "Clear"])
        dialog.set_cancel_button(0)
        dialog.set_default_button(0)

        def on_response(dialog, result):
            try:
                response = dialog.choose_finish(result)
                if response == 1:
                    self._history.clear()
                    self._load_history()
                    logger.info("Query history cleared by user")
            except Exception:
                pass

        dialog.choose(self, None, on_response)
