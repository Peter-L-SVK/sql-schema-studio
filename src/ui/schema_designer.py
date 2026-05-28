# ----------------------------------------------------------------------
# SQL Schema Studio 0.5 - Schema Designer (GPLv3)
# Copyright (C) 2026 Peter Leukanič
# License: GNU GPL v3+ <https://www.gnu.org/licenses/gpl-3.0.txt>
# This is free software with NO WARRANTY.
# Feel free to distribute and modify.
# ----------------------------------------------------------------------

"""Visual schema designer with drag-and-drop table editing."""

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, Gdk, GObject
import cairo

from src.config import (
    SCHEMA_TABLE_WIDTH,
    SCHEMA_TABLE_HEADER_HEIGHT,
    SCHEMA_TABLE_ROW_HEIGHT,
    SCHEMA_TABLE_BODY_PADDING,
)
from src.utils.logging import get_logger
from src.utils.gtk_helpers import set_margin

logger = get_logger(__name__)
GType = GObject.GType


class ForeignKey:
    """Represents a foreign key relationship between two tables."""

    def __init__(self, name: str, from_table: str, from_column: str, to_table: str, to_column: str):
        self.name = name
        self.from_table = from_table
        self.to_table = to_table
        self.from_column = from_column
        self.to_column = to_column


