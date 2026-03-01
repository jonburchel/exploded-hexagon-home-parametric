from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
import math
from typing import Callable, Dict, Iterable, List, Tuple

from shapely.geometry import GeometryCollection, LineString, MultiPolygon, Point, Polygon
from shapely.ops import triangulate, unary_union

from .plan import PlanGeometry, WING_EDGE_INDICES

Point2D = Tuple[float, float]
Point3D = Tuple[float, float, float]
Triangle3D = Tuple[Point3D, Point3D, Point3D]


@dataclass
class ModelData:
    triangles_by_material: Dict[str, List[Triangle3D]] = field(default_factory=lambda: defaultdict(list))
    triangles_by_component: Dict[str, Dict[str, List[Triangle3D]]] = field(
        default_factory=lambda: defaultdict(lambda: defaultdict(list))
    )

    def add_triangle(self, material: str, tri: Triangle3D, component: str = "model") -> None:
        self.triangles_by_material[material].append(tri)
        self.triangles_by_component[component][material].append(tri)


def _triangle_normal(tri: Triangle3D) -> Point3D:
    a, b, c = tri
    ux, uy, uz = b[0] - a[0], b[1] - a[1], b[2] - a[2]
    vx, vy, vz = c[0] - a[0], c[1] - a[1], c[2] - a[2]
    nx = uy * vz - uz * vy
    ny = uz * vx - ux * vz
    nz = ux * vy - uy * vx
    mag = math.sqrt(nx * nx + ny * ny + nz * nz)
    if mag == 0:
        return (0.0, 0.0, 1.0)
    return nx / mag, ny / mag, nz / mag


def _iter_polygons(geometry) -> Iterable[Polygon]:
    if geometry.is_empty:
        return []
    if isinstance(geometry, Polygon):
        return [geometry]
    if isinstance(geometry, MultiPolygon):
        return list(geometry.geoms)
    if isinstance(geometry, GeometryCollection):
        return [geom for geom in geometry.geoms if isinstance(geom, Polygon)]
    raise TypeError(f"Unsupported geometry type: {geometry.geom_type}")


def _triangles_for_polygon(poly: Polygon) -> List[Tuple[Point2D, Point2D, Point2D]]:
    tris = []
    for tri in triangulate(poly):
        if not poly.covers(tri.representative_point()):
            continue
        coords = list(tri.exterior.coords)[:-1]
        if len(coords) != 3:
            continue
        tris.append((coords[0], coords[1], coords[2]))
    return tris


def _signed_area_2d(points: List[Point2D]) -> float:
    area = 0.0
    for i, (x0, y0) in enumerate(points):
        x1, y1 = points[(i + 1) % len(points)]
        area += x0 * y1 - x1 * y0
    return area * 0.5


def _add_polygon_cap(
    mesh: ModelData,
    material: str,
    poly: Polygon,
    z: float,
    up: bool,
    component: str = "model",
) -> None:
    for tri in _triangles_for_polygon(poly):
        tri_pts = [tri[0], tri[1], tri[2]]
        if _signed_area_2d(tri_pts) < 0:
            tri_pts.reverse()

        tri3d: Triangle3D = (
            (tri_pts[0][0], tri_pts[0][1], z),
            (tri_pts[1][0], tri_pts[1][1], z),
            (tri_pts[2][0], tri_pts[2][1], z),
        )
        if not up:
            tri3d = (tri3d[0], tri3d[2], tri3d[1])
        mesh.add_triangle(material, tri3d, component=component)


def _add_solid_wall_edge(
    mesh: ModelData,
    material: str,
    p0: Point2D,
    p1: Point2D,
    z0: float,
    z1: float,
    wall_thickness: float,
    interior_test_polygon: Polygon,
    component: str = "model",
) -> None:
    """Create a solid wall box for a single edge with real thickness."""
    edge_dx = p1[0] - p0[0]
    edge_dy = p1[1] - p0[1]
    edge_len = math.hypot(edge_dx, edge_dy)
    if edge_len < 1e-9:
        return

    # Perpendicular unit normal
    nx = -edge_dy / edge_len
    ny = edge_dx / edge_len

    # Determine outward direction using interior test
    mx = (p0[0] + p1[0]) * 0.5
    my = (p0[1] + p1[1]) * 0.5
    probe = Point(mx + nx * 0.05, my + ny * 0.05)
    if interior_test_polygon.covers(probe):
        nx, ny = -nx, -ny  # flip so (nx, ny) points outward

    half_t = wall_thickness / 2.0

    # Outer vertices (offset outward)
    o0 = (p0[0] + nx * half_t, p0[1] + ny * half_t)
    o1 = (p1[0] + nx * half_t, p1[1] + ny * half_t)
    # Inner vertices (offset inward)
    i0 = (p0[0] - nx * half_t, p0[1] - ny * half_t)
    i1 = (p1[0] - nx * half_t, p1[1] - ny * half_t)

    def _quad(a: Point3D, b: Point3D, c: Point3D, d: Point3D, out: Point3D) -> None:
        """Add a quad (a,b,c,d) with normals facing toward 'out' direction."""
        t1: Triangle3D = (a, b, c)
        t2: Triangle3D = (a, c, d)
        n = _triangle_normal(t1)
        # Check if normal points toward out direction
        dot = n[0] * out[0] + n[1] * out[1] + n[2] * out[2]
        if dot < 0:
            t1 = (t1[0], t1[2], t1[1])
            t2 = (t2[0], t2[2], t2[1])
        mesh.add_triangle(material, t1, component=component)
        mesh.add_triangle(material, t2, component=component)

    # Outer face (normal points outward)
    _quad((o0[0], o0[1], z0), (o1[0], o1[1], z0),
          (o1[0], o1[1], z1), (o0[0], o0[1], z1),
          (nx, ny, 0.0))

    # Inner face (normal points inward)
    _quad((i1[0], i1[1], z0), (i0[0], i0[1], z0),
          (i0[0], i0[1], z1), (i1[0], i1[1], z1),
          (-nx, -ny, 0.0))

    # Top cap (normal points up)
    _quad((o0[0], o0[1], z1), (o1[0], o1[1], z1),
          (i1[0], i1[1], z1), (i0[0], i0[1], z1),
          (0.0, 0.0, 1.0))

    # Bottom cap (normal points down)
    _quad((i0[0], i0[1], z0), (i1[0], i1[1], z0),
          (o1[0], o1[1], z0), (o0[0], o0[1], z0),
          (0.0, 0.0, -1.0))

    # Left end cap (at p0, normal along -edge direction)
    edge_ux = edge_dx / edge_len
    edge_uy = edge_dy / edge_len
    _quad((o0[0], o0[1], z0), (o0[0], o0[1], z1),
          (i0[0], i0[1], z1), (i0[0], i0[1], z0),
          (-edge_ux, -edge_uy, 0.0))

    # Right end cap (at p1, normal along +edge direction)
    _quad((i1[0], i1[1], z0), (i1[0], i1[1], z1),
          (o1[0], o1[1], z1), (o1[0], o1[1], z0),
          (edge_ux, edge_uy, 0.0))


