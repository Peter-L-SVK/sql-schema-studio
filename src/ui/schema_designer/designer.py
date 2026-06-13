# ----------------------------------------------------------------------
# SQL Schema Studio 0.9 - Schema Designer (GPLv3)
# Copyright (C) 2026 Peter Leukanič
# License: GNU GPL v3+ <https://www.gnu.org/licenses/gpl-3.0.txt>
# This is free software with NO WARRANTY.
# Feel free to distribute and modify.
# ----------------------------------------------------------------------

"""Visual schema designer with drag-and-drop table editing."""

import math
import copy

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gtk, Gdk, GObject, GLib

from src.config import (
    SCHEMA_CANVAS_WIDTH,
    SCHEMA_CANVAS_HEIGHT,
    SCHEMA_COLORS,
)
from src.utils.logging import get_logger
from src.utils.gtk_helpers import set_margin
from src.ui.schema_designer.models import ForeignKey, SchemaTable, TableColumn
from src.ui.schema_designer.routing import RoutingMixin
from src.ui.schema_designer.drawing import DrawingMixin
from src.ui.schema_designer.worker_bridge import WorkerBridgeMixin

logger = get_logger(__name__)
GType = GObject.GType


class SchemaDesigner(WorkerBridgeMixin, RoutingMixin, DrawingMixin, Gtk.Box):
    """Visual database schema designer."""

    def __init__(self, window):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self._window = window
        self.set_size_request(800, 600)
        self._relationships: list[ForeignKey] = []
        self._creating_relationship: tuple | None = None
        self._table_index: dict[str, SchemaTable] = {}
        self._selected_table: SchemaTable | None = None
        self._line_style = "straight"
        self._selected_color = SCHEMA_COLORS["blue"]

        # Custom colors storage
        self._custom_colors: list[tuple] = []
        self._max_custom_colors = 16

        self._undo_stack: list[dict] = []
        self._redo_stack: list[dict] = []
        self._max_history = 50

        # Waypoint dragging state
        self._dragging_waypoint_fk: ForeignKey | None = None
        self._dragging_waypoint_index: int = -1

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

        sep_dir = Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)
        toolbar.append(sep_dir)

        self._btn_color = Gtk.ToggleButton()
        self._btn_color.set_tooltip_text("Table color")
        self._btn_color.connect("toggled", self._on_color_button_toggled)
        toolbar.append(self._btn_color)
        self._update_color_button()

        self._direction_forward = False
        btn_dir = Gtk.Button(label="←")
        btn_dir.set_tooltip_text("FK direction: forward (child → parent)")
        btn_dir.connect("clicked", self._on_toggle_direction)
        toolbar.append(btn_dir)
        self._btn_direction = btn_dir

        btn_reset_zoom = Gtk.Button(label="1:1")
        btn_reset_zoom.set_tooltip_text("Reset zoom and pan")
        btn_reset_zoom.connect("clicked", self._on_reset_zoom)
        toolbar.append(btn_reset_zoom)

        sep_undo = Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)
        toolbar.append(sep_undo)

        btn_undo = Gtk.Button(label="↩")
        btn_undo.set_tooltip_text("Undo (Ctrl+Z)")
        btn_undo.connect("clicked", self._on_undo)
        toolbar.append(btn_undo)

        btn_redo = Gtk.Button(label="↪")
        btn_redo.set_tooltip_text("Redo (Ctrl+Y)")
        btn_redo.connect("clicked", self._on_redo)
        toolbar.append(btn_redo)

        sep = Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)
        toolbar.append(sep)

        self.btn_line_straight = Gtk.Button(label="╱")
        self.btn_line_straight.set_tooltip_text("Straight lines")
        self.btn_line_straight.connect("clicked", lambda b: self._set_line_style("straight"))
        toolbar.append(self.btn_line_straight)

        self.btn_line_curve = Gtk.Button(label="∿")
        self.btn_line_curve.set_tooltip_text("S-curve lines")
        self.btn_line_curve.connect("clicked", lambda b: self._set_line_style("curve"))
        toolbar.append(self.btn_line_curve)

        self.btn_line_ortho = Gtk.Button(label="└┐")
        self.btn_line_ortho.set_tooltip_text("Orthogonal lines (L-shape)")
        self.btn_line_ortho.connect("clicked", lambda b: self._set_line_style("ortho"))
        toolbar.append(self.btn_line_ortho)

        self.append(toolbar)

        # Drawing area
        self._canvas = Gtk.DrawingArea()
        self._canvas.set_draw_func(self._on_draw)
        self._canvas.set_hexpand(True)
        self._canvas.set_vexpand(True)
        self._canvas.set_content_width(SCHEMA_CANVAS_WIDTH)
        self._canvas.set_content_height(SCHEMA_CANVAS_HEIGHT)

        drop_target = Gtk.DropTarget.new(GObject.TYPE_STRING, Gdk.DragAction.COPY)
        drop_target.connect("drop", self._on_drop)
        self._canvas.add_controller(drop_target)

        file_drop_target = Gtk.DropTarget.new(Gdk.FileList, Gdk.DragAction.COPY)
        file_drop_target.connect("drop", self._on_file_drop)
        self._canvas.add_controller(file_drop_target)

        drag_gesture = Gtk.GestureDrag()
        drag_gesture.connect("drag-begin", self._on_drag_begin)
        drag_gesture.connect("drag-update", self._on_drag_update)
        drag_gesture.connect("drag-end", self._on_drag_end)
        self._canvas.add_controller(drag_gesture)

        click_gesture = Gtk.GestureClick()
        click_gesture.connect("pressed", self._on_click)
        self._canvas.add_controller(click_gesture)

        right_click = Gtk.GestureClick()
        right_click.set_button(3)
        right_click.connect("pressed", self._on_right_click)
        self._canvas.add_controller(right_click)

        scroll = Gtk.ScrolledWindow()
        scroll.set_child(self._canvas)
        scroll.set_hexpand(True)
        scroll.set_vexpand(True)
        self.append(scroll)
        self.set_focusable(True)

        key_controller = Gtk.EventControllerKey()
        key_controller.connect("key-pressed", self._on_key_pressed)
        self.add_controller(key_controller)

        zoom_controller = Gtk.EventControllerScroll()
        zoom_controller.set_flags(Gtk.EventControllerScrollFlags.VERTICAL)
        zoom_controller.connect("scroll", self._on_scroll)
        self._canvas.add_controller(zoom_controller)

        pan_gesture = Gtk.GestureDrag()
        pan_gesture.set_button(2)
        pan_gesture.connect("drag-begin", self._on_pan_begin)
        pan_gesture.connect("drag-update", self._on_pan_update)
        self._canvas.add_controller(pan_gesture)

        self._zoom_level = 1.0
        self._min_zoom = 0.3
        self._max_zoom = 3.0
        self._pan_offset_x = 0.0
        self._pan_offset_y = 0.0
        self._pan_prev_x = 0.0
        self._pan_prev_y = 0.0

        # Path computation state
        self._path_serial = 0
        self._path_pending = False
        self._path_debounce_id = 0

        self._tables: list[SchemaTable] = []
        self._dragging: SchemaTable | None = None
        self._drag_offset_x: float = 0.0
        self._drag_offset_y: float = 0.0

    # =====================================================================
    # Line style
    # =====================================================================

    def _set_line_style(self, style):
        self._line_style = style
        for btn in [self.btn_line_straight, self.btn_line_curve, self.btn_line_ortho]:
            btn.remove_css_class("suggested-action")
        if style == "straight":
            self.btn_line_straight.add_css_class("suggested-action")
        elif style == "curve":
            self.btn_line_curve.add_css_class("suggested-action")
        elif style == "ortho":
            self.btn_line_ortho.add_css_class("suggested-action")
        self._canvas.queue_draw()

    # =====================================================================
    # Table management
    # =====================================================================

    def _on_add_table(self, button):
        self._save_state("add_table")
        count = len(self._tables) + 1
        table = SchemaTable(
            name=f"new_table_{count}",
            x=50 + (count * 30) % 400,
            y=50 + (count * 30) % 300,
        )
        table.columns.append(TableColumn("id", "serial", is_primary=True))
        self._tables.append(table)
        self._table_index[table.name] = table
        logger.info(f"Added table: {table.name}")
        self._update_canvas_size()
        self._invalidate_all_paths()
        self._canvas.queue_draw()

    def _update_canvas_size(self):
        if not self._tables:
            return
        max_x = 0
        max_y = 0
        for table in self._tables:
            w, h = table.get_size()
            max_x = max(max_x, table.x + w + 200)
            max_y = max(max_y, table.y + h + 200)
        self._canvas.set_content_width(max(SCHEMA_CANVAS_WIDTH, int(max_x)))
        self._canvas.set_content_height(max(SCHEMA_CANVAS_HEIGHT, int(max_y)))

    def _on_delete_table(self, button):
        self._save_state("delete_table")
        if self._selected_table is None:
            logger.warning("No table selected to delete")
            return
        table = self._selected_table
        self._relationships = [
            fk
            for fk in self._relationships
            if fk.from_table != table.name and fk.to_table != table.name
        ]
        if self._creating_relationship and self._creating_relationship[0] == table:
            self._creating_relationship = None
        if table.name in self._table_index:
            del self._table_index[table.name]
        self._tables.remove(table)
        self._selected_table = None
        logger.info(f"Deleted table: {table.name}")
        self._invalidate_all_paths()
        self._update_canvas_size()
        self._canvas.queue_draw()

    def _on_generate_sql(self, button):
        if not self._tables:
            return
        sql_lines = []
        for table in self._tables:
            sql_lines.append(table.to_sql())
            sql_lines.append("")
        for fk in self._relationships:
            source_table = self._table_index.get(fk.from_table)
            target_table = self._table_index.get(fk.to_table)
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
            f"Generated SQL for {len(self._tables)} tables, "
            f"{len(self._relationships)} relationships"
        )

    def _find_column_at(self, table, x, y):
        if not table or not table.columns:
            return None
        line_height = table._row_height
        header_height = line_height + 6
        body_start_y = table.y + header_height
        col_index = int((y - body_start_y) / line_height)
        if 0 <= col_index < len(table.columns):
            return table.columns[col_index]
        return None

    def _find_table_at(self, x: float, y: float):
        for table in reversed(self._tables):
            if table.contains(x, y):
                return table
        return None

    # =====================================================================
    # Waypoints
    # =====================================================================

    def _find_waypoint_at(self, x: float, y: float):
        for fk in self._relationships:
            for i, (wx, wy) in enumerate(fk.waypoints):
                if abs(x - wx) < 8 and abs(y - wy) < 8:
                    return fk, i
        return None, -1

    # =====================================================================
    # Drag & drop
    # =====================================================================

    def _on_drag_begin(self, gesture, start_x, start_y):
        fk, idx = self._find_waypoint_at(start_x, start_y)
        if fk is not None and idx >= 0:
            self._save_state("drag_waypoint")
            self._dragging_waypoint_fk = fk
            self._dragging_waypoint_index = idx
            logger.debug(f"Dragging waypoint {idx} of FK {fk.name}")
            return
        table = self._find_table_at(start_x, start_y)
        if table:
            self._save_state("drag_table")
            self._dragging = table
            self._drag_offset_x = table.x - start_x
            self._drag_offset_y = table.y - start_y
            logger.debug(f"Dragging {table.name}")

    def _on_drag_update(self, gesture, offset_x, offset_y):
        if self._dragging_waypoint_fk:
            _, start_x, start_y = gesture.get_start_point()
            new_x = start_x + offset_x
            new_y = start_y + offset_y
            self._dragging_waypoint_fk.waypoints[self._dragging_waypoint_index] = (
                new_x,
                new_y,
            )
            self._dragging_waypoint_fk._cached_path = []
            self._canvas.queue_draw()
            return
        if self._dragging:
            _, start_x, start_y = gesture.get_start_point()
            self._dragging.x = start_x + offset_x + self._drag_offset_x
            self._dragging.y = start_y + offset_y + self._drag_offset_y
            self._invalidate_all_paths()
            self._canvas.queue_draw()

    def _on_drag_end(self, gesture, offset_x, offset_y):
        if self._dragging_waypoint_fk:
            logger.debug(
                f"Dropped waypoint {self._dragging_waypoint_index} "
                f"of FK {self._dragging_waypoint_fk.name}"
            )
            self._dragging_waypoint_fk = None
            self._dragging_waypoint_index = -1
            self._canvas.queue_draw()
            return
        if self._dragging:
            logger.debug(
                f"Dropped {self._dragging.name} at "
                f"({self._dragging.x:.0f}, {self._dragging.y:.0f})"
            )
            self._dragging = None
            self._update_canvas_size()
            self._canvas.queue_draw()

    def _on_click(self, gesture, n_press, x, y):
        self.grab_focus()
        fk, idx = self._find_waypoint_at(x, y)
        if fk is not None and idx >= 0:
            if n_press == 2:
                self._save_state("delete_waypoint")
                del fk.waypoints[idx]
                fk._cached_path = []
                self._canvas.queue_draw()
                logger.info(
                    f"Deleted waypoint {idx} from FK {fk.from_table}->{fk.to_table}"
                )
            return
        table = self._find_table_at(x, y)
        if table:
            self._selected_table = table
            self._update_color_button()
            if n_press == 2:
                self._edit_table(table)
        else:
            self._selected_table = None
            fk = self._find_relationship_at(x, y)
            if fk:
                if n_press == 2:
                    self._save_state("delete_fk")
                    self._relationships.remove(fk)
                    logger.info(
                        f"Deleted FK: {fk.from_table}.{fk.from_column} "
                        f"-> {fk.to_table}.{fk.to_column}"
                    )
                elif n_press == 1:
                    self._save_state("toggle_fk_direction")
                    fk.direction = "reverse" if fk.direction == "forward" else "forward"
                    fk._cached_path = []
                    logger.info(
                        f"Toggled FK direction to {fk.direction}: "
                        f"{fk.from_table}.{fk.from_column} -> {fk.to_table}.{fk.to_column}"
                    )
        self._canvas.queue_draw()

    def _find_relationship_at(self, x, y):
        closest_fk = None
        closest_dist = float("inf")
        for fk in self._relationships:
            source_table = self._table_index.get(fk.from_table)
            target_table = self._table_index.get(fk.to_table)
            if not source_table or not target_table:
                continue
            path = self._calculate_line_path(fk, source_table, target_table)
            for i in range(len(path) - 1):
                x1, y1 = path[i]
                x2, y2 = path[i + 1]
                dist = abs(
                    (y2 - y1) * x - (x2 - x1) * y + x2 * y1 - y2 * x1
                ) / math.sqrt((y2 - y1) ** 2 + (x2 - x1) ** 2)
                if dist < closest_dist:
                    closest_dist = dist
                    closest_fk = fk
        if closest_fk and closest_dist < 80:
            return closest_fk
        return None

    def _on_toggle_direction(self, button):
        self._direction_forward = not self._direction_forward
        if self._direction_forward:
            button.set_label("←")
            button.set_tooltip_text("FK direction: forward (child → parent)")
        else:
            button.set_label("→")
            button.set_tooltip_text("FK direction: reverse (parent → child)")

    def _on_right_click(self, gesture, n_press, x, y):
        button = gesture.get_current_button()
        if button != 3:
            return
        table = self._find_table_at(x, y)
        if not table:
            self._creating_relationship = None
            self._canvas.queue_draw()
            return
        clicked_column = self._find_column_at(table, x, y)
        if self._creating_relationship is None:
            if not clicked_column:
                logger.warning("No column clicked")
                return
            self._creating_relationship = (table, clicked_column)
            logger.info(
                f"Creating relationship from {table.name}.{clicked_column.name}"
            )
        else:
            source_table, source_col = self._creating_relationship
            if source_table == table:
                self._creating_relationship = None
                return
            if not clicked_column:
                logger.warning("No target column clicked")
                return
            fk_name = f"fk_{table.name}_{source_table.name}"
            direction = "reverse" if self._direction_forward else "forward"
            fk = ForeignKey(
                name=fk_name,
                from_table=source_table.name,
                from_column=source_col.name,
                to_table=table.name,
                to_column=clicked_column.name,
                from_col_index=source_table.columns.index(source_col),
                to_col_index=table.columns.index(clicked_column),
                color=source_table.color,
                line_style=self._line_style,
                direction=direction,
            )
            self._save_state("add_fk")
            self._relationships.append(fk)
            self._creating_relationship = None
            self._invalidate_all_paths()
            self._canvas.queue_draw()
            logger.info(
                f"Created FK: {source_table.name}.{source_col.name} "
                f"-> {table.name}.{clicked_column.name}"
            )
        self._canvas.queue_draw()

    # =====================================================================
    # Keyboard
    # =====================================================================

    def _on_key_pressed(self, controller, keyval, keycode, state):
        if keyval == Gdk.KEY_Delete and self._selected_table:
            logger.info(f"Deleting selected table: {self._selected_table.name}")
            self._on_delete_table(None)
            return True
        if keyval == Gdk.KEY_plus and (state & Gdk.ModifierType.CONTROL_MASK):
            self._zoom_level = min(self._max_zoom, self._zoom_level + 0.1)
            self._canvas.queue_draw()
            return True
        if keyval == Gdk.KEY_minus and (state & Gdk.ModifierType.CONTROL_MASK):
            self._zoom_level = max(self._min_zoom, self._zoom_level - 0.1)
            self._canvas.queue_draw()
            return True
        if keyval == Gdk.KEY_0 and (state & Gdk.ModifierType.CONTROL_MASK):
            self._on_reset_zoom(None)
            return True
        if keyval == Gdk.KEY_Left:
            self._pan_offset_x += 50
            self._canvas.queue_draw()
            return True
        if keyval == Gdk.KEY_Right:
            self._pan_offset_x -= 50
            self._canvas.queue_draw()
            return True
        if keyval == Gdk.KEY_Up:
            self._pan_offset_y += 50
            self._canvas.queue_draw()
            return True
        if keyval == Gdk.KEY_Down:
            self._pan_offset_y -= 50
            self._canvas.queue_draw()
            return True
        if keyval == Gdk.KEY_z and (state & Gdk.ModifierType.CONTROL_MASK):
            self._on_undo(None)
            return True
        if keyval == Gdk.KEY_y and (state & Gdk.ModifierType.CONTROL_MASK):
            self._on_redo(None)
            return True
        return False

    # =====================================================================
    # Color
    # =====================================================================

    def _update_color_button(self):
        color = (
            self._selected_table.color
            if self._selected_table
            else self._selected_color
        )
        color_box = Gtk.DrawingArea()
        color_box.set_size_request(20, 20)
        color_box.set_can_target(False)
        color_box.set_focusable(False)

        def draw_color(area, cr, w, h, c=color):
            cr.set_source_rgb(*c)
            cr.paint()
            cr.set_source_rgb(0.3, 0.3, 0.3)
            cr.set_line_width(1)
            cr.rectangle(0, 0, w, h)
            cr.stroke()

        color_box.set_draw_func(draw_color)
        self._btn_color.set_child(color_box)

    def _on_color_button_toggled(self, button):
        self._on_color_button_clicked(button)

    def _on_color_button_clicked(self, button):
        popover = Gtk.Popover()
        popover.set_has_arrow(False)
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        set_margin(vbox, 8)
        vbox.append(Gtk.Label(label="Preset Colors", halign=Gtk.Align.START))
        preset_box = Gtk.FlowBox()
        preset_box.set_max_children_per_line(4)
        preset_box.set_row_spacing(4)
        preset_box.set_column_spacing(4)

        def make_swatch_callback(c):
            return lambda b: (self._apply_color(c), popover.popdown())

        for color_name, color_rgb in SCHEMA_COLORS.items():
            btn = Gtk.Button()
            btn.set_tooltip_text(color_name)
            swatch = Gtk.DrawingArea()
            swatch.set_size_request(24, 24)

            def draw_swatch(area, cr, w, h, c=color_rgb):
                cr.set_source_rgb(*c)
                cr.paint()
                cr.set_source_rgb(0.3, 0.3, 0.3)
                cr.set_line_width(1)
                cr.rectangle(0, 0, w, h)
                cr.stroke()

            swatch.set_draw_func(draw_swatch)
            btn.set_child(swatch)
            btn.connect("clicked", make_swatch_callback(color_rgb))
            preset_box.append(btn)
        vbox.append(preset_box)

        if self._custom_colors:
            vbox.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))
            vbox.append(Gtk.Label(label="Custom Colors", halign=Gtk.Align.START))
            custom_box = Gtk.FlowBox()
            custom_box.set_max_children_per_line(4)
            custom_box.set_row_spacing(4)
            custom_box.set_column_spacing(4)
            for rgb in self._custom_colors:
                btn = Gtk.Button()
                swatch = Gtk.DrawingArea()
                swatch.set_size_request(24, 24)

                def draw_custom(area, cr, w, h, c=rgb):
                    cr.set_source_rgb(*c)
                    cr.paint()
                    cr.set_source_rgb(0.3, 0.3, 0.3)
                    cr.set_line_width(1)
                    cr.rectangle(0, 0, w, h)
                    cr.stroke()

                swatch.set_draw_func(draw_custom)
                btn.set_child(swatch)
                btn.connect("clicked", make_swatch_callback(rgb))
                custom_box.append(btn)
            vbox.append(custom_box)

        vbox.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))
        btn_picker = Gtk.Button(label="Pick Custom Color...")

        def on_picker_clicked(b):
            popover.popdown()
            self._on_pick_custom_color()

        btn_picker.connect("clicked", on_picker_clicked)
        vbox.append(btn_picker)
        popover.set_child(vbox)
        popover.set_parent(button)
        popover.popup()

    def _apply_color(self, color):
        self._save_state("change_color")
        if self._selected_table:
            self._selected_table.color = color
            self._update_color_button()
            self._canvas.queue_draw()

    def _on_pick_custom_color(self):
        if not self._selected_table:
            return
        dialog = Gtk.ColorDialog()
        dialog.set_title("Pick Custom Table Color")
        dialog.set_modal(True)

        def on_color_selected(dialog, result):
            try:
                color = dialog.choose_rgba_finish(result)
                if color:
                    rgb = (color.red, color.green, color.blue)
                    if rgb not in self._custom_colors:
                        GLib.idle_add(lambda: self._custom_colors.append(rgb))
                        if len(self._custom_colors) > self._max_custom_colors:
                            GLib.idle_add(lambda: self._custom_colors.pop(0))
                    GLib.idle_add(lambda: self._apply_color(rgb))
            except Exception as e:
                logger.error(f"Color picker failed: {e}")

        dialog.choose_rgba(self._window, None, None, on_color_selected)

    def _edit_table(self, table):
        from src.ui.dialogs.column_editor import ColumnEditorDialog

        def on_save(saved_table):
            self._invalidate_all_paths()
            self._canvas.queue_draw()

        dialog = ColumnEditorDialog(self._window, table, on_save_callback=on_save)
        dialog.present()

    # =====================================================================
    # Drop handlers
    # =====================================================================

    def _on_drop(self, target, value, x, y):
        if isinstance(value, str):
            return self._drop_table_from_browser(value, x, y)
        return False

    def _drop_table_from_browser(self, table_name, x, y):
        if not table_name:
            return False
        parts = table_name.split(".", 1)
        schema = parts[0] if len(parts) > 1 else "public"
        name = parts[1] if len(parts) > 1 else parts[0]
        logger.info(f"Dropped table from browser: {schema}.{name}")
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
        self._table_index[table.name] = table
        self._invalidate_all_paths()
        self._update_canvas_size()
        self._canvas.queue_draw()
        logger.info(f"Imported table: {name} with {len(table.columns)} columns")
        return True

    def _on_file_drop(self, target, value, x, y):
        files = value.get_files()
        for file in files:
            path = file.get_path()
            if path.endswith(".sql"):
                self._import_sql_file(path, x, y)
        return True

    def _import_sql_file(self, path, x, y):
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
            self._table_index[table.name] = table
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
            logger.info(
                f"Imported table: {table.name} with {len(table.columns)} columns"
            )
        for fk_data in foreign_keys:
            source_table_obj = self._table_index.get(fk_data["from_table"])
            target_table_obj = self._table_index.get(fk_data["to_table"])
            from_idx = None
            to_idx = None
            if source_table_obj:
                for i, col in enumerate(source_table_obj.columns):
                    if col.name == fk_data["from_column"]:
                        from_idx = i
                        break
            if target_table_obj:
                for i, col in enumerate(target_table_obj.columns):
                    if col.name == fk_data["to_column"]:
                        to_idx = i
                        break
            fk = ForeignKey(
                name=fk_data["name"],
                from_table=fk_data["from_table"],
                from_column=fk_data["from_column"],
                to_table=fk_data["to_table"],
                to_column=fk_data["to_column"],
                from_col_index=from_idx,
                to_col_index=to_idx,
                direction="reverse",
            )
            self._relationships.append(fk)
            logger.info(
                f"Imported FK: {fk.from_table}.{fk.from_column} "
                f"-> {fk.to_table}.{fk.to_column}"
            )
        self._invalidate_all_paths()
        self._update_canvas_size()
        self._canvas.queue_draw()

    # =====================================================================
    # Zoom and pan
    # =====================================================================

    def _on_scroll(self, controller, dx, dy):
        state = controller.get_current_event_state()
        if state & Gdk.ModifierType.CONTROL_MASK:
            zoom_step = 0.1
            if dy < 0:
                self._zoom_level = min(self._max_zoom, self._zoom_level + zoom_step)
            else:
                self._zoom_level = max(self._min_zoom, self._zoom_level - zoom_step)
            logger.debug(f"Zoom: {self._zoom_level:.1f}x")
            self._canvas.queue_draw()
            return True
        return False

    def _on_pan_begin(self, gesture, start_x, start_y):
        self._pan_prev_x = 0.0
        self._pan_prev_y = 0.0

    def _on_pan_update(self, gesture, offset_x, offset_y):
        delta_x = offset_x - self._pan_prev_x
        delta_y = offset_y - self._pan_prev_y
        self._pan_prev_x = offset_x
        self._pan_prev_y = offset_y
        self._pan_offset_x += delta_x
        self._pan_offset_y += delta_y
        gesture.set_state(Gtk.EventSequenceState.CLAIMED)
        self._canvas.queue_draw()

    def _on_reset_zoom(self, button):
        self._zoom_level = 1.0
        self._pan_offset_x = 0.0
        self._pan_offset_y = 0.0
        self._canvas.queue_draw()

    # =====================================================================
    # Undo / Redo
    # =====================================================================

    def _save_state(self, action: str = ""):
        state = {
            "action": action,
            "tables": copy.deepcopy(self._tables),
            "relationships": copy.deepcopy(self._relationships),
        }
        self._undo_stack.append(state)
        if len(self._undo_stack) > self._max_history:
            self._undo_stack.pop(0)
        self._redo_stack.clear()

    def _on_undo(self, button):
        if not self._undo_stack:
            return
        self._redo_stack.append(self._get_current_state())
        state = self._undo_stack.pop()
        self._restore_state(state)
        logger.info(f"Undo: {state.get('action', 'unknown')}")

    def _on_redo(self, button):
        if not self._redo_stack:
            return
        self._undo_stack.append(self._get_current_state())
        state = self._redo_stack.pop()
        self._restore_state(state)
        logger.info(f"Redo: {state.get('action', 'unknown')}")

    def _get_current_state(self):
        return {
            "tables": copy.deepcopy(self._tables),
            "relationships": copy.deepcopy(self._relationships),
        }

    def _restore_state(self, state):
        self._tables = state["tables"]
        self._relationships = state["relationships"]
        self._table_index = {t.name: t for t in self._tables}
        self._selected_table = None
        self._invalidate_all_paths()
        self._update_canvas_size()
        self._canvas.queue_draw()

    # =====================================================================
    # Clean up
    # =====================================================================
        
    def _on_close(self):
        """Clean up before the designer is destroyed.
    
        Increment _path_serial so any in-flight worker callbacks
        from the old instance are silently discarded instead of
        crashing on a destroyed canvas.
        """
        self._path_serial += 1000  # Invalidate all pending callbacks
        self._path_pending = False
        if self._path_debounce_id:
            GLib.source_remove(self._path_debounce_id)
            self._path_debounce_id = 0
