# ----------------------------------------------------------------------
# SQL Schema Studio 0.5 - Column Editor Dialog (GPLv3)
# Copyright (C) 2026 Peter Leukanič
# License: GNU GPL v3+ <https://www.gnu.org/licenses/gpl-3.0.txt>
# This is free software with NO WARRANTY.
# Feel free to distribute and modify.
# ----------------------------------------------------------------------

"""Dialog for editing table columns in the schema designer."""

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

from src.utils.gtk_helpers import set_margin
from src.utils.logging import get_logger

logger = get_logger(__name__)

# Available PostgreSQL data types
DATA_TYPES = [
    "serial",
    "bigserial",
    "integer",
    "bigint",
    "smallint",
    "varchar",
    "char",
    "text",
    "boolean",
    "date",
    "timestamp",
    "timestamptz",
    "numeric",
    "real",
    "double precision",
    "json",
    "jsonb",
    "uuid",
]


class ColumnEditorDialog(Gtk.Window):
    """Dialog for adding and editing columns."""

    def __init__(self, parent, schema_table, on_save_callback=None):
        super().__init__(
            title=f"Edit Columns — {schema_table.name}",
            transient_for=parent,
            modal=True,
        )
        self._table = schema_table
        self._on_save_callback = on_save_callback
        self.set_default_size(550, 450)

        self._build_ui()
        self._populate_columns()

    def _build_ui(self):
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        set_margin(main_box, 16)

        # Table name editor
        name_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        name_label = Gtk.Label(label="Table Name:")
        name_box.append(name_label)

        self._name_entry = Gtk.Entry()
        self._name_entry.set_text(self._table.name)
        self._name_entry.set_hexpand(True)
        name_box.append(self._name_entry)

        main_box.append(name_box)

        # Separator
        separator = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        main_box.append(separator)

        # Column list with headers
        self._list_store = Gtk.ListStore(str, str, bool, bool, str, int)
        self._tree = Gtk.TreeView(model=self._list_store)
        self._tree.set_headers_visible(True)

        # Name column (editable)
        name_renderer = Gtk.CellRendererText()
        name_renderer.set_property("editable", True)
        name_renderer.connect("edited", self._on_name_edited)
        name_col = Gtk.TreeViewColumn("Name", name_renderer, text=0)
        name_col.set_expand(True)
        self._tree.append_column(name_col)

        # Type column (editable via combo)
        type_renderer = Gtk.CellRendererText()
        type_renderer.set_property("editable", False)
        type_col = Gtk.TreeViewColumn("Type", type_renderer, text=1)
        self._tree.append_column(type_col)

        # Primary Key toggle
        pk_renderer = Gtk.CellRendererToggle()
        pk_renderer.connect("toggled", self._on_pk_toggled)
        pk_col = Gtk.TreeViewColumn("PK", pk_renderer, active=2)
        self._tree.append_column(pk_col)

        # Nullable toggle
        null_renderer = Gtk.CellRendererToggle()
        null_renderer.connect("toggled", self._on_null_toggled)
        null_col = Gtk.TreeViewColumn("Nullable", null_renderer, active=3)
        self._tree.append_column(null_col)

        # Length column (editable)
        len_renderer = Gtk.CellRendererText()
        len_renderer.set_property("editable", True)
        len_renderer.connect("edited", self._on_length_edited)
        len_col = Gtk.TreeViewColumn("Length", len_renderer, text=5)
        self._tree.append_column(len_col)

        # Scrolled list
        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)
        scroll.set_child(self._tree)
        main_box.append(scroll)

        # Type selector for editing selected row
        type_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        type_label = Gtk.Label(label="Set selected type:")
        type_box.append(type_label)

        self._type_combo = Gtk.ComboBoxText()
        for dtype in DATA_TYPES:
            self._type_combo.append_text(dtype)
        self._type_combo.set_active(DATA_TYPES.index("integer"))
        type_box.append(self._type_combo)

        btn_apply_type = Gtk.Button(label="Apply")
        btn_apply_type.connect("clicked", self._on_apply_type)
        type_box.append(btn_apply_type)

        main_box.append(type_box)

        # Buttons
        btn_add = Gtk.Button(label="Add Column")
        btn_add.connect("clicked", self._on_add_column)
        btn_remove = Gtk.Button(label="Remove Selected")
        btn_remove.connect("clicked", self._on_remove_column)
        btn_save = Gtk.Button(label="Save")
        btn_save.connect("clicked", self._on_save)
        btn_close = Gtk.Button(label="Cancel")
        btn_close.connect("clicked", lambda b: self.close())

        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        button_box.set_halign(Gtk.Align.END)
        button_box.append(btn_add)
        button_box.append(btn_remove)
        button_box.append(btn_close)
        button_box.append(btn_save)
        set_margin(button_box, 12)
        main_box.append(button_box)

        self.set_child(main_box)

    def _populate_columns(self):
        """Load existing columns into the list."""
        logger.debug(f"Populating {len(self._table.columns)} columns for {self._table.name}")
        for col in self._table.columns:
            length = col.length if col.length else 0
            logger.debug(f"  Adding column: {col.name} {col.data_type}")
            self._list_store.append(
                [
                    col.name,
                    col.data_type,
                    col.is_primary,
                    col.nullable,
                    "",
                    length,
                ]
            )
        logger.debug(f"List store now has {len(self._list_store)} rows")

    def _add_row(self, name="new_column", dtype="integer", is_pk=False, nullable=True, length=0):
        """Add a row to the list store."""
        return self._list_store.append([name, dtype, is_pk, nullable, "", length])

    # --- Signal handlers ---

    def _on_name_edited(self, renderer, path, new_text):
        if new_text.strip():
            self._list_store[path][0] = new_text.strip()

    def _on_pk_toggled(self, renderer, path):
        self._list_store[path][2] = not self._list_store[path][2]
        # If setting PK, auto-set NOT NULL
        if self._list_store[path][2]:
            self._list_store[path][3] = False

    def _on_null_toggled(self, renderer, path):
        # Can't set NULL if it's a primary key
        if self._list_store[path][2]:
            return
        self._list_store[path][3] = not self._list_store[path][3]

    def _on_length_edited(self, renderer, path, new_text):
        try:
            val = int(new_text) if new_text.strip() else 0
            self._list_store[path][5] = max(0, val)
        except ValueError:
            pass

    def _on_apply_type(self, button):
        """Apply the selected type to the selected row."""
        selection = self._tree.get_selection()
        model, tree_iter = selection.get_selected()
        if tree_iter:
            new_type = self._type_combo.get_active_text()
            model.set_value(tree_iter, 1, new_type)

    def _on_add_column(self, button):
        count = len(self._list_store)
        logger.debug(f"Adding column, current count: {count}")
        self._add_row(name=f"column_{count + 1}")
        logger.debug(f"List store now has {len(self._list_store)} rows")

    def _on_remove_column(self, button):
        selection = self._tree.get_selection()
        model, tree_iter = selection.get_selected()
        if tree_iter:
            col_name = model.get_value(tree_iter, 0)
            model.remove(tree_iter)
            logger.debug(f"Removed column '{col_name}' from {self._table.name}")

    def _on_save(self, button):
        try:
            from src.ui.schema_designer import TableColumn

            logger.info("Save clicked")
            logger.debug(
                f"Table before save: {self._table.name}, columns: {len(self._table.columns)}"
            )

            new_name = self._name_entry.get_text().strip()
            if new_name:
                self._table.name = new_name
                logger.debug(f"Name changed to: {new_name}")

            self._table.columns.clear()
            logger.debug(f"Columns cleared, list_store rows: {len(self._list_store)}")

            for row in self._list_store:
                name = row[0]
                dtype = row[1]
                is_pk = row[2]
                nullable = row[3]
                length = row[5] if row[5] > 0 else None
                logger.debug(f"  Saving column: {name} {dtype} PK={is_pk}")
                self._table.columns.append(
                    TableColumn(
                        name=name,
                        data_type=dtype,
                        is_primary=is_pk,
                        nullable=nullable,
                        length=length,
                    )
                )

            logger.debug(f"Calling on_save callback: {self._on_save_callback}")
            if self._on_save_callback:
                self._on_save_callback(self._table)

            logger.debug("Closing dialog")
            self.close()
        except Exception as e:
            logger.error(f"SAVE ERROR: {e}")
            import traceback

            traceback.print_exc()