def _add_wall_band_ring(
    mesh: ModelData,
    material: str,
    ring_coords: List[Point2D],
    z0: float,
    z1: float,
    interior_test_polygon: Polygon,
    component: str = "model",
    skip_edges: List[Tuple[Point2D, Point2D]] | None = None,
    wall_thickness: float = 0.0,
) -> None:
    pts = ring_coords[:-1] if ring_coords and ring_coords[0] == ring_coords[-1] else ring_coords
    if len(pts) < 2 or z1 <= z0:
        return

    for i in range(len(pts)):
        p0 = pts[i]
        p1 = pts[(i + 1) % len(pts)]

        # Check if this edge should be skipped (open connection)
        if skip_edges:
            skip = False
            for se0, se1 in skip_edges:
                d0a = math.hypot(p0[0] - se0[0], p0[1] - se0[1])
                d0b = math.hypot(p0[0] - se1[0], p0[1] - se1[1])
                d1a = math.hypot(p1[0] - se0[0], p1[1] - se0[1])
                d1b = math.hypot(p1[0] - se1[0], p1[1] - se1[1])
                if (d0a < 1e-3 and d1b < 1e-3) or (d0b < 1e-3 and d1a < 1e-3):
                    skip = True
                    break
            if skip:
                continue

        if wall_thickness > 0:
            _add_solid_wall_edge(mesh, material, p0, p1, z0, z1,
                                wall_thickness, interior_test_polygon, component)
        else:
            tri1: Triangle3D = ((p0[0], p0[1], z0), (p1[0], p1[1], z0), (p1[0], p1[1], z1))
            tri2: Triangle3D = ((p0[0], p0[1], z0), (p1[0], p1[1], z1), (p0[0], p0[1], z1))

            nx, ny, _ = _triangle_normal(tri1)
            if abs(nx) + abs(ny) > 1e-9:
                mx = (p0[0] + p1[0]) * 0.5
                my = (p0[1] + p1[1]) * 0.5
                probe = Point(mx + nx * 0.05, my + ny * 0.05)
                if interior_test_polygon.covers(probe):
                    tri1 = (tri1[0], tri1[2], tri1[1])
                    tri2 = (tri2[0], tri2[2], tri2[1])

            mesh.add_triangle(material, tri1, component=component)
            mesh.add_triangle(material, tri2, component=component)


def _add_vertical_walls_for_polygon(
    mesh: ModelData,
    poly: Polygon,
    z0: float,
    z1: float,
    material: str,
    component: str = "model",
    skip_edges: List[Tuple[Point2D, Point2D]] | None = None,
    wall_thickness: float = 0.0,
) -> None:
    _add_wall_band_ring(mesh, material, list(poly.exterior.coords), z0, z1, poly, component=component, skip_edges=skip_edges, wall_thickness=wall_thickness)
    for interior in poly.interiors:
        _add_wall_band_ring(mesh, material, list(interior.coords), z0, z1, poly, component=component, skip_edges=skip_edges, wall_thickness=wall_thickness)


def add_extruded_polygon(
    mesh: ModelData,
    geometry,
    z0: float,
    z1: float,
    top_material: str,
    bottom_material: str,
    side_material: str,
    component: str = "model",
    wall_thickness: float = 0.0,
) -> None:
    if z1 <= z0:
        return
    for poly in _iter_polygons(geometry):
        _add_polygon_cap(mesh, top_material, poly, z1, up=True, component=component)
        _add_polygon_cap(mesh, bottom_material, poly, z0, up=False, component=component)
        _add_vertical_walls_for_polygon(mesh, poly, z0, z1, side_material, component=component, wall_thickness=wall_thickness)


def _terrain_profile(
    y: float,
    y_break: float,
    y_low: float,
    z_high: float,
    z_low: float,
) -> float:
    if y <= y_break:
        return z_high
    if y >= y_low:
        return z_low
    if abs(y_low - y_break) < 1e-9:
        return z_low
    t = (y - y_break) / (y_low - y_break)
    return z_high + (z_low - z_high) * t


def _line_intersection(a0: Point2D, a1: Point2D, b0: Point2D, b1: Point2D) -> Point2D:
    x1, y1 = a0
    x2, y2 = a1
    x3, y3 = b0
    x4, y4 = b1
    den = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
    if abs(den) < 1e-12:
        return ((a0[0] + b0[0]) * 0.5, min(a0[1], b0[1]) - abs(a0[0] - b0[0]))
    det_a = x1 * y2 - y1 * x2
    det_b = x3 * y4 - y3 * x4
    px = (det_a * (x3 - x4) - (x1 - x2) * det_b) / den
    py = (det_a * (y3 - y4) - (y1 - y2) * det_b) / den
    return px, py


def _motorcourt_and_driveway(
    s: float,
    driveway_width: float,
    driveway_length: float,
    flat_length: float = 0.0,
    curve_length: float = 0.0,
) -> Tuple[Polygon, Polygon, Point2D, Point2D, Tuple[Point2D, Point2D, Point2D, Point2D],
           List[Polygon], List[Point2D], List[Point2D]]:
    cx, cy = 0.0, -math.sqrt(3.0) * s
    points: List[Point2D] = []
    for i in range(6):
        a = math.radians(i * 60.0)
        points.append((cx + s * math.cos(a), cy + s * math.sin(a)))
    # Half-hex at the rear (toward house) + triangular front extension.
    apex = _line_intersection(points[3], points[4], points[0], points[5])
    motorcourt = Polygon([points[0], points[1], points[2], points[3], apex])

    rear_left = points[3]
    rear_right = points[0]
    rear_width = math.hypot(rear_right[0] - rear_left[0], rear_right[1] - rear_left[1])
    if rear_width < 1e-6:
        rear_width = driveway_width
    t = max(0.05, min(0.95, driveway_width / rear_width))

    start_left = (
        apex[0] + t * (rear_left[0] - apex[0]),
        apex[1] + t * (rear_left[1] - apex[1]),
    )
    start_right = (
        apex[0] + t * (rear_right[0] - apex[0]),
        apex[1] + t * (rear_right[1] - apex[1]),
    )
    start_center = ((start_left[0] + start_right[0]) * 0.5, (start_left[1] + start_right[1]) * 0.5)

    dx = apex[0] - start_center[0]
    dy = apex[1] - start_center[1]
    mag = math.hypot(dx, dy)
    ux, uy = ((0.0, -1.0) if mag < 1e-9 else (dx / mag, dy / mag))
    end_left = (start_left[0] + ux * driveway_length, start_left[1] + uy * driveway_length)
    end_right = (start_right[0] + ux * driveway_length, start_right[1] + uy * driveway_length)
    end_center = ((end_left[0] + end_right[0]) * 0.5, (end_left[1] + end_right[1]) * 0.5)

    driveway = Polygon([start_left, start_right, end_right, end_left])

    # Extended segments beyond the ramp
    extra_segments: List[Polygon] = []
    extra_left_edges: List[Point2D] = []
    extra_right_edges: List[Point2D] = []
    nx, ny = -uy, ux  # perpendicular to driveway direction
    half_w = driveway_width * 0.5

    if flat_length > 0:
        # Flat section continuing in same direction beyond ramp end
        flat_end_left = (end_left[0] + ux * flat_length, end_left[1] + uy * flat_length)
        flat_end_right = (end_right[0] + ux * flat_length, end_right[1] + uy * flat_length)
        flat_seg = Polygon([end_left, end_right, flat_end_right, flat_end_left])
        extra_segments.append(flat_seg)
        extra_left_edges.extend([end_left, flat_end_left])
        extra_right_edges.extend([end_right, flat_end_right])

        if curve_length > 0:
            # Smooth Bezier curve for 90° turn (toward +nx direction)
            flat_end_center = (
                (flat_end_left[0] + flat_end_right[0]) * 0.5,
                (flat_end_left[1] + flat_end_right[1]) * 0.5,
            )
            R_center = curve_length * 2.0 / math.pi
            # Center of curvature offset in (nx, ny) direction from centerline
            arc_cx = flat_end_center[0] + R_center * nx
            arc_cy = flat_end_center[1] + R_center * ny
            R_outer = R_center + half_w  # left edge (far side)
            R_inner = max(R_center - half_w, 0.5)  # right edge (near side)

            theta_start = math.atan2(
                flat_end_center[1] - arc_cy, flat_end_center[0] - arc_cx
            )
            theta_end = theta_start + math.pi / 2.0

            # Bezier kappa for optimal quarter-circle approximation
            kappa = 4.0 / 3.0 * math.tan(math.pi / 8.0)

            def _bezier(P0: Point2D, P1: Point2D, P2: Point2D, P3: Point2D, t: float) -> Point2D:
                s = 1.0 - t
                return (
                    s**3 * P0[0] + 3*s**2*t * P1[0] + 3*s*t**2 * P2[0] + t**3 * P3[0],
                    s**3 * P0[1] + 3*s**2*t * P1[1] + 3*s*t**2 * P2[1] + t**3 * P3[1],
                )

            # Left edge (outer) Bezier control points
            P0L = flat_end_left
            P3L = (arc_cx + R_outer * math.cos(theta_end),
                   arc_cy + R_outer * math.sin(theta_end))
            P1L = (P0L[0] + kappa * R_outer * ux,
                   P0L[1] + kappa * R_outer * uy)
            P2L = (P3L[0] - kappa * R_outer * nx,
                   P3L[1] - kappa * R_outer * ny)

            # Right edge (inner) Bezier control points
            P0R = flat_end_right
            P3R = (arc_cx + R_inner * math.cos(theta_end),
                   arc_cy + R_inner * math.sin(theta_end))
            P1R = (P0R[0] + kappa * R_inner * ux,
                   P0R[1] + kappa * R_inner * uy)
            P2R = (P3R[0] - kappa * R_inner * nx,
                   P3R[1] - kappa * R_inner * ny)

            n_segs = 48
            prev_left = flat_end_left
            prev_right = flat_end_right
            for seg_i in range(1, n_segs + 1):
                t = seg_i / n_segs
                cur_left = _bezier(P0L, P1L, P2L, P3L, t)
                cur_right = _bezier(P0R, P1R, P2R, P3R, t)
                seg_poly = Polygon([prev_left, prev_right, cur_right, cur_left])
                if seg_poly.is_valid and seg_poly.area > 0.01:
                    extra_segments.append(seg_poly)
                extra_left_edges.append(cur_left)
                extra_right_edges.append(cur_right)
                prev_left = cur_left
                prev_right = cur_right

    return (motorcourt, driveway, start_center, end_center,
            (start_left, start_right, end_right, end_left),
            extra_segments, extra_left_edges, extra_right_edges)


