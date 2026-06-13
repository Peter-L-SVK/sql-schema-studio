# ----------------------------------------------------------------------
# SQL Schema Studio 0.9 - Schema Designer Drawing (GPLv3)
# Copyright (C) 2026 Peter Leukanič
# License: GNU GPL v3+ <https://www.gnu.org/licenses/gpl-3.0.txt>
# This is free software with NO WARRANTY.
# Feel free to distribute and modify.
# ----------------------------------------------------------------------

"""Drawing routines for the schema designer — tables, relationships,
line jumps, and arrowheads."""

import cairo
import math

from src.config import SCHEMA_CANVAS_BG


class DrawingMixin:
    """Mixin providing drawing methods for SchemaDesigner."""

    # Expected from the main class:
    # self._tables, self._relationships, self._table_index,
    # self._canvas, self._pan_offset_x, self._pan_offset_y, self._zoom_level,
    # self._creating_relationship

    # =====================================================================
    # Main draw callback
    # =====================================================================

    def _on_draw(self, area, cr, width, height):
        cr.save()
        cr.translate(self._pan_offset_x, self._pan_offset_y)
        cr.scale(self._zoom_level, self._zoom_level)
        cr.set_source_rgb(*SCHEMA_CANVAS_BG)
        cr.paint()
        for fk in self._relationships:
            self._draw_relationship(cr, fk)
        if self._creating_relationship:
            table, col = self._creating_relationship
            src_x = table.x + table.get_size()[0] / 2
            src_y = table.y + table.get_size()[1]
            cr.set_source_rgb(0.8, 0.3, 0.3)
            cr.set_dash([5, 5])
            cr.set_line_width(1.5)
            cr.move_to(src_x, src_y)
            cr.line_to(src_x, src_y + 50)
            cr.stroke()
            cr.set_dash([])
        for table in self._tables:
            self._draw_table(cr, table)
        cr.restore()

    # =====================================================================
    # Relationship drawing
    # =====================================================================

    def _draw_relationship(self, cr, fk):
        """Draw a relationship line with waypoint support and line jumps."""
        source_table = self._table_index.get(fk.from_table)
        target_table = self._table_index.get(fk.to_table)

        if not source_table or not target_table:
            return

        # Use cached path if available, otherwise draw straight fallback
        # WITHOUT storing it (worker pool will compute the real path).
        path = fk._cached_path
        if not path or len(path) < 2:
            # Straight fallback — draw only, don't cache
            src_w, src_h = source_table.get_size()
            tgt_w, tgt_h = target_table.get_size()
            x1 = source_table.x + src_w
            y1 = source_table.y + src_h / 2
            x2 = target_table.x
            y2 = target_table.y + tgt_h / 2
            cr.set_source_rgb(*fk.color)
            cr.set_line_width(2)
            self._draw_segment_styled(cr, x1, y1, x2, y2, fk.line_style)
            self._draw_arrowhead_direct(cr, fk, x1, y1, x2, y2)
            return

        intersections = self._find_line_intersections(fk)

        cr.set_source_rgb(*fk.color)
        cr.set_line_width(2)

        for i in range(len(path) - 1):
            x1, y1 = path[i]
            x2, y2 = path[i + 1]
            segment_angle = math.atan2(y2 - y1, x2 - x1)

            seg_intersections = []
            for ix, iy, other_fk in intersections:
                if self._point_on_segment(x1, y1, x2, y2, ix, iy):
                    dist = math.sqrt((ix - x1) ** 2 + (iy - y1) ** 2)
                    seg_intersections.append((dist, ix, iy))

            seg_intersections.sort(key=lambda item: item[0])

            if not seg_intersections:
                self._draw_segment_styled(cr, x1, y1, x2, y2, fk.line_style)
            else:
                prev_x, prev_y = x1, y1
                for _, ix, iy in seg_intersections:
                    pre_x = ix - 7 * math.cos(segment_angle)
                    pre_y = iy - 7 * math.sin(segment_angle)

                    self._draw_segment_styled(cr, prev_x, prev_y, pre_x, pre_y, fk.line_style)
                    self._draw_line_jump(cr, ix, iy, segment_angle, fk.color)

                    prev_x = ix + 7 * math.cos(segment_angle)
                    prev_y = iy + 7 * math.sin(segment_angle)

                self._draw_segment_styled(cr, prev_x, prev_y, x2, y2, fk.line_style)

        if len(path) >= 2:
            self._draw_arrowhead_on_path(cr, fk)

        for wx, wy in fk.waypoints:
            cr.set_source_rgb(0.8, 0.2, 0.2)
            cr.arc(wx, wy, 5, 0, 2 * math.pi)
            cr.fill()
            cr.set_source_rgb(1, 1, 1)
            cr.arc(wx, wy, 2.5, 0, 2 * math.pi)
            cr.fill()

    def _draw_segment_styled(self, cr, x1, y1, x2, y2, line_style):
        """Draw a single path segment using the FK line style."""
        seg_length = math.hypot(x2 - x1, y2 - y1)

        cr.set_line_width(2.0)
        cr.move_to(x1, y1)

        if line_style == "curve" and seg_length > 20:
            ctrl = max(abs(x2 - x1) * 0.5, 40)
            cr.curve_to(x1 + ctrl, y1, x2 - ctrl, y2, x2, y2)
        elif line_style == "ortho" and seg_length > 20:
            mid_x = (x1 + x2) / 2
            cr.line_to(mid_x, y1)
            cr.line_to(mid_x, y2)
            cr.line_to(x2, y2)
        else:
            cr.line_to(x2, y2)

        cr.stroke()

    # =====================================================================
    # Line jumps
    # =====================================================================

    def _find_line_intersections(self, current_fk):
        """Find all intersections between current_fk and other relationship lines."""
        intersections = []
        if not current_fk._cached_path or len(current_fk._cached_path) < 2:
            return intersections

        current_segments = []
        path = current_fk._cached_path
        for i in range(len(path) - 1):
            current_segments.append((path[i][0], path[i][1], path[i+1][0], path[i+1][1]))

        for other_fk in self._relationships:
            if other_fk is current_fk:
                continue
            other_path = other_fk._cached_path
            if not other_path or len(other_path) < 2:
                continue
            other_segments = []
            for i in range(len(other_path) - 1):
                other_segments.append((other_path[i][0], other_path[i][1],
                                       other_path[i+1][0], other_path[i+1][1]))
            for seg1 in current_segments:
                for seg2 in other_segments:
                    result = self._line_intersection(
                        seg1[0], seg1[1], seg1[2], seg1[3],
                        seg2[0], seg2[1], seg2[2], seg2[3]
                    )
                    if result is not None:
                        ix, iy = result
                        is_endpoint = False
                        for table in self._tables:
                            tw, th = table.get_size()
                            if (abs(ix - table.x) < 15 or abs(ix - (table.x + tw)) < 15) and \
                               (table.y - 15 <= iy <= table.y + th + 15):
                                is_endpoint = True
                                break
                            if (abs(iy - table.y) < 15 or abs(iy - (table.y + th)) < 15) and \
                               (table.x - 15 <= ix <= table.x + tw + 15):
                                is_endpoint = True
                                break
                        if not is_endpoint:
                            intersections.append((ix, iy, other_fk))
        return intersections

    def _draw_line_jump(self, cr, ix, iy, angle, line_color):
        """Draw a bridge arc over an intersecting line."""
        jump_radius = 7

        cr.set_source_rgb(*SCHEMA_CANVAS_BG)
        cr.arc(ix, iy, jump_radius + 1, 0, 2 * math.pi)
        cr.fill()

        cr.set_source_rgb(*line_color)
        cr.set_line_width(2.0)
        cr.arc_negative(ix, iy, jump_radius, angle, angle + math.pi)
        cr.stroke()

    # =====================================================================
    # Arrowheads
    # =====================================================================

    def _draw_arrowhead_on_path(self, cr, fk):
        """Draw arrowhead on the last segment and labels near the tables."""
        if len(fk._cached_path) < 2:
            return

        source_table = self._table_index.get(fk.from_table)
        target_table = self._table_index.get(fk.to_table)
    
        if not source_table or not target_table:
            return
    
        # Arrowhead on last segment
        x1, y1 = fk._cached_path[-2]
        x2, y2 = fk._cached_path[-1]

        arrow_size = 10
        cr.set_source_rgb(*fk.color)
        cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        cr.set_font_size(10)

        if fk.direction == "forward":
            angle = math.atan2(y2 - y1, x2 - x1)
            cr.move_to(x2, y2)
            cr.line_to(
                x2 - arrow_size * math.cos(angle - 0.4),
                y2 - arrow_size * math.sin(angle - 0.4),
            )
            cr.line_to(
                x2 - arrow_size * math.cos(angle + 0.4),
                y2 - arrow_size * math.sin(angle + 0.4),
            )
            cr.close_path()
            cr.fill()
        else:
            angle = math.atan2(y1 - y2, x1 - x2)
            cr.move_to(x1, y1)
            cr.line_to(
                x1 - arrow_size * math.cos(angle - 0.4),
                y1 - arrow_size * math.sin(angle - 0.4),
            )
            cr.line_to(
                x1 - arrow_size * math.cos(angle + 0.4),
                y1 - arrow_size * math.sin(angle + 0.4),
            )
            cr.close_path()
            cr.fill()

        # Labels — always near the tables
        src_w, src_h = source_table.get_size()
        tgt_w, tgt_h = target_table.get_size()

        # "N" near from_table (child) — right edge
        cr.move_to(source_table.x + src_w + 4, source_table.y + src_h / 2 - 10)
        cr.show_text("N")

        # "1" near to_table (parent) — left edge
        cr.move_to(target_table.x - 20, target_table.y + tgt_h / 2 - 10)
        cr.show_text("1")

    def _draw_arrowhead_direct(self, cr, fk, x1, y1, x2, y2):
        """Draw arrowhead directly between two points (fallback)."""
        source_table = self._table_index.get(fk.from_table)
        target_table = self._table_index.get(fk.to_table)
    
        if not source_table or not target_table:
            return
    
        arrow_size = 10
        cr.set_source_rgb(*fk.color)
        cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        cr.set_font_size(10)

        if fk.direction == "forward":
            angle = math.atan2(y2 - y1, x2 - x1)
            cr.move_to(x2, y2)
            cr.line_to(
                x2 - arrow_size * math.cos(angle - 0.4),
                y2 - arrow_size * math.sin(angle - 0.4),
            )
            cr.line_to(
                x2 - arrow_size * math.cos(angle + 0.4),
                y2 - arrow_size * math.sin(angle + 0.4),
            )
            cr.close_path()
            cr.fill()
        else:
            angle = math.atan2(y1 - y2, x1 - x2)
            cr.move_to(x1, y1)
            cr.line_to(
                x1 - arrow_size * math.cos(angle - 0.4),
                y1 - arrow_size * math.sin(angle - 0.4),
            )
            cr.line_to(
                x1 - arrow_size * math.cos(angle + 0.4),
                y1 - arrow_size * math.sin(angle + 0.4),
            )
            cr.close_path()
            cr.fill()

        # Labels — always near the tables
        src_w, src_h = source_table.get_size()
        tgt_w, tgt_h = target_table.get_size()

        # "N" near from_table (child) — right edge
        cr.move_to(source_table.x + src_w + 4, source_table.y + src_h / 2 - 10)
        cr.show_text("N")

        # "1" near to_table (parent) — left edge
        cr.move_to(target_table.x - 20, target_table.y + tgt_h / 2 - 10)
        cr.show_text("1")

    # =====================================================================
    # Table drawing
    # =====================================================================

    def _draw_table(self, cr, table):
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
        line_height = table._row_height
        header_height = table._header_height
        body_padding = table._body_padding
        body_height = len(col_lines) * line_height + body_padding
        total_height = header_height + body_height
        total_width = max(max_line * 8, table._width)
        cr.set_source_rgba(0, 0, 0, 0.15)
        cr.rectangle(table.x + 3, table.y + 3, total_width, total_height)
        cr.fill()
        cr.set_source_rgb(1, 1, 1)
        cr.rectangle(table.x, table.y, total_width, total_height)
        cr.fill()
        cr.set_source_rgb(*table.color)
        cr.rectangle(table.x, table.y, total_width, header_height)
        cr.fill()
        cr.set_source_rgb(0.2, 0.3, 0.5)
        cr.rectangle(table.x, table.y, total_width, header_height)
        cr.set_line_width(1)
        cr.stroke()
        cr.set_source_rgb(
            table.color[0] * 0.5, table.color[1] * 0.5, table.color[2] * 0.5
        )
        cr.rectangle(table.x, table.y, total_width, total_height)
        cr.set_line_width(1)
        cr.stroke()
        cr.set_source_rgb(0.4, 0.5, 0.6)
        cr.move_to(table.x, table.y + header_height)
        cr.line_to(table.x + total_width, table.y + header_height)
        cr.stroke()
        cr.set_source_rgb(1, 1, 1)
        cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        cr.set_font_size(13)
        cr.move_to(table.x + 6, table.y + header_height - 6)
        cr.show_text(table.name)
        cr.set_source_rgba(0.7, 0.7, 0.7, 0.4)
        cr.set_line_width(0.5)
        for i in range(1, len(col_lines)):
            sep_y = table.y + header_height + i * line_height
            cr.move_to(table.x + 4, sep_y)
            cr.line_to(table.x + total_width - 4, sep_y)
            cr.stroke()
        cr.set_source_rgb(0.1, 0.1, 0.1)
        cr.select_font_face(
            "Monospace", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL
        )
        cr.set_font_size(11)
        y_pos = table.y + header_height + line_height - 4
        for i, line in enumerate(col_lines):
            text = col_lines[i].strip()
            cr.move_to(table.x + 8, y_pos)
            cr.show_text(text)
            y_pos += line_height
        if table == self._selected_table:
            cr.set_source_rgb(*table.color)
            cr.set_line_width(2)
            cr.rectangle(
                table.x - 2, table.y - 2, total_width + 4, total_height + 4
            )
            cr.stroke()
