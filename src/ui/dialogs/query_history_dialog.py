# ----------------------------------------------------------------------
# SQL Schema Studio 0.8 - Query History Dialog (GPLv3)
# Copyright (C) 2026 Peter Leukanič
# License: GNU GPL v3+ <https://www.gnu.org/licenses/gpl-3.0.txt>
# This is free software with NO WARRANTY.
# Feel free to distribute and modify.
# ----------------------------------------------------------------------

"""Query history dialog with search."""

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

from src.utils.gtk_helpers import set_margin
from src.utils.logging import get_logger

logger = get_logger(__name__)


class QueryHistoryDialog(Gtk.Window):
    """Dialog showing query history."""

    def __init__(self, parent, query_history, on_select=None):
        super().__init__(
            title="Query History",
            transient_for=parent,
            modal=False,
        )
        self._history = query_history
        self._on_select = on_select
        self.set_default_size(650, 450)
        self._build_ui()
        self._load_history()

    def _build_ui(self):
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        set_margin(main_box, 12)

        # Search bar
        search_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self._search_entry = Gtk.Entry()
        self._search_entry.set_placeholder_text("Search queries...")
        self._search_entry.set_hexpand(True)
        self._search_entry.connect("changed", self._on_search_changed)
        search_box.append(self._search_entry)

        btn_clear = Gtk.Button(label="Clear History")
        btn_clear.connect("clicked", self._on_clear)
        search_box.append(btn_clear)

        main_box.append(search_box)

        # History list
        self._list_store = Gtk.ListStore(str, str, str, str, str)
        self._tree = Gtk.TreeView(model=self._list_store)
        self._tree.set_headers_visible(True)

        # Date column
        date_renderer = Gtk.CellRendererText()
        date_col = Gtk.TreeViewColumn("Date", date_renderer, text=0)
        date_col.set_min_width(160)
        self._tree.append_column(date_col)

        # Column Col
        cat_renderer = Gtk.CellRendererText()
        cat_col = Gtk.TreeViewColumn("Type", cat_renderer, text=4)
        cat_col.set_min_width(60)
        self._tree.append_column(cat_col)

        # Time column
        time_renderer = Gtk.CellRendererText()
        time_col = Gtk.TreeViewColumn("Time", time_renderer, text=1)
        time_col.set_min_width(60)
        self._tree.append_column(time_col)

        # Query column
        query_renderer = Gtk.CellRendererText()
        query_renderer.set_property("ellipsize", 3)  # END
        query_col = Gtk.TreeViewColumn("Query", query_renderer, text=2)
        query_col.set_expand(True)
        self._tree.append_column(query_col)

        # Rows column
        rows_renderer = Gtk.CellRendererText()
        rows_col = Gtk.TreeViewColumn("Rows", rows_renderer, text=3)
        self._tree.append_column(rows_col)

        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)
        scroll.set_child(self._tree)
        main_box.append(scroll)

        # Buttons
        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        button_box.set_halign(Gtk.Align.END)

        btn_load = Gtk.Button(label="Load to Editor")
        btn_load.add_css_class("suggested-action")
        btn_load.connect("clicked", self._on_load)
        button_box.append(btn_load)

        btn_close = Gtk.Button(label="Close")
        btn_close.connect("clicked", lambda b: self.close())
        button_box.append(btn_close)

        main_box.append(button_box)
        self.set_child(main_box)

    def _load_history(self, search: str = ""):
        self._list_store.clear()
        rows = self._history.search(search) if search else self._history.get_recent()

        for r in rows:
            date_str = r["executed_at"][:10] if r["executed_at"] else ""
            time_str = (
                r["executed_at"][11:19] if r["executed_at"] and len(r["executed_at"]) > 11 else ""
            )
            query = r["query"][:100] + "..." if len(r["query"]) > 100 else r["query"]
            row_count = str(r["row_count"])
            category = r.get("category", "OTHER")
            self._list_store.append([date_str, time_str, query, row_count, category])

    def _on_search_changed(self, entry):
        """Filter by search term."""
        self._load_history(entry.get_text())

    def _on_load(self, button):
        """Load selected query into editor."""
        selection = self._tree.get_selection()
        model, tree_iter = selection.get_selected()
        if tree_iter:
            date_str = model.get_value(tree_iter, 0)
            time_str = model.get_value(tree_iter, 1)
            # Find the full query by date/time
            rows = self._history.get_recent(200)
            for r in rows:
                if r["executed_at"] and r["executed_at"].startswith(f"{date_str} {time_str}"):
                    if self._on_select:
                        self._on_select(r["query"])
                    self.close()
                    return

    def _on_clear(self, button):
        """Clear all history."""
        self._history.clear()
        self._list_store.clear()