def _add_terrain(
    mesh: ModelData,
    plan: PlanGeometry,
    config: Dict[str, float],
) -> None:
    lower_ground = float(config["lower_ground"])
    upper_ground = float(config["upper_ground"])
    terrain_drop = float(config["terrain_drop"])
    s = float(config["s"])
    driveway_width = float(config.get("driveway_width", 12.0))
    driveway_length = float(config.get("driveway_length", 67.5))
    driveway_flat_length = float(config.get("driveway_flat_length", 50.0))
    driveway_curve_length = float(config.get("driveway_curve_length", 50.0))
    approach_slope = float(config.get("driveway_approach_slope", 0.02))
    slab_t = float(config.get("slab_thickness", 1.0))
    z_base = lower_ground - terrain_drop

    house_points = plan.master_triangle + plan.hex_vertices + [p for wing in plan.wing_polygons.values() for p in wing]
    min_x = min(p[0] for p in house_points)
    max_x = max(p[0] for p in house_points)
    min_y = min(p[1] for p in house_points)
    max_y = max(p[1] for p in house_points)
    cx = (min_x + max_x) * 0.5
    cy = (min_y + max_y) * 0.5
    side = max(max_x - min_x, max_y - min_y) * 6.0
    half = side * 0.5
    terrain_square = Polygon(
        [
            (cx - half, cy - half),
            (cx + half, cy - half),
            (cx + half, cy + half),
            (cx - half, cy + half),
        ]
    )

    # Terrain stays flat across to the back of Wings A and B, then drops
    wing_a_back_y = max(p[1] for p in plan.wing_polygons["A"])
    wing_b_back_y = max(p[1] for p in plan.wing_polygons["B"])
    y_break = max(wing_a_back_y, wing_b_back_y)
    wing_c_outer_mid = (
        (plan.extension_vertices[1][0] + plan.extension_vertices[2][0]) * 0.5,
        (plan.extension_vertices[1][1] + plan.extension_vertices[2][1]) * 0.5,
    )
    y_low = wing_c_outer_mid[1]

    cutout_list = [
        Polygon(plan.hex_vertices),
        Polygon(plan.wing_polygons["A"]),
        Polygon(plan.wing_polygons["B"]),
        Polygon(plan.wing_polygons["C"]),
    ]
    # Side courtyards cut from terrain
    if plan.side_courtyard_right:
        cutout_list.append(Polygon(plan.side_courtyard_right))
    if plan.side_courtyard_left:
        cutout_list.append(Polygon(plan.side_courtyard_left))
    building_cutouts = unary_union(cutout_list)
    motorcourt, driveway, drive_start, drive_end, floor_pts, extra_drive_segs, extra_left_edges, extra_right_edges = _motorcourt_and_driveway(
        s, driveway_width, driveway_length, driveway_flat_length, driveway_curve_length
    )

    def _base_terrain_z(x: float, y: float) -> float:
        return _terrain_profile(y, y_break, y_low, upper_ground, lower_ground)

    drive_dx = drive_end[0] - drive_start[0]
    drive_dy = drive_end[1] - drive_start[1]
    drive_len = max(math.hypot(drive_dx, drive_dy), 1e-6)
    drive_ux, drive_uy = drive_dx / drive_len, drive_dy / drive_len
    cut_nx, cut_ny = -drive_uy, drive_ux
    driveway_end_z = _base_terrain_z(drive_end[0], drive_end[1])
    half_w_drive = driveway_width * 0.5

    def driveway_z(x: float, y: float) -> float:
        proj = (x - drive_start[0]) * drive_ux + (y - drive_start[1]) * drive_uy
        t = max(0.0, min(1.0, proj / drive_len))
        return lower_ground + (driveway_end_z - lower_ground) * t

    def extra_drive_z(x: float, y: float) -> float:
        proj = (x - drive_end[0]) * drive_ux + (y - drive_end[1]) * drive_uy
        dist = max(0.0, proj)
        return driveway_end_z - approach_slope * dist

    # Embankment grading: terrain slopes down to meet extended driveway
    _EMBANKMENT_W = 20.0
    if extra_left_edges or extra_right_edges:
        _all_ext = extra_left_edges + extra_right_edges
        _ext_bbox = (
            min(p[0] for p in _all_ext) - _EMBANKMENT_W,
            min(p[1] for p in _all_ext) - _EMBANKMENT_W,
            max(p[0] for p in _all_ext) + _EMBANKMENT_W,
            max(p[1] for p in _all_ext) + _EMBANKMENT_W,
        )
    else:
        _ext_bbox = (0.0, 0.0, 0.0, 0.0)

    def terrain_z(x: float, y: float) -> float:
        base = _base_terrain_z(x, y)
        if not extra_left_edges and not extra_right_edges:
            return base
        if x < _ext_bbox[0] or x > _ext_bbox[2] or y < _ext_bbox[1] or y > _ext_bbox[3]:
            return base
        min_dist = _EMBANKMENT_W + 1.0
        nearest_dz = base
        for edge_list in (extra_left_edges, extra_right_edges):
            for i in range(len(edge_list) - 1):
                e0, e1 = edge_list[i], edge_list[i + 1]
                edx, edy = e1[0] - e0[0], e1[1] - e0[1]
                seg_sq = edx * edx + edy * edy
                if seg_sq < 1e-12:
                    continue
                et = max(0.0, min(1.0, ((x - e0[0]) * edx + (y - e0[1]) * edy) / seg_sq))
                px, py = e0[0] + et * edx, e0[1] + et * edy
                d = math.hypot(x - px, y - py)
                if d < min_dist:
                    min_dist = d
                    nearest_dz = extra_drive_z(px, py)
        if min_dist >= _EMBANKMENT_W:
            return base
        blend = min_dist / _EMBANKMENT_W
        blend = blend * blend * (3.0 - 2.0 * blend)
        return nearest_dz + blend * (base - nearest_dz)
    # Keep driveway top cut aligned to driveway wall footprint at the courtyard seam.
    cut_start_half = driveway_width * 0.5
    cut_start_a = (drive_start[0] + cut_nx * cut_start_half, drive_start[1] + cut_ny * cut_start_half)
    cut_start_b = (drive_start[0] - cut_nx * cut_start_half, drive_start[1] - cut_ny * cut_start_half)
    cut_end_half = driveway_width * 0.5
    cut_end_a = (drive_end[0] + cut_nx * cut_end_half, drive_end[1] + cut_ny * cut_end_half)
    cut_end_b = (drive_end[0] - cut_nx * cut_end_half, drive_end[1] - cut_ny * cut_end_half)
    floor_sl, floor_sr, floor_er, floor_el = floor_pts

    def _side_sign(pt: Point2D) -> float:
        vx = pt[0] - drive_start[0]
        vy = pt[1] - drive_start[1]
        return drive_ux * vy - drive_uy * vx

    left_is_positive = _side_sign(floor_sl) >= 0.0
    start_a_positive = _side_sign(cut_start_a) >= 0.0
    end_a_positive = _side_sign(cut_end_a) >= 0.0

    cut_start_left, cut_start_right = (
        (cut_start_a, cut_start_b) if start_a_positive == left_is_positive else (cut_start_b, cut_start_a)
    )
    cut_end_left, cut_end_right = (cut_end_a, cut_end_b) if end_a_positive == left_is_positive else (cut_end_b, cut_end_a)

    driveway_cut = Polygon([cut_start_left, cut_start_right, cut_end_right, cut_end_left])
    if not driveway_cut.is_valid:
        driveway_cut = driveway_cut.buffer(0)
    if isinstance(driveway_cut, MultiPolygon):
        driveway_cut = max(driveway_cut.geoms, key=lambda g: g.area)
    # Build precise wedge extensions so the driveway cut meets the motorcourt's
    # angled side edges exactly (eliminates shoulder slivers without over-cutting).
    mc_raw = list(motorcourt.exterior.coords)
    if mc_raw and mc_raw[-1] == mc_raw[0]:
        mc_raw = mc_raw[:-1]
    driveway_cut_terrain = driveway_cut
    if len(mc_raw) >= 5:
        # Apex is the vertex closest to the driveway start (bottom of motorcourt).
        apex_idx = min(range(len(mc_raw)), key=lambda i:
            (mc_raw[i][0] - drive_start[0]) ** 2 + (mc_raw[i][1] - drive_start[1]) ** 2)
        prev_idx = (apex_idx - 1) % len(mc_raw)
        next_idx = (apex_idx + 1) % len(mc_raw)

        def _offset_of(pt: Point2D) -> float:
            return (pt[0] - drive_start[0]) * cut_nx + (pt[1] - drive_start[1]) * cut_ny

        def _find_edge_at_offset(p0: Point2D, p1: Point2D, target: float):
            d0, d1 = _offset_of(p0), _offset_of(p1)
            if abs(d1 - d0) < 1e-9:
                return None
            t = (target - d0) / (d1 - d0)
            if 0.0 < t < 1.0:
                return (p0[0] + t * (p1[0] - p0[0]), p0[1] + t * (p1[1] - p0[1]))
            return None

        off_prev = _offset_of(mc_raw[prev_idx])
        off_next = _offset_of(mc_raw[next_idx])
        if off_prev < off_next:
            left_edge = (mc_raw[prev_idx], mc_raw[apex_idx])
            right_edge = (mc_raw[apex_idx], mc_raw[next_idx])
        else:
            left_edge = (mc_raw[next_idx], mc_raw[apex_idx])
            right_edge = (mc_raw[apex_idx], mc_raw[prev_idx])

        ext_left = _find_edge_at_offset(left_edge[0], left_edge[1], _offset_of(cut_start_left))
        ext_right = _find_edge_at_offset(right_edge[0], right_edge[1], _offset_of(cut_start_right))

        wedges: list = []
        if ext_left:
            wedges.append(Polygon([ext_left, cut_start_left, floor_sl]).buffer(0.01))
        if ext_right:
            wedges.append(Polygon([ext_right, floor_sr, cut_start_right]).buffer(0.01))
        if wedges:
            driveway_cut_terrain = unary_union([driveway_cut] + wedges)
            if isinstance(driveway_cut_terrain, MultiPolygon):
                driveway_cut_terrain = max(driveway_cut_terrain.geoms, key=lambda g: g.area)

    # Include extra driveway segments in terrain cutout
    all_drive_cuts = [building_cutouts, motorcourt, driveway_cut_terrain]
    for seg_poly in extra_drive_segs:
        if seg_poly.is_valid and not seg_poly.is_empty:
            all_drive_cuts.append(seg_poly)
    terrain_area = terrain_square.difference(unary_union(all_drive_cuts))

    for poly in _iter_polygons(terrain_area):
        for tri in _triangles_for_polygon(poly):
            p0, p1, p2 = tri
            t0 = (p0[0], p0[1], terrain_z(p0[0], p0[1]))
            t1 = (p1[0], p1[1], terrain_z(p1[0], p1[1]))
            t2 = (p2[0], p2[1], terrain_z(p2[0], p2[1]))
            n = _triangle_normal((t0, t1, t2))
            tri3 = (t0, t1, t2) if n[2] >= 0 else (t0, t2, t1)
            mesh.add_triangle("ground", tri3, component="ground")

        _add_polygon_cap(mesh, "ground", poly, z_base, up=False, component="ground")

        ext = list(poly.exterior.coords)
        ext = ext[:-1] if ext and ext[0] == ext[-1] else ext
        for i in range(len(ext)):
            p0 = ext[i]
            p1 = ext[(i + 1) % len(ext)]
            z0 = terrain_z(p0[0], p0[1])
            z1 = terrain_z(p1[0], p1[1])
            tri1 = ((p0[0], p0[1], z_base), (p1[0], p1[1], z_base), (p1[0], p1[1], z1))
            tri2 = ((p0[0], p0[1], z_base), (p1[0], p1[1], z1), (p0[0], p0[1], z0))
            mesh.add_triangle("ground", tri1, component="ground")
            mesh.add_triangle("ground", tri2, component="ground")

    slab_t = float(config["slab_thickness"])
    driveway_cut_boundary = driveway_cut.boundary
    atrium_front_boundary = LineString(plan.atrium_front_edge)
    motorcourt_floor_area = motorcourt.difference(driveway_cut)
    for poly in _iter_polygons(motorcourt_floor_area):
        # Motorcourt slab: top + bottom + side walls (1' thick)
        _add_polygon_cap(mesh, "concrete", poly, lower_ground, up=True, component="motorcourt_floor")
        _add_polygon_cap(mesh, "concrete", poly, lower_ground - slab_t, up=False, component="motorcourt_floor")
        centroid_xy = (poly.centroid.x, poly.centroid.y)
        ring = list(poly.exterior.coords)
        ring = ring[:-1] if ring and ring[0] == ring[-1] else ring
        for i in range(len(ring)):
            p0 = ring[i]
            p1 = ring[(i + 1) % len(ring)]
            midpoint = ((p0[0] + p1[0]) * 0.5, (p0[1] + p1[1]) * 0.5)
            on_driveway_cut_edge = (
                driveway_cut_boundary.distance(Point(p0)) < 1e-5
                and driveway_cut_boundary.distance(Point(p1)) < 1e-5
                and driveway_cut_boundary.distance(Point(midpoint)) < 1e-5
            )
            on_atrium_front_edge = (
                atrium_front_boundary.distance(Point(p0)) < 1e-5
                and atrium_front_boundary.distance(Point(p1)) < 1e-5
                and atrium_front_boundary.distance(Point(midpoint)) < 1e-5
            )
            if on_driveway_cut_edge:
                continue
            if on_atrium_front_edge:
                # Add slab edge face (motorcourt slab thickness visible from atrium side)
                se1_af: Triangle3D = ((p0[0], p0[1], lower_ground - slab_t), (p1[0], p1[1], lower_ground - slab_t), (p1[0], p1[1], lower_ground))
                se2_af: Triangle3D = ((p0[0], p0[1], lower_ground - slab_t), (p1[0], p1[1], lower_ground), (p0[0], p0[1], lower_ground))
                sn_af = _triangle_normal(se1_af)
                af_mx = (p0[0] + p1[0]) * 0.5
                af_my = (p0[1] + p1[1]) * 0.5
                af_tcx = centroid_xy[0] - af_mx
                af_tcy = centroid_xy[1] - af_my
                if (sn_af[0] * af_tcx + sn_af[1] * af_tcy) > 0.0:
                    se1_af = (se1_af[0], se1_af[2], se1_af[1])
                    se2_af = (se2_af[0], se2_af[2], se2_af[1])
                mesh.add_triangle("concrete", se1_af, component="motorcourt_walls")
                mesh.add_triangle("concrete", se2_af, component="motorcourt_walls")
                continue
            z0 = terrain_z(p0[0], p0[1])
            z1 = terrain_z(p1[0], p1[1])
            # Retaining wall from slab bottom to terrain
            tri1: Triangle3D = ((p0[0], p0[1], lower_ground - slab_t), (p1[0], p1[1], z1), (p1[0], p1[1], lower_ground - slab_t))
            tri2: Triangle3D = ((p0[0], p0[1], lower_ground - slab_t), (p0[0], p0[1], z0), (p1[0], p1[1], z1))
            nx, ny, _ = _triangle_normal(tri1)
            mx = (tri1[0][0] + tri1[1][0] + tri1[2][0]) / 3.0
            my = (tri1[0][1] + tri1[1][1] + tri1[2][1]) / 3.0
            to_center_x = centroid_xy[0] - mx
            to_center_y = centroid_xy[1] - my
            if (nx * to_center_x + ny * to_center_y) < 0.0:
                tri1 = (tri1[0], tri1[2], tri1[1])
                tri2 = (tri2[0], tri2[2], tri2[1])
            mesh.add_triangle("concrete", tri1, component="motorcourt_walls")
            mesh.add_triangle("concrete", tri2, component="motorcourt_walls")
            # Slab edge (from slab bottom to slab top)
            se1: Triangle3D = ((p0[0], p0[1], lower_ground - slab_t), (p1[0], p1[1], lower_ground - slab_t), (p1[0], p1[1], lower_ground))
            se2: Triangle3D = ((p0[0], p0[1], lower_ground - slab_t), (p1[0], p1[1], lower_ground), (p0[0], p0[1], lower_ground))
            sn = _triangle_normal(se1)
            if (sn[0] * to_center_x + sn[1] * to_center_y) > 0.0:
                se1 = (se1[0], se1[2], se1[1])
                se2 = (se2[0], se2[2], se2[1])
            mesh.add_triangle("concrete", se1, component="motorcourt_walls")
            mesh.add_triangle("concrete", se2, component="motorcourt_walls")

    # Driveway slab: top surface + bottom surface (offset 1' down) + side edge walls
    for tri in _triangles_for_polygon(driveway):
        p0, p1, p2 = tri
        # Top surface
        t0 = (p0[0], p0[1], driveway_z(p0[0], p0[1]))
        t1 = (p1[0], p1[1], driveway_z(p1[0], p1[1]))
        t2 = (p2[0], p2[1], driveway_z(p2[0], p2[1]))
        n = _triangle_normal((t0, t1, t2))
        tri3 = (t0, t1, t2) if n[2] >= 0 else (t0, t2, t1)
        mesh.add_triangle("concrete", tri3, component="driveway_floor")
        # Bottom surface (1' below)
        b0 = (p0[0], p0[1], driveway_z(p0[0], p0[1]) - slab_t)
        b1 = (p1[0], p1[1], driveway_z(p1[0], p1[1]) - slab_t)
        b2 = (p2[0], p2[1], driveway_z(p2[0], p2[1]) - slab_t)
        n2 = _triangle_normal((b0, b1, b2))
        tri3b = (b0, b2, b1) if n2[2] >= 0 else (b0, b1, b2)
        mesh.add_triangle("concrete", tri3b, component="driveway_floor")

    wall_pairs = [
        (floor_sl, cut_start_left, cut_end_left, floor_el),
        (floor_sr, cut_start_right, cut_end_right, floor_er),
    ]
    driveway_center_xy = ((drive_start[0] + drive_end[0]) * 0.5, (drive_start[1] + drive_end[1]) * 0.5)
    for f_start, c_start, c_end, f_end in wall_pairs:
        # Wall from slab bottom to terrain (retaining wall visible from outside)
        fs_bot = (f_start[0], f_start[1], driveway_z(f_start[0], f_start[1]) - slab_t)
        fe_bot = (f_end[0], f_end[1], driveway_z(f_end[0], f_end[1]) - slab_t)
        cs = (c_start[0], c_start[1], max(terrain_z(c_start[0], c_start[1]), fs_bot[2]))
        ce = (c_end[0], c_end[1], max(terrain_z(c_end[0], c_end[1]), fe_bot[2]))
        tri1: Triangle3D = (fs_bot, cs, ce)
        tri2: Triangle3D = (fs_bot, ce, fe_bot)
        nx, ny, _ = _triangle_normal(tri1)
        mx = (fs_bot[0] + cs[0] + ce[0]) / 3.0
        my = (fs_bot[1] + cs[1] + ce[1]) / 3.0
        to_center_x = driveway_center_xy[0] - mx
        to_center_y = driveway_center_xy[1] - my
        if (nx * to_center_x + ny * to_center_y) < 0.0:
            tri1 = (tri1[0], tri1[2], tri1[1])
            tri2 = (tri2[0], tri2[2], tri2[1])
        mesh.add_triangle("concrete", tri1, component="driveway_walls")
        mesh.add_triangle("concrete", tri2, component="driveway_walls")
        # Slab edge strip (slab bottom to slab top)
        fs_top = (f_start[0], f_start[1], driveway_z(f_start[0], f_start[1]))
        fe_top = (f_end[0], f_end[1], driveway_z(f_end[0], f_end[1]))
        se1: Triangle3D = (fs_bot, fe_bot, fe_top)
        se2: Triangle3D = (fs_bot, fe_top, fs_top)
        sn = _triangle_normal(se1)
        if (sn[0] * to_center_x + sn[1] * to_center_y) > 0.0:
            se1 = (se1[0], se1[2], se1[1])
            se2 = (se2[0], se2[2], se2[1])
        mesh.add_triangle("concrete", se1, component="driveway_walls")
        mesh.add_triangle("concrete", se2, component="driveway_walls")

    # Extra driveway segments (flat + curved sections) — top + bottom surfaces
    for seg_poly in extra_drive_segs:
        if not seg_poly.is_valid or seg_poly.is_empty:
            continue
        for tri in _triangles_for_polygon(seg_poly):
            p0, p1, p2 = tri
            # Top surface
            t0 = (p0[0], p0[1], extra_drive_z(p0[0], p0[1]))
            t1 = (p1[0], p1[1], extra_drive_z(p1[0], p1[1]))
            t2 = (p2[0], p2[1], extra_drive_z(p2[0], p2[1]))
            n = _triangle_normal((t0, t1, t2))
            tri3 = (t0, t1, t2) if n[2] >= 0 else (t0, t2, t1)
            mesh.add_triangle("concrete", tri3, component="driveway_ext_floor")
            # Bottom surface (1' below)
            b0 = (p0[0], p0[1], extra_drive_z(p0[0], p0[1]) - slab_t)
            b1 = (p1[0], p1[1], extra_drive_z(p1[0], p1[1]) - slab_t)
            b2 = (p2[0], p2[1], extra_drive_z(p2[0], p2[1]) - slab_t)
            n2 = _triangle_normal((b0, b1, b2))
            tri3b = (b0, b2, b1) if n2[2] >= 0 else (b0, b1, b2)
            mesh.add_triangle("concrete", tri3b, component="driveway_ext_floor")

    # Retaining walls along extra driveway edges (fills terrain-to-driveway gap)
    for edge_points, sign in [(extra_left_edges, 1.0), (extra_right_edges, -1.0)]:
        if len(edge_points) < 2:
            continue
        for i in range(len(edge_points) - 1):
            p0 = edge_points[i]
            p1 = edge_points[i + 1]
            tz0 = terrain_z(p0[0], p0[1])
            tz1 = terrain_z(p1[0], p1[1])
            dz0 = extra_drive_z(p0[0], p0[1])
            dz1 = extra_drive_z(p1[0], p1[1])
            dz0_bot = dz0 - slab_t
            dz1_bot = dz1 - slab_t
            if tz0 <= dz0_bot + 0.05 and tz1 <= dz1_bot + 0.05:
                continue
            top0: Point3D = (p0[0], p0[1], max(tz0, dz0_bot))
            top1: Point3D = (p1[0], p1[1], max(tz1, dz1_bot))
            bot0: Point3D = (p0[0], p0[1], dz0_bot)
            bot1: Point3D = (p1[0], p1[1], dz1_bot)
            tri1: Triangle3D = (bot0, bot1, top1)
            tri2: Triangle3D = (bot0, top1, top0)
            # Orient normals outward (away from driveway center)
            wnx, wny, _ = _triangle_normal(tri1)
            edge_dx = p1[0] - p0[0]
            edge_dy = p1[1] - p0[1]
            # Cross product of edge direction with up gives outward direction
            outward_x = -edge_dy * sign
            outward_y = edge_dx * sign
            if (wnx * outward_x + wny * outward_y) < 0:
                tri1 = (tri1[0], tri1[2], tri1[1])
                tri2 = (tri2[0], tri2[2], tri2[1])
            mesh.add_triangle("concrete", tri1, component="driveway_ext_walls")
            mesh.add_triangle("concrete", tri2, component="driveway_ext_walls")