class SchemaDesigner(Gtk.Box):
    """Visual database schema designer."""

    def __init__(self, window):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self._window = window
        self.set_size_request(800, 600)
        self._relationships: list[ForeignKey] = []
        self._creating_relationship: tuple | None = None  # (table, column) waiting for target
        self._selected_table: SchemaTable | None = None

        # Toolbar
        toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        toolbar.add_css_class("toolbar")
        set_margin(toolbar, 8)

        btn_add_table = Gtk.Button(label="Add Table")
        btn_add_table.connect("clicked", self._on_add_table)
        toolbar.append(btn_add_table)

        btn_delete_table = Gtk.Button(label="Delete Table")
        btn_delete_table.connect("clicked", self._on_delete_table)
        toolbar.append(btn_delete_table)

        btn_generate = Gtk.Button(label="Generate SQL")
        btn_generate.connect("clicked", self._on_generate_sql)
        toolbar.append(btn_generate)

        self.append(toolbar)

        # Drawing area
        self._canvas = Gtk.DrawingArea()
        self._canvas.set_draw_func(self._on_draw)
        self._canvas.set_hexpand(True)
        self._canvas.set_vexpand(True)

        # Drop target — accept tables from browser
        drop_target = Gtk.DropTarget.new(GObject.TYPE_STRING, Gdk.DragAction.COPY)
        drop_target.connect("drop", self._on_drop)
        self._canvas.add_controller(drop_target)

        # Drop target for .sql files from file manager
        file_drop_target = Gtk.DropTarget.new(Gdk.FileList, Gdk.DragAction.COPY)
        file_drop_target.connect("drop", self._on_file_drop)
        self._canvas.add_controller(file_drop_target)

        # Enable mouse events
        drag_gesture = Gtk.GestureDrag()
        drag_gesture.connect("drag-begin", self._on_drag_begin)
        drag_gesture.connect("drag-update", self._on_drag_update)
        drag_gesture.connect("drag-end", self._on_drag_end)
        self._canvas.add_controller(drag_gesture)

        click_gesture = Gtk.GestureClick()
        click_gesture.connect("pressed", self._on_click)
        self._canvas.add_controller(click_gesture)

        # Right-click for relationship creation — ADD THIS
        right_click = Gtk.GestureClick()
        right_click.set_button(3)
        right_click.connect("pressed", self._on_right_click)
        self._canvas.add_controller(right_click)

        self.append(self._canvas)

        # State
        self._tables: list[SchemaTable] = []
        self._dragging: SchemaTable | None = None
        self._drag_offset_x: float = 0.0
        self._drag_offset_y: float = 0.0

    def _on_add_table(self, button):
        """Add a new table to the canvas."""
        count = len(self._tables) + 1
        table = SchemaTable(
            name=f"new_table_{count}",
            x=50 + (count * 30) % 400,
            y=50 + (count * 30) % 300,
        )
        table.columns.append(TableColumn("id", "serial", is_primary=True))
        self._tables.append(table)
        logger.info(f"Added table: {table.name}")
        self._canvas.queue_draw()

    def _on_delete_table(self, button):
        """Delete the selected table and its relationships."""
        if self._selected_table is None:
            logger.warning("No table selected to delete")
            return

        table = self._selected_table

        # Remove relationships involving this table
        self._relationships = [
            fk
            for fk in self._relationships
            if fk.from_table != table.name and fk.to_table != table.name
        ]

        # Clear relationship creation if using this table
        if self._creating_relationship and self._creating_relationship[0] == table:
            self._creating_relationship = None

        # Remove the table
        self._tables.remove(table)
        self._selected_table = None

        logger.info(f"Deleted table: {table.name}")
        self._canvas.queue_draw()

    def _on_generate_sql(self, button):
        """Generate SQL and show in editor."""
        if not self._tables:
            return

        sql_lines = []
        for table in self._tables:
            sql_lines.append(table.to_sql())
            sql_lines.append("")

        for fk in self._relationships:
            source_table = next((t for t in self._tables if t.name == fk.from_table), None)
            target_table = next((t for t in self._tables if t.name == fk.to_table), None)

            src_schema = source_table.schema if source_table else "public"
            tgt_schema = target_table.schema if target_table else "public"

            sql_lines.append(
                f'ALTER TABLE {src_schema}."{fk.from_table}" '
                f'ADD CONSTRAINT "{fk.name}" '
                f'FOREIGN KEY ("{fk.from_column}") '
                f'REFERENCES {tgt_schema}."{fk.to_table}" ("{fk.to_column}");'
            )
            sql_lines.append("")

        sql = "\n".join(sql_lines)
        self._window.editor.set_text(sql)
        logger.info(
            f"Generated SQL for {len(self._tables)} tables, {len(self._relationships)} relationships"
        )

    def _find_column_at(self, table, x, y):
        """Find which column of a table is at the given position."""
        if not table or not table.columns:
            return None

        line_height = 20
        header_height = line_height + 6  # Same as in _draw_table

        # The body starts right after the header
        body_start_y = table.y + header_height

        # First column text is at body_start_y + line_height - 4 (from _draw_table)
        # So column 0 occupies body_start_y to body_start_y + line_height
        col_index = int((y - body_start_y) / line_height)

        if 0 <= col_index < len(table.columns):
            return table.columns[col_index]
        return None

    def _find_table_at(self, x: float, y: float):
        """Find a table at the given canvas coordinates."""
        for table in reversed(self._tables):
            if table.contains(x, y):
                return table
        return None

    def _on_drag_begin(self, gesture, start_x, start_y):
        """Start dragging a table."""
        table = self._find_table_at(start_x, start_y)
        if table:
            self._dragging = table
            self._drag_offset_x = table.x - start_x
            self._drag_offset_y = table.y - start_y
            logger.debug(f"Dragging {table.name}")

    def _on_drag_update(self, gesture, offset_x, offset_y):
        """Update table position during drag."""
        if self._dragging:
            _, start_x, start_y = gesture.get_start_point()
            self._dragging.x = start_x + offset_x + self._drag_offset_x
            self._dragging.y = start_y + offset_y + self._drag_offset_y
            self._canvas.queue_draw()

    def _on_drag_end(self, gesture, offset_x, offset_y):
        """Stop dragging."""
        if self._dragging:
            logger.debug(
                f"Dropped {self._dragging.name} at "
                f"({self._dragging.x:.0f}, {self._dragging.y:.0f})"
            )
            self._dragging = None
            self._canvas.queue_draw()

    def _on_click(self, gesture, n_press, x, y):
        """Handle click on tables."""
        table = self._find_table_at(x, y)

        # Select table on single click
        self._selected_table = table

        if table and n_press == 2:
            self._edit_table(table)

        self._canvas.queue_draw()

    def _on_right_click(self, gesture, n_press, x, y):
        """Right-click a table to start/complete a relationship."""
        button = gesture.get_current_button()
        if button != 3:
            return

        table = self._find_table_at(x, y)

        if not table:
            self._creating_relationship = None
            self._canvas.queue_draw()
            return

        # Find which column was clicked
        clicked_column = self._find_column_at(table, x, y)

        if self._creating_relationship is None:
            # Start creating — use the clicked column
            if not clicked_column:
                logger.warning("No column clicked")
                return
            self._creating_relationship = (table, clicked_column)
            logger.info(f"Creating relationship from {table.name}.{clicked_column.name}")
        else:
            # Complete — create FK from source column to clicked target column
            source_table, source_col = self._creating_relationship
            if source_table == table:
                self._creating_relationship = None
                return

            if not clicked_column:
                logger.warning("No target column clicked")
                return

            fk_name = f"fk_{table.name}_{source_table.name}"
            fk = ForeignKey(
                name=fk_name,
                from_table=source_table.name,
                from_column=source_col.name,
                to_table=table.name,
                to_column=clicked_column.name,
            )
            self._relationships.append(fk)
            logger.info(
                f"Created FK: {source_table.name}.{source_col.name} -> {table.name}.{clicked_column.name}"
            )
            self._creating_relationship = None

        self._canvas.queue_draw()

    def _edit_table(self, table):
        """Open dialog to edit table columns."""
        from src.ui.dialogs.column_editor import ColumnEditorDialog

        def on_save(saved_table):
            self._canvas.queue_draw()

        dialog = ColumnEditorDialog(self._window, table, on_save_callback=on_save)
        dialog.present()

    def _on_draw(self, area, cr, width, height):
        """Draw the schema canvas."""
        # Background and grid... (unchanged)

        # Draw relationships
        for fk in self._relationships:
            self._draw_relationship(cr, fk)

        # Draw pending relationship
        if self._creating_relationship:
            table, col = self._creating_relationship
            # Find the table position and the bottom-center of it
            src_x = table.x + table.get_size()[0] / 2
            src_y = table.y + table.get_size()[1]
            # Draw to mouse? We need current pointer position.
            # For now, draw a dashed line to the bottom of the source table
            cr.set_source_rgb(0.8, 0.3, 0.3)
            cr.set_dash([5, 5])
            cr.set_line_width(1.5)
            cr.move_to(src_x, src_y)
            cr.line_to(src_x, src_y + 50)  # Placeholder — ideally tracks mouse
            cr.stroke()
            cr.set_dash([])

        # Tables
        for table in self._tables:
            self._draw_table(cr, table)

    def _draw_relationship(self, cr, fk):
        """Draw a relationship line between two tables."""
        # Find source and target tables
        source_table = None
        target_table = None
        for t in self._tables:
            if t.name == fk.from_table:
                source_table = t
            if t.name == fk.to_table:
                target_table = t

        if not source_table or not target_table:
            return

        # Calculate connection points
        src_w, src_h = source_table.get_size()
        tgt_w, tgt_h = target_table.get_size()

        # Start from bottom-center of source
        x1 = source_table.x + src_w / 2
        y1 = source_table.y + src_h

        # End at top-center of target
        x2 = target_table.x + tgt_w / 2
        y2 = target_table.y

        # Draw line with FK label
        cr.set_source_rgb(0.2, 0.4, 0.6)
        cr.set_line_width(2)
        cr.move_to(x1, y1)
        cr.line_to(x2, y2)
        cr.stroke()

        # Draw "1" at source end and "N" at target end
        cr.set_source_rgb(0.2, 0.4, 0.6)
        cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        cr.set_font_size(10)

        # Source: "1"
        cr.move_to(x1 + 5, y1 - 5)
        cr.show_text("1")

        # Target: "N"
        cr.move_to(x2 - 15, y2 + 12)
        cr.show_text("N")

    def _draw_table(self, cr, table):
        """Draw a single table on the canvas."""
        # Calculate dimensions
        title = f" {table.name} "
        col_lines = []
        for col in table.columns:
            pk = "PK" if col.is_primary else ""
            dtype = col.data_type
            if col.length:
                dtype = f"{dtype}({col.length})"
            col_lines.append(f" {col.name}: {dtype} {pk} ")

        if col_lines:
            max_line = max(len(title), max(len(c) for c in col_lines))
        else:
            max_line = len(title)

        line_height = 20
        header_height = line_height + 6
        body_height = len(col_lines) * line_height + 6
        total_height = header_height + body_height
        total_width = max(max_line * 8, 120)

        # Shadow
        cr.set_source_rgba(0, 0, 0, 0.15)
        cr.rectangle(table.x + 3, table.y + 3, total_width, total_height)
        cr.fill()

        # Body background
        cr.set_source_rgb(1, 1, 1)
        cr.rectangle(table.x, table.y, total_width, total_height)
        cr.fill()

        # Header background
        cr.set_source_rgb(0.3, 0.5, 0.8)
        cr.rectangle(table.x, table.y, total_width, header_height)
        cr.fill()

        # Header border
        cr.set_source_rgb(0.2, 0.3, 0.5)
        cr.rectangle(table.x, table.y, total_width, header_height)
        cr.set_line_width(1)
        cr.stroke()

        # Body border
        cr.set_source_rgb(0.5, 0.5, 0.5)
        cr.rectangle(table.x, table.y, total_width, total_height)
        cr.set_line_width(1)
        cr.stroke()

        # Divider line
        cr.set_source_rgb(0.4, 0.5, 0.6)
        cr.move_to(table.x, table.y + header_height)
        cr.line_to(table.x + total_width, table.y + header_height)
        cr.stroke()

        # Title text
        cr.set_source_rgb(1, 1, 1)
        cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        cr.set_font_size(13)
        cr.move_to(table.x + 6, table.y + header_height - 6)
        cr.show_text(table.name)

        # Column text
        cr.set_source_rgb(0.1, 0.1, 0.1)
        cr.select_font_face("Monospace", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
        cr.set_font_size(11)
        y_pos = table.y + header_height + line_height - 4
        for i, line in enumerate(col_lines):
            text = col_lines[i].strip()
            cr.move_to(table.x + 8, y_pos)
            cr.show_text(text)
            y_pos += line_height

        # Selection highlight
        if table == self._selected_table:
            cr.set_source_rgb(0.3, 0.6, 1.0)
            cr.set_line_width(2)
            cr.rectangle(table.x - 2, table.y - 2, total_width + 4, total_height + 4)
            cr.stroke()

    def _on_drop(self, target, value, x, y):
        """Handle drops from browser."""
        if isinstance(value, str):
            return self._drop_table_from_browser(value, x, y)

        return False

    def _drop_table_from_browser(self, table_name, x, y):
        """Import a table from the database browser."""
        if not table_name:
            return False

        parts = table_name.split(".", 1)
        schema = parts[0] if len(parts) > 1 else "public"
        name = parts[1] if len(parts) > 1 else parts[0]

        logger.info(f"Dropped table from browser: {schema}.{name}")

        # Load columns directly
        try:
            columns = self._window.db_connector.execute_sync(
                """SELECT column_name, data_type, is_nullable,
                character_maximum_length
                FROM information_schema.columns
                WHERE table_schema = %s AND table_name = %s
                ORDER BY ordinal_position""",
                (schema, name),
            )
        except Exception as e:
            logger.error(f"Failed to load columns: {e}")
            return False

        table = SchemaTable(name=name, x=x, y=y)
        for col in columns:
            dtype = col["data_type"]
            length = col.get("character_maximum_length")
            nullable = col["is_nullable"] == "YES"
            is_pk = col["column_name"] == "id"
            table.columns.append(
                TableColumn(
                    name=col["column_name"],
                    data_type=dtype,
                    is_primary=is_pk,
                    nullable=nullable,
                    length=length,
                )
            )

        self._tables.append(table)
        self._canvas.queue_draw()
        logger.info(f"Imported table: {name} with {len(table.columns)} columns")
        return True

    def _on_file_drop(self, target, value, x, y):
        """Handle .sql files dropped from file manager."""
        files = value.get_files()
        for file in files:
            path = file.get_path()
            if path.endswith(".sql"):
                self._import_sql_file(path, x, y)
        return True

    def _import_sql_file(self, path, x, y):
        """Parse SQL file using sqlparse."""
        from src.core.schema_parser import SchemaParser

        logger.info(f"Importing SQL file: {path}")

        try:
            with open(path, "r") as f:
                content = f.read()
        except Exception as e:
            logger.error(f"Failed to read SQL file: {e}")
            return

        parser = SchemaParser()
        tables, foreign_keys = parser.parse_sql(content)

        offset_x = x
        offset_y = y

        for table_data in tables:
            table = SchemaTable(name=table_data["name"], x=offset_x, y=offset_y)
            table.schema = table_data["schema"]

            for col_data in table_data["columns"]:
                table.columns.append(
                    TableColumn(
                        name=col_data["name"],
                        data_type=col_data["type"],
                        is_primary=col_data["is_pk"],
                        nullable=col_data["nullable"],
                        length=col_data["length"],
                    )
                )

            self._tables.append(table)
            offset_x += 200
            if offset_x > 600:
                offset_x = x
                offset_y += 200
            logger.info(f"Imported table: {table.name} with {len(table.columns)} columns")

        for fk_data in foreign_keys:
            fk = ForeignKey(
                name=fk_data["name"],
                from_table=fk_data["from_table"],
                from_column=fk_data["from_column"],
                to_table=fk_data["to_table"],
                to_column=fk_data["to_column"],
            )
            self._relationships.append(fk)
            logger.info(
                f"Imported FK: {fk.from_table}.{fk.from_column} -> {fk.to_table}.{fk.to_column}"
            )

        self._canvas.queue_draw()


class SchemaTable:
    """Represents a table on the designer canvas."""

    def __init__(self, name: str, x: float = 50, y: float = 50):
        self.name = name
        self.x = x
        self.y = y
        self.columns: list[TableColumn] = []
        self.schema = "public"
        self._width = SCHEMA_TABLE_WIDTH
        self._header_height = SCHEMA_TABLE_HEADER_HEIGHT
        self._row_height = SCHEMA_TABLE_ROW_HEIGHT
        self._body_padding = SCHEMA_TABLE_BODY_PADDING

    def contains(self, px: float, py: float) -> bool:
        """Check if a point is inside this table."""
        w, h = self.get_size()
        return self.x <= px <= self.x + w and self.y <= py <= self.y + h

    def get_size(self) -> tuple[float, float]:
        """Calculate table dimensions."""
        rows = max(len(self.columns), 1)
        return (
            self._width,
            self._header_height + rows * self._row_height + self._body_padding,
        )

    def to_sql(self) -> str:
        """Generate CREATE TABLE SQL."""

        def quote(name):
            return f'"{name}"'

        lines = [f"CREATE TABLE {self.schema}.{quote(self.name)} ("]
        col_defs = []
        for col in self.columns:
            col_defs.append(f"    {col.to_sql()}")
        pks = [c.name for c in self.columns if c.is_primary]
        if pks:
            col_defs.append(f"    PRIMARY KEY ({', '.join(quote(c) for c in pks)})")
        lines.append(",\n".join(col_defs))
        lines.append(");")
        return "\n".join(lines)


class TableColumn:
    """Column in the schema designer."""

    def __init__(
        self,
        name: str,
        data_type: str = "integer",
        is_primary: bool = False,
        nullable: bool = True,
        length: int | None = None,
    ):
        self.name = name
        self.data_type = data_type
        self.is_primary = is_primary
        self.nullable = nullable
        self.length = length

    def to_sql(self) -> str:
        """Generate column definition."""
        dtype = self.data_type
        if self.length:
            dtype = f"{dtype}({self.length})"
        parts = [f'"{self.name}"', dtype]
        if not self.nullable:
            parts.append("NOT NULL")
        return " ".join(parts)
