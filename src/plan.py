from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Dict, List, Tuple

from shapely.geometry import Polygon

Point2D = Tuple[float, float]

WING_EDGE_INDICES: Dict[str, Tuple[int, int]] = {
    "A": (5, 0),  # front-right
    "B": (3, 4),  # front-left
    "C": (1, 2),  # back (double-height)
}

TRIANGLE_EDGE_INDICES: Tuple[Tuple[int, int], ...] = (
    (1, 2),
    (3, 4),
    (5, 0),  # rotated 120° to align points between wing axes
)


@dataclass
class PlanGeometry:
    hex_vertices: List[Point2D]
    extension_vertices: List[Point2D]
    wing_polygons: Dict[str, List[Point2D]]
    master_triangle: List[Point2D]
    atrium_front_edge: Tuple[Point2D, Point2D]
    courtyard_polygon: List[Point2D]
    side_courtyard_right: List[Point2D] = None  # between Wing A and C
    side_courtyard_left: List[Point2D] = None   # between Wing B and C

    @property
    def atrium_polygon(self) -> Polygon:
        return Polygon(self.hex_vertices)


def _polygon_area(points: List[Point2D]) -> float:
    area = 0.0
    for i, (x0, y0) in enumerate(points):
        x1, y1 = points[(i + 1) % len(points)]
        area += x0 * y1 - x1 * y0
    return area * 0.5


def _ensure_ccw(points: List[Point2D]) -> List[Point2D]:
    if _polygon_area(points) < 0:
        return list(reversed(points))
    return points


def _unit(vx: float, vy: float) -> Point2D:
    mag = math.hypot(vx, vy)
    if mag == 0:
        raise ValueError("Zero-length vector.")
    return vx / mag, vy / mag


def _offset_edge_line(
    p0: Point2D,
    p1: Point2D,
    center: Point2D,
    offset: float,
) -> Tuple[Point2D, Point2D]:
    ex, ey = p1[0] - p0[0], p1[1] - p0[1]
    midpoint = ((p0[0] + p1[0]) * 0.5, (p0[1] + p1[1]) * 0.5)
    to_mid = (midpoint[0] - center[0], midpoint[1] - center[1])

    n1 = (ey, -ex)
    n2 = (-ey, ex)
    n1u = _unit(*n1)
    n2u = _unit(*n2)
    use = n1u if (n1u[0] * to_mid[0] + n1u[1] * to_mid[1]) > (n2u[0] * to_mid[0] + n2u[1] * to_mid[1]) else n2u

    ox, oy = use[0] * offset, use[1] * offset
    return (p0[0] + ox, p0[1] + oy), (p1[0] + ox, p1[1] + oy)


def _line_intersection(a0: Point2D, a1: Point2D, b0: Point2D, b1: Point2D) -> Point2D:
    x1, y1 = a0
    x2, y2 = a1
    x3, y3 = b0
    x4, y4 = b1
    den = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
    if abs(den) < 1e-12:
        raise ValueError("Parallel lines encountered while building master triangle.")

    det_a = x1 * y2 - y1 * x2
    det_b = x3 * y4 - y3 * x4
    px = (det_a * (x3 - x4) - (x1 - x2) * det_b) / den
    py = (det_a * (y3 - y4) - (y1 - y2) * det_b) / den
    return px, py


def _rotate_point(point: Point2D, center: Point2D, angle_rad: float) -> Point2D:
    px, py = point[0] - center[0], point[1] - center[1]
    c, s = math.cos(angle_rad), math.sin(angle_rad)
    return center[0] + c * px - s * py, center[1] + s * px + c * py


def _distance_point_to_line(point: Point2D, line_a: Point2D, line_b: Point2D) -> float:
    ux, uy = line_b[0] - line_a[0], line_b[1] - line_a[1]
    vx, vy = point[0] - line_a[0], point[1] - line_a[1]
    den = max(math.hypot(ux, uy), 1e-12)
    return abs((ux * vy - uy * vx) / den)


def make_shared_front_edge_courtyard(
    atrium_front_edge: Tuple[Point2D, Point2D],
    master_triangle: List[Point2D],
) -> List[Point2D]:
    atrium_left, atrium_right = sorted(atrium_front_edge, key=lambda p: p[0])
    front_pair = sorted(sorted(master_triangle, key=lambda p: p[1])[:2], key=lambda p: p[0])
    tri_left, tri_right = front_pair
    return _ensure_ccw([atrium_left, atrium_right, tri_right, tri_left])


def make_exterior_hex_courtyard(s: float) -> List[Point2D]:
    center = (0.0, -math.sqrt(3.0) * s)
    points: List[Point2D] = []
    for i in range(6):
        angle = math.radians(i * 60.0)
        points.append((center[0] + s * math.cos(angle), center[1] + s * math.sin(angle)))
    return _ensure_ccw(points)


def make_side_courtyard_hex(s: float, side: str) -> List[Point2D]:
    """Create a hexagonal courtyard between wing pairs.

    side='right' for between Wing A and C (edge 0→1 direction).
    side='left' for between Wing B and C (edge 2→3 direction).
    """
    sqrt3 = math.sqrt(3.0)
    if side == "right":
        # Between A and C: direction of edge 0→1 midpoint (30° from center)
        cx = 1.5 * s
        cy = sqrt3 * s * 0.5
    else:
        # Between B and C: direction of edge 2→3 midpoint (150° from center)
        cx = -1.5 * s
        cy = sqrt3 * s * 0.5
    points: List[Point2D] = []
    for i in range(6):
        angle = math.radians(i * 60.0)
        points.append((cx + s * math.cos(angle), cy + s * math.sin(angle)))
    return _ensure_ccw(points)