def _add_pyramid_roof(
    mesh: ModelData,
    base_points: List[Point2D],
    z_base: float,
    rise: float,
    material: str,
    component: str = "model",
) -> None:
    cx = sum(p[0] for p in base_points) / len(base_points)
    cy = sum(p[1] for p in base_points) / len(base_points)
    apex = (cx, cy, z_base + rise)

    for i in range(len(base_points)):
        p0 = base_points[i]
        p1 = base_points[(i + 1) % len(base_points)]
        tri: Triangle3D = ((p0[0], p0[1], z_base), (p1[0], p1[1], z_base), apex)
        nx, ny, nz = _triangle_normal(tri)
        if nz < 0:
            tri = (tri[0], tri[2], tri[1])
        elif abs(nz) < 1e-6 and (nx * (p0[0] - cx) + ny * (p0[1] - cy)) < 0:
            tri = (tri[0], tri[2], tri[1])
        mesh.add_triangle(material, tri, component=component)


def build_courtyard_shared_front_edge(mesh: ModelData, plan: PlanGeometry, config: Dict[str, float]) -> None:
    if not plan.courtyard_polygon:
        return
    courtyard = Polygon(plan.courtyard_polygon)
    top = float(config.get("master_triangle_elevation", float(config["upper_ground"])))
    drop = top + float(config["courtyard_drop"])
    wt_conc = float(config.get("wall_thickness_concrete", 0.0))
    _add_polygon_cap(mesh, "concrete", courtyard, drop, up=True, component="courtyard")
    _add_vertical_walls_for_polygon(mesh, courtyard, drop, top, "concrete", component="courtyard", wall_thickness=wt_conc)


