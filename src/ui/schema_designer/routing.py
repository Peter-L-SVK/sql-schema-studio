# ----------------------------------------------------------------------
# SQL Schema Studio 0.9 - Schema Designer Routing (GPLv3)
# Copyright (C) 2026 Peter Leukanič
# License: GNU GPL v3+ <https://www.gnu.org/licenses/gpl-3.0.txt>
# This is free software with NO WARRANTY.
# Feel free to distribute and modify.
# ----------------------------------------------------------------------

"""Line routing geometry for the schema designer — collision detection,
detour calculation, and iterative path finding."""

import math


class RoutingMixin:
    """Mixin providing line-routing geometry methods for SchemaDesigner."""

    # These attributes are expected from the main SchemaDesigner class:
    # self._tables, self._relationships, self._table_index

    # =====================================================================
    # Segment intersection tests
    # =====================================================================

    def _segments_intersect(self, x1, y1, x2, y2, x3, y3, x4, y4):
        def ccw(ax, ay, bx, by, cx, cy):
            return (bx - ax) * (cy - ay) - (by - ay) * (cx - ax)

        d1 = ccw(x3, y3, x4, y4, x1, y1)
        d2 = ccw(x3, y3, x4, y4, x2, y2)
        d3 = ccw(x1, y1, x2, y2, x3, y3)
        d4 = ccw(x1, y1, x2, y2, x4, y4)
        if ((d1 > 0 and d2 < 0) or (d1 < 0 and d2 > 0)) and (
            (d3 > 0 and d4 < 0) or (d3 < 0 and d4 > 0)
        ):
            return True
        if d1 == 0 and self._point_on_segment(x3, y3, x4, y4, x1, y1):
            return True
        if d2 == 0 and self._point_on_segment(x3, y3, x4, y4, x2, y2):
            return True
        if d3 == 0 and self._point_on_segment(x1, y1, x2, y2, x3, y3):
            return True
        if d4 == 0 and self._point_on_segment(x1, y1, x2, y2, x4, y4):
            return True
        return False

    def _point_on_segment(self, x1, y1, x2, y2, px, py):
        return min(x1, x2) <= px <= max(x1, x2) and min(y1, y2) <= py <= max(y1, y2)

    def _line_intersects_table(self, x1, y1, x2, y2, table, exclude_tables=None):
        if exclude_tables and table in exclude_tables:
            return False
        w, h = table.get_size()
        margin = 10
        tx = table.x - margin
        ty = table.y - margin
        tw = w + 2 * margin
        th = h + 2 * margin
        if tx <= x1 <= tx + tw and ty <= y1 <= ty + th:
            return True
        if tx <= x2 <= tx + tw and ty <= y2 <= ty + th:
            return True
        edges = [
            (tx, ty, tx + tw, ty),
            (tx + tw, ty, tx + tw, ty + th),
            (tx, ty + th, tx + tw, ty + th),
            (tx, ty, tx, ty + th),
        ]
        for ex1, ey1, ex2, ey2 in edges:
            if self._segments_intersect(x1, y1, x2, y2, ex1, ey1, ex2, ey2):
                return True
        return False

    def _line_intersection(self, x1, y1, x2, y2, x3, y3, x4, y4):
        denom = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
        if abs(denom) < 1e-10:
            return None
        t = ((x1 - x3) * (y3 - y4) - (y1 - y3) * (x3 - x4)) / denom
        u = -((x1 - x2) * (y1 - y3) - (y1 - y2) * (x1 - x3)) / denom
        if 0 <= t <= 1 and 0 <= u <= 1:
            ix = x1 + t * (x2 - x1)
            iy = y1 + t * (y2 - y1)
            return (ix, iy)
        return None

    # =====================================================================
    # Connection point calculation
    # =====================================================================

    def _get_connection_point(self, table, col_index, is_source):
        w, h = table.get_size()
        if col_index is not None:
            col_y = (
                table.y
                + table._header_height
                + col_index * table._row_height
                + table._row_height / 2
            )
            if is_source:
                return (table.x + w, col_y)
            else:
                return (table.x, col_y)
        else:
            if is_source:
                return (table.x + w, table.y + h / 2)
            else:
                return (table.x, table.y + h / 2)

    # =====================================================================
    # Rectangle side detection
    # =====================================================================

    def _get_rect_side(self, px, py, rx, ry, rw, rh):
        dist_left = abs(px - rx)
        dist_right = abs(px - (rx + rw))
        dist_top = abs(py - ry)
        dist_bottom = abs(py - (ry + rh))
        min_dist = min(dist_left, dist_right, dist_top, dist_bottom)
        if min_dist == dist_left:
            return "left"
        elif min_dist == dist_right:
            return "right"
        elif min_dist == dist_top:
            return "top"
        else:
            return "bottom"

    # =====================================================================
    # Entry/exit point detection
    # =====================================================================

    def _find_entry_exit_points(self, x1, y1, x2, y2, table):
        w, h = table.get_size()
        margin = 8
        tx = table.x - margin
        ty = table.y - margin
        tw = w + 2 * margin
        th = h + 2 * margin
        edges = [
            (tx, ty, tx + tw, ty),
            (tx + tw, ty, tx + tw, ty + th),
            (tx, ty + th, tx + tw, ty + th),
            (tx, ty, tx, ty + th),
        ]
        intersections = []
        for ex1, ey1, ex2, ey2 in edges:
            result = self._line_intersection(x1, y1, x2, y2, ex1, ey1, ex2, ey2)
            if result is not None:
                ix, iy = result
                intersections.append((ix, iy))
        if len(intersections) < 2:
            if tx <= x1 <= tx + tw and ty <= y1 <= ty + th:
                if intersections:
                    return ((x1, y1), intersections[0])
            if tx <= x2 <= tx + tw and ty <= y2 <= ty + th:
                if intersections:
                    return (intersections[-1], (x2, y2))
            return (None, None)
        intersections.sort(key=lambda p: (p[0] - x1) ** 2 + (p[1] - y1) ** 2)
        return (intersections[0], intersections[-1])

    # =====================================================================
    # Detour calculation
    # =====================================================================

    def _calculate_detour_around_table(self, x1, y1, x2, y2, table):
        """Calculate minimal orthogonal detour around a table obstacle."""
        w, h = table.get_size()
        margin = 25

        tx = table.x - margin
        ty = table.y - margin
        tw = w + 2 * margin
        th = h + 2 * margin

        corners = {
            "tl": (tx, ty),
            "tr": (tx + tw, ty),
            "bl": (tx, ty + th),
            "br": (tx + tw, ty + th),
        }

        dx = x2 - x1
        dy = y2 - y1

        if dx >= 0 and dy >= 0:
            corner = corners["tr"]
        elif dx >= 0 and dy < 0:
            corner = corners["br"]
        elif dx < 0 and dy >= 0:
            corner = corners["tl"]
        else:
            corner = corners["bl"]

        corner_x, corner_y = corner

        if abs(dx) > abs(dy):
            path = [
                (x1, y1),
                (x1, corner_y),
                (corner_x, corner_y),
                (x2, corner_y),
                (x2, y2),
            ]
        else:
            path = [
                (x1, y1),
                (corner_x, y1),
                (corner_x, corner_y),
                (corner_x, y2),
                (x2, y2),
            ]

        return path

    # =====================================================================
    # Main path calculation
    # =====================================================================

    def _calculate_line_path(self, fk, source_table, target_table):
        """Calculate a clean path that avoids all obstacle tables iteratively."""
        start_x, start_y = self._get_connection_point(
            source_table, fk.from_col_index, is_source=True
        )
        end_x, end_y = self._get_connection_point(target_table, fk.to_col_index, is_source=False)

        points = [(start_x, start_y)]
        points.extend(fk.waypoints)
        points.append((end_x, end_y))

        max_iterations = 30
        for _ in range(max_iterations):
            collision_found = False
            new_points = [points[0]]

            for i in range(len(points) - 1):
                x1, y1 = points[i]
                x2, y2 = points[i + 1]

                collision_table = None
                for table in self._tables:
                    if table.name in (fk.from_table, fk.to_table):
                        continue
                    if self._line_intersects_table(x1, y1, x2, y2, table):
                        collision_table = table
                        break

                if collision_table:
                    detour_points = self._calculate_detour_around_table(
                        x1, y1, x2, y2, collision_table
                    )
                    if detour_points and len(detour_points) >= 2:
                        for px, py in detour_points[1:]:
                            new_points.append((px, py))
                        collision_found = True
                    else:
                        new_points.append((x2, y2))
                else:
                    new_points.append((x2, y2))

            deduped = []
            for p in new_points:
                if not deduped:
                    deduped.append(p)
                else:
                    last = deduped[-1]
                    if abs(p[0] - last[0]) > 2 or abs(p[1] - last[1]) > 2:
                        deduped.append(p)

            points = deduped

            # Re-check ALL segments against ALL tables
            still_intersects = False
            for i in range(len(points) - 1):
                x1, y1 = points[i]
                x2, y2 = points[i + 1]
                for table in self._tables:
                    if table.name in (fk.from_table, fk.to_table):
                        continue
                    if self._line_intersects_table(x1, y1, x2, y2, table):
                        still_intersects = True
                        break
                if still_intersects:
                    break

            if not still_intersects:
                break

        return points