def build_plan(config: Dict[str, float]) -> PlanGeometry:
    s = float(config["s"])
    d = float(config["d"])
    center: Point2D = (0.0, 0.0)

    hex_vertices: List[Point2D] = []
    for i in range(6):
        angle = math.radians(i * 60.0)
        hex_vertices.append((s * math.cos(angle), s * math.sin(angle)))
    hex_vertices = _ensure_ccw(hex_vertices)

    extension_vertices: List[Point2D] = []
    for vx, vy in hex_vertices:
        ux, uy = _unit(vx - center[0], vy - center[1])
        extension_vertices.append((vx + ux * s, vy + uy * s))

    wing_polygons: Dict[str, List[Point2D]] = {}
    for wing_name, (i0, i1) in WING_EDGE_INDICES.items():
        wing_polygons[wing_name] = _ensure_ccw(
            [
                hex_vertices[i0],
                hex_vertices[i1],
                extension_vertices[i1],
                extension_vertices[i0],
            ]
        )

    offset_lines = []
    for i0, i1 in TRIANGLE_EDGE_INDICES:
        offset_lines.append(_offset_edge_line(hex_vertices[i0], hex_vertices[i1], center, d))

    top = _line_intersection(offset_lines[0][0], offset_lines[0][1], offset_lines[1][0], offset_lines[1][1])
    left = _line_intersection(offset_lines[1][0], offset_lines[1][1], offset_lines[2][0], offset_lines[2][1])
    right = _line_intersection(offset_lines[2][0], offset_lines[2][1], offset_lines[0][0], offset_lines[0][1])
    master_triangle = _ensure_ccw([right, top, left])
    tri_center = (
        sum(p[0] for p in master_triangle) / 3.0,
        sum(p[1] for p in master_triangle) / 3.0,
    )
    back_edge_idx = max(range(3), key=lambda i: (master_triangle[i][1] + master_triangle[(i + 1) % 3][1]) * 0.5)
    back_a = master_triangle[back_edge_idx]
    back_b = master_triangle[(back_edge_idx + 1) % 3]
    wing_c_top_right = extension_vertices[1]
    step = (2.0 * math.pi) / 7200.0
    best_angle = 0.0
    best_dist = float("inf")
    for k in range(1, 7201):
        angle = k * step
        ra = _rotate_point(back_a, tri_center, angle)
        rb = _rotate_point(back_b, tri_center, angle)
        dist = _distance_point_to_line(wing_c_top_right, ra, rb)
        if dist < best_dist:
            best_dist = dist
            best_angle = angle
        if dist <= 1e-3:
            best_angle = angle
            break
    lo = max(0.0, best_angle - step)
    hi = best_angle + step
    for _ in range(40):
        m1 = lo + (hi - lo) / 3.0
        m2 = hi - (hi - lo) / 3.0
        d1 = _distance_point_to_line(
            wing_c_top_right,
            _rotate_point(back_a, tri_center, m1),
            _rotate_point(back_b, tri_center, m1),
        )
        d2 = _distance_point_to_line(
            wing_c_top_right,
            _rotate_point(back_a, tri_center, m2),
            _rotate_point(back_b, tri_center, m2),
        )
        if d1 <= d2:
            hi = m2
        else:
            lo = m1
    best_angle = (lo + hi) * 0.5
    clockwise_backoff_deg = float(config.get("triangle_clockwise_backoff_deg", 0.0))
    best_angle -= math.radians(clockwise_backoff_deg)
    master_triangle = _ensure_ccw([_rotate_point(p, tri_center, best_angle) for p in master_triangle])
    down_shift = float(config.get("triangle_plan_down_shift_ft", 0.0))
    if abs(down_shift) > 1e-9:
        master_triangle = [(p[0], p[1] - down_shift) for p in master_triangle]
        master_triangle = _ensure_ccw(master_triangle)

    atrium_front_edge = (hex_vertices[4], hex_vertices[5])
    courtyard_module_name = str(config.get("courtyard_module", "none"))
    if courtyard_module_name == "none":
        courtyard_polygon: List[Point2D] = []
    elif courtyard_module_name == "shared_front_edge":
        courtyard_polygon = make_shared_front_edge_courtyard(atrium_front_edge, master_triangle)
    elif courtyard_module_name == "exterior_hex":
        courtyard_polygon = make_exterior_hex_courtyard(s)
    else:
        raise ValueError(f"Unknown courtyard module: {courtyard_module_name}")

    # Side courtyards between wing pairs
    side_courtyard_right = make_side_courtyard_hex(s, "right")
    side_courtyard_left = make_side_courtyard_hex(s, "left")

    return PlanGeometry(
        hex_vertices=hex_vertices,
        extension_vertices=extension_vertices,
        wing_polygons=wing_polygons,
        master_triangle=master_triangle,
        atrium_front_edge=atrium_front_edge,
        courtyard_polygon=courtyard_polygon,
        side_courtyard_right=side_courtyard_right,
        side_courtyard_left=side_courtyard_left,
    )