def build_courtyard_none(mesh: ModelData, plan: PlanGeometry, config: Dict[str, float]) -> None:
    return


COURTYARD_MODULES: Dict[str, Callable[[ModelData, PlanGeometry, Dict[str, float]], None]] = {
    "none": build_courtyard_none,
    "exterior_hex": build_courtyard_shared_front_edge,
    "shared_front_edge": build_courtyard_shared_front_edge,
}


def _add_side_courtyards(
    mesh: ModelData,
    plan: PlanGeometry,
    config: Dict[str, float],
) -> None:
    """Build hexagonal courtyard voids between wing pairs.

    Retaining walls rise 4' above surrounding terrain, open at the back
    where terrain descends to ground level.  Floor is lawn.
    """
    lower_ground = float(config["lower_ground"])
    upper_ground = float(config["upper_ground"])
    terrain_drop = float(config["terrain_drop"])
    s = float(config["s"])
    retaining_wall_rise = 4.0  # feet above surrounding earth

    wing_a_back_y = max(p[1] for p in plan.wing_polygons["A"])
    wing_b_back_y = max(p[1] for p in plan.wing_polygons["B"])
    y_break = max(wing_a_back_y, wing_b_back_y)
    wing_c_outer_mid = (
        (plan.extension_vertices[1][0] + plan.extension_vertices[2][0]) * 0.5,
        (plan.extension_vertices[1][1] + plan.extension_vertices[2][1]) * 0.5,
    )
    y_low = wing_c_outer_mid[1]

    def terrain_z(x: float, y: float) -> float:
        return _terrain_profile(y, y_break, y_low, upper_ground, lower_ground)

    for label, court_verts in [
        ("side_court_right", plan.side_courtyard_right),
        ("side_court_left", plan.side_courtyard_left),
    ]:
        if not court_verts:
            continue
        court_poly = Polygon(court_verts)
        # Lawn floor at lower_ground level
        _add_polygon_cap(mesh, "ground", court_poly, lower_ground, up=True, component=f"{label}_floor")

        pts = list(court_verts)
        # Find the back edge (highest Y midpoint) — leave it open to back yard
        back_edge_idx = max(
            range(len(pts)),
            key=lambda i: (pts[i][1] + pts[(i + 1) % len(pts)][1]) / 2.0,
        )
        wt_conc = float(config.get("wall_thickness_concrete", 0.667))
        for i in range(len(pts)):
            p0 = pts[i]
            p1 = pts[(i + 1) % len(pts)]
            # Skip the back edge entirely — open to back lawn
            if i == back_edge_idx:
                continue
            # Terrain height at each vertex
            tz0 = terrain_z(p0[0], p0[1])
            tz1 = terrain_z(p1[0], p1[1])
            # Retaining wall top = terrain + 4', but not below courtyard floor
            wall_top_0 = max(tz0 + retaining_wall_rise, lower_ground)
            wall_top_1 = max(tz1 + retaining_wall_rise, lower_ground)
            # Skip edges where wall height is negligible
            if wall_top_0 - lower_ground < 0.5 and wall_top_1 - lower_ground < 0.5:
                continue
            # Build thick wall with per-vertex top heights (follows terrain contour)
            edge_dx = p1[0] - p0[0]
            edge_dy = p1[1] - p0[1]
            edge_len = math.hypot(edge_dx, edge_dy)
            if edge_len < 1e-9:
                continue
            # Perpendicular outward normal (away from courtyard center)
            nx = -edge_dy / edge_len
            ny = edge_dx / edge_len
            cx, cy = court_poly.centroid.x, court_poly.centroid.y
            mx, my = (p0[0] + p1[0]) * 0.5, (p0[1] + p1[1]) * 0.5
            if nx * (mx - cx) + ny * (my - cy) < 0:
                nx, ny = -nx, -ny
            half_t = wt_conc / 2.0
            # Outer vertices
            o0 = (p0[0] + nx * half_t, p0[1] + ny * half_t)
            o1 = (p1[0] + nx * half_t, p1[1] + ny * half_t)
            # Inner vertices
            i0 = (p0[0] - nx * half_t, p0[1] - ny * half_t)
            i1 = (p1[0] - nx * half_t, p1[1] - ny * half_t)

            def _cquad(a, b, c, d, out_dir):
                t1 = (a, b, c)
                t2 = (a, c, d)
                n = _triangle_normal(t1)
                dot = n[0]*out_dir[0] + n[1]*out_dir[1] + n[2]*out_dir[2]
                if dot < 0:
                    t1 = (t1[0], t1[2], t1[1])
                    t2 = (t2[0], t2[2], t2[1])
                mesh.add_triangle("concrete", t1, component=f"{label}_walls")
                mesh.add_triangle("concrete", t2, component=f"{label}_walls")

            z_bot = lower_ground
            # Outer face (per-vertex top heights)
            _cquad((o0[0], o0[1], z_bot), (o1[0], o1[1], z_bot),
                   (o1[0], o1[1], wall_top_1), (o0[0], o0[1], wall_top_0),
                   (nx, ny, 0.0))
            # Inner face
            _cquad((i1[0], i1[1], z_bot), (i0[0], i0[1], z_bot),
                   (i0[0], i0[1], wall_top_0), (i1[0], i1[1], wall_top_1),
                   (-nx, -ny, 0.0))
            # Top cap (sloped)
            _cquad((o0[0], o0[1], wall_top_0), (o1[0], o1[1], wall_top_1),
                   (i1[0], i1[1], wall_top_1), (i0[0], i0[1], wall_top_0),
                   (0.0, 0.0, 1.0))
            # Bottom cap
            _cquad((i0[0], i0[1], z_bot), (i1[0], i1[1], z_bot),
                   (o1[0], o1[1], z_bot), (o0[0], o0[1], z_bot),
                   (0.0, 0.0, -1.0))


def build_model(plan: PlanGeometry, config: Dict[str, float]) -> ModelData:
    mesh = ModelData()

    lower_ground = float(config["lower_ground"])
    upper_ground = float(config["upper_ground"])
    slab = float(config["slab_thickness"])
    ceiling = float(config["ceiling_height"])
    master_triangle_elevation = float(config.get("master_triangle_elevation", upper_ground + ceiling))
    atrium_floor = float(config["atrium_floor"])
    atrium_roof_base = float(config["atrium_roof_base"])
    atrium_roof_rise = float(config["atrium_roof_rise"])

    wt_conc = float(config.get("wall_thickness_concrete", 0.0))
    wt_glass = float(config.get("wall_thickness_glass", 0.0))

    triangle_poly = Polygon(plan.master_triangle)
    atrium_poly = Polygon(plan.hex_vertices)
    courtyard_module_name = str(config.get("courtyard_module", "none"))
    courtyard_module = COURTYARD_MODULES.get(courtyard_module_name)
    if courtyard_module is None:
        raise ValueError(f"Unknown courtyard module: {courtyard_module_name}")
    _add_terrain(mesh, plan, config)

    triangle_slab_poly = triangle_poly.difference(atrium_poly)
    add_extruded_polygon(
        mesh,
        triangle_slab_poly,
        master_triangle_elevation,
        master_triangle_elevation + slab,
        top_material="concrete",
        bottom_material="concrete",
        side_material="concrete",
        component="master_triangle_floor",
        wall_thickness=wt_conc,
    )
    _add_vertical_walls_for_polygon(
        mesh,
        triangle_poly,
        master_triangle_elevation + slab,
        master_triangle_elevation + slab + ceiling,
        "glass",
        component="master_triangle_facade",
        wall_thickness=wt_glass,
    )
    triangle_roof_poly = triangle_poly.difference(atrium_poly)
    add_extruded_polygon(
        mesh,
        triangle_roof_poly,
        master_triangle_elevation + slab + ceiling,
        master_triangle_elevation + slab + ceiling + slab,
        top_material="concrete",
        bottom_material="concrete",
        side_material="concrete",
        component="master_triangle_roof_slab",
        wall_thickness=wt_conc,
    )

    garage_floor = lower_ground
    for wing_name in ("A", "B"):
        wing_poly = Polygon(plan.wing_polygons[wing_name])
        i0, i1 = WING_EDGE_INDICES[wing_name]
        atrium_edge_garage = (plan.hex_vertices[i0], plan.hex_vertices[i1])

        # Solid concrete foundation from atrium floor to garage walking surface
        # Creates walls on ALL edges (including atrium-facing) to seal completely
        add_extruded_polygon(
            mesh,
            wing_poly,
            atrium_floor,
            garage_floor + slab,
            top_material="concrete",
            bottom_material="concrete",
            side_material="concrete",
            component=f"wing_{wing_name.lower()}_garage_floor",
            wall_thickness=wt_conc,
        )
        # All garage walls concrete (including atrium-facing edge)
        _add_vertical_walls_for_polygon(
            mesh,
            wing_poly,
            garage_floor + slab,
            garage_floor + slab + ceiling,
            "concrete",
            component=f"wing_{wing_name.lower()}_garage_facade",
            skip_edges=[atrium_edge_garage],
            wall_thickness=wt_conc,
        )
        # Concrete wall on atrium-facing edge
        p0, p1 = atrium_edge_garage
        z0_w, z1_w = garage_floor + slab, garage_floor + slab + ceiling
        _add_solid_wall_edge(mesh, "concrete", p0, p1, z0_w, z1_w,
                             wt_conc, wing_poly,
                             component=f"wing_{wing_name.lower()}_garage_facade")
        # NOTE: garage_roof_slab removed - wing_floor at same z range covers it,
        # and having both caused z-fighting on the atrium edge.

    wing_floor_elevation = {"A": upper_ground, "B": upper_ground, "C": lower_ground}
    double_height_wings = {"C"}
    # Edges facing the atrium that should be open (no wall)
    wing_atrium_edges = {
        "A": (plan.hex_vertices[0], plan.hex_vertices[5]),   # hex v0→v5
        "C": (plan.hex_vertices[1], plan.hex_vertices[2]),   # hex v1→v2
    }
    for wing_name, floor in wing_floor_elevation.items():
        wing_poly = Polygon(plan.wing_polygons[wing_name])
        wall_top = master_triangle_elevation if wing_name in double_height_wings else floor + ceiling
        add_extruded_polygon(
            mesh,
            wing_poly,
            floor,
            floor + slab,
            top_material="marble" if wing_name == "C" else "concrete",
            bottom_material="concrete",
            side_material="concrete",
            component=f"wing_{wing_name.lower()}_floor",
            wall_thickness=wt_conc,
        )
        wing_skip = [wing_atrium_edges[wing_name]] if wing_name in wing_atrium_edges else []
        _add_vertical_walls_for_polygon(
            mesh,
            wing_poly,
            floor + slab,
            wall_top,
            "glass",
            component=f"wing_{wing_name.lower()}_facade",
            skip_edges=wing_skip,
            wall_thickness=wt_glass,
        )
        add_extruded_polygon(
            mesh,
            wing_poly,
            wall_top,
            wall_top + slab,
            top_material="concrete",
            bottom_material="concrete",
            side_material="concrete",
            component=f"wing_{wing_name.lower()}_roof_slab",
            wall_thickness=wt_conc,
        )

    # Concrete wall closing the gap between atrium floor and Wing C floor.
    # Wings A and B don't need this: their garage structure already provides
    # continuous wall coverage from atrium_floor to upper_ground on the atrium edge.
    # Having both caused z-fighting artifacts (dark band at wall-floor junction).
    for wing_name in ("C",):
        i0, i1 = WING_EDGE_INDICES[wing_name]
        p0 = plan.hex_vertices[i0]
        p1 = plan.hex_vertices[i1]
        z_bot = atrium_floor
        z_top = wing_floor_elevation[wing_name]
        if z_top > z_bot:
            w_poly = Polygon(plan.wing_polygons[wing_name])
            _add_solid_wall_edge(mesh, "concrete", p0, p1, z_bot, z_top,
                                wt_conc, w_poly,
                                component=f"wing_{wing_name.lower()}_atrium_wall")

    # Atrium floor slab.
    # Polygon buffered OUTWARD by half concrete wall thickness so the marble
    # cap extends under/through the surrounding structural walls, preventing
    # any visible seam at the floor-wall junction.  A small extra overlap
    # (seam_fix) pushes the marble slightly past the coplanar wall face to
    # eliminate T-junction rendering artifacts (dark band from z-fighting).
    half_wt = wt_conc / 2.0
    seam_fix = 0.05                                        # 0.6" overlap
    atrium_floor_poly = atrium_poly.buffer(half_wt + seam_fix, join_style=2)
    _add_polygon_cap(mesh, "marble", atrium_floor_poly, atrium_floor + slab,
                     up=True, component="atrium_floor")
    _add_polygon_cap(mesh, "concrete", atrium_floor_poly, atrium_floor,
                     up=False, component="atrium_floor")
    # Inward-facing side walls seal the slab edge so no void is visible from
    # inside the atrium when looking toward the wall base at a steep angle.
    _ring = list(atrium_floor_poly.exterior.coords)
    if _ring and _ring[0] == _ring[-1]:
        _ring = _ring[:-1]
    _cx = sum(p[0] for p in _ring) / len(_ring)
    _cy = sum(p[1] for p in _ring) / len(_ring)
    _z0, _z1 = atrium_floor, atrium_floor + slab
    for _i in range(len(_ring)):
        _p0 = _ring[_i]
        _p1 = _ring[(_i + 1) % len(_ring)]
        # Determine inward winding: cross product with centroid direction
        _ex = _p1[0] - _p0[0]
        _ey = _p1[1] - _p0[1]
        _tx = _cx - _p0[0]
        _ty = _cy - _p0[1]
        _cross = _ex * _ty - _ey * _tx
        if _cross > 0:
            _a, _b = _p0, _p1
        else:
            _a, _b = _p1, _p0
        mesh.add_triangle("concrete",
            ((_a[0], _a[1], _z0), (_a[0], _a[1], _z1), (_b[0], _b[1], _z1)),
            component="atrium_floor")
        mesh.add_triangle("concrete",
            ((_a[0], _a[1], _z0), (_b[0], _b[1], _z1), (_b[0], _b[1], _z0)),
            component="atrium_floor")

    # Wing C edge (hex v1→v2) and Wing A edge (hex v0→v5) are open to atrium
    # Wing B edge (hex v3→v4) handled separately: concrete at bedroom level, glass elsewhere
    wing_b_atrium_edge = (plan.hex_vertices[3], plan.hex_vertices[4])
    open_atrium_edges = [
        (plan.hex_vertices[1], plan.hex_vertices[2]),  # Wing C
        (plan.hex_vertices[0], plan.hex_vertices[5]),  # Wing A
        wing_b_atrium_edge,                             # Wing B (added manually below)
    ]
    # Start glass walls at atrium_floor (below marble surface) so the
    # bottom edge is hidden beneath the slab and no teal band is visible.
    _add_vertical_walls_for_polygon(
        mesh,
        atrium_poly,
        atrium_floor,
        atrium_roof_base,
        "glass",
        component="atrium_facade",
        skip_edges=open_atrium_edges,
        wall_thickness=wt_glass,
    )
    # Wing B atrium edge: glass below bedroom, concrete at bedroom, glass above
    p0_b, p1_b = wing_b_atrium_edge
    bed_wall_segments = [
        (atrium_floor, master_triangle_elevation, "glass", wt_glass),
        (master_triangle_elevation + slab, master_triangle_elevation + slab + ceiling, "concrete", wt_conc),
        (master_triangle_elevation + slab + ceiling, atrium_roof_base, "glass", wt_glass),
    ]
    for z0_seg, z1_seg, seg_mat, seg_wt in bed_wall_segments:
        if z1_seg <= z0_seg:
            continue
        comp = "atrium_facade" if seg_mat == "glass" else "bedroom_accent_wall"
        _add_solid_wall_edge(mesh, seg_mat, p0_b, p1_b, z0_seg, z1_seg,
                             seg_wt, atrium_poly, component=comp)
    _add_pyramid_roof(mesh, plan.hex_vertices, atrium_roof_base, atrium_roof_rise, "glass", component="atrium_roof")

    courtyard_module(mesh, plan, config)

    # Side courtyards between wing pairs
    _add_side_courtyards(mesh, plan, config)

    return mesh

