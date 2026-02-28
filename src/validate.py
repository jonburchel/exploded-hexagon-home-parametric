from __future__ import annotations

from pathlib import Path
from typing import Dict, Iterable, List, Tuple
import math

from shapely.geometry import Polygon

from .plan import PlanGeometry

Point2D = Tuple[float, float]


def _distance(a: Point2D, b: Point2D) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _edge_match(edge_a: Tuple[Point2D, Point2D], edge_b: Tuple[Point2D, Point2D], eps: float) -> bool:
    direct = _distance(edge_a[0], edge_b[0]) <= eps and _distance(edge_a[1], edge_b[1]) <= eps
    reverse = _distance(edge_a[0], edge_b[1]) <= eps and _distance(edge_a[1], edge_b[0]) <= eps
    return direct or reverse


def _polygon_has_edge(points: List[Point2D], edge: Tuple[Point2D, Point2D], eps: float) -> bool:
    for i in range(len(points)):
        candidate = (points[i], points[(i + 1) % len(points)])
        if _edge_match(candidate, edge, eps):
            return True
    return False


def _normalize_angle(angle: float) -> float:
    twopi = 2.0 * math.pi
    while angle < 0.0:
        angle += twopi
    while angle >= twopi:
        angle -= twopi
    return angle


def validate_geometry(plan: PlanGeometry, config: Dict[str, float]) -> Dict[str, object]:
    eps = float(config.get("epsilon", 1e-6))
    s = float(config["s"])
    courtyard_module = str(config.get("courtyard_module", "none"))
    include_courtyard = courtyard_module != "none" and bool(plan.courtyard_polygon)

    hex_lengths = []
    for i in range(len(plan.hex_vertices)):
        hex_lengths.append(_distance(plan.hex_vertices[i], plan.hex_vertices[(i + 1) % len(plan.hex_vertices)]))
    if any(abs(length - s) > eps for length in hex_lengths):
        raise AssertionError("Hex side length constraint failed.")

    extension_lengths = []
    for i, p in enumerate(plan.hex_vertices):
        extension_lengths.append(_distance(p, plan.extension_vertices[i]))
    if any(abs(length - s) > eps for length in extension_lengths):
        raise AssertionError("Exploded extension length constraint failed.")

    if include_courtyard and not _polygon_has_edge(plan.courtyard_polygon, plan.atrium_front_edge, eps):
        raise AssertionError("Courtyard front edge must match atrium front edge.")

    area_atrium = Polygon(plan.hex_vertices).area
    area_wings = {wing: Polygon(poly).area for wing, poly in plan.wing_polygons.items()}
    area_triangle = Polygon(plan.master_triangle).area
    triangle_poly = Polygon(plan.master_triangle)
    atrium_poly = Polygon(plan.hex_vertices)
    triangle_usable = triangle_poly.difference(atrium_poly)
    center = (atrium_poly.centroid.x, atrium_poly.centroid.y)
    wing_angles: Dict[str, float] = {}
    for wing_name, wing_poly in plan.wing_polygons.items():
        e0, e1 = wing_poly[0], wing_poly[1]
        mid = ((e0[0] + e1[0]) * 0.5, (e0[1] + e1[1]) * 0.5)
        wing_angles[wing_name] = _normalize_angle(math.atan2(mid[1] - center[1], mid[0] - center[0]))
    ordered = sorted(wing_angles.items(), key=lambda kv: kv[1])
    ordered_names = [name for name, _ in ordered]
    ordered_angles = [ang for _, ang in ordered]

    def _mid_angle(a0: float, a1: float) -> float:
        if a1 < a0:
            a1 += 2.0 * math.pi
        return _normalize_angle((a0 + a1) * 0.5)

    boundary_angles: Dict[str, Tuple[float, float]] = {}
    for i, wing_name in enumerate(ordered_names):
        prev_ang = ordered_angles[(i - 1) % 3]
        this_ang = ordered_angles[i]
        next_ang = ordered_angles[(i + 1) % 3]
        start = _mid_angle(prev_ang, this_ang)
        end = _mid_angle(this_ang, next_ang)
        if end < start:
            end += 2.0 * math.pi
        boundary_angles[wing_name] = (start, end)

    min_x, min_y, max_x, max_y = triangle_poly.bounds
    radius = max(max_x - min_x, max_y - min_y) * 4.0 + 10.0
    triangle_room_areas: Dict[str, float] = {}
    for wing_name in ("A", "B", "C"):
        start, end = boundary_angles[wing_name]
        p0 = (center[0] + radius * math.cos(start), center[1] + radius * math.sin(start))
        p1 = (center[0] + radius * math.cos(end), center[1] + radius * math.sin(end))
        sector = Polygon([center, p0, p1])
        triangle_room_areas[wing_name] = triangle_usable.intersection(sector).area

    area_courtyard = Polygon(plan.courtyard_polygon).area if include_courtyard else 0.0
    reported_courtyard_area = area_courtyard if include_courtyard else 0.0

    if area_atrium <= 0 or area_triangle <= 0:
        raise AssertionError("Area calculation produced non-positive geometry.")
    if include_courtyard and area_courtyard <= 0:
        raise AssertionError("Courtyard area must be positive when enabled.")
    if include_courtyard and area_courtyard >= area_triangle:
        raise AssertionError("Courtyard cannot exceed or equal master triangle area.")
    if include_courtyard and courtyard_module == "exterior_hex":
        atrium_area = area_atrium
        if abs(area_courtyard - atrium_area) > eps * max(1.0, atrium_area):
            raise AssertionError("Exterior hex courtyard must match atrium hex area.")

    return {
        "hex_side_lengths": hex_lengths,
        "extension_lengths": extension_lengths,
        "areas": {
            "atrium": area_atrium,
            "wing_A": area_wings["A"],
            "wing_B": area_wings["B"],
            "wing_C": area_wings["C"],
            "wings_total": sum(area_wings.values()),
            "master_triangle": area_triangle,
            "courtyard": reported_courtyard_area,
        },
        "triangle_room_areas": {
            "room_A": triangle_room_areas["A"],
            "room_B": triangle_room_areas["B"],
            "room_C": triangle_room_areas["C"],
            "room_total": sum(triangle_room_areas.values()),
        },
        "shared_edge_valid": include_courtyard,
        "courtyard_enabled": include_courtyard,
    }


def write_summary(
    summary_path: Path,
    config: Dict[str, float],
    metrics: Dict[str, object],
    outputs: Dict[str, Path],
    render_paths: List[Path],
    quicklook_path: Path | None,
    blender_available: bool,
) -> None:
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    areas = metrics["areas"]
    room_areas = metrics.get("triangle_room_areas", {})

    lines = [
        "Exploded Hexagon Home - Summary",
        "",
        "Parameters",
        f"s: {config['s']}",
        f"d: {config['d']}",
        f"ceiling_height: {config['ceiling_height']}",
        f"slab_thickness: {config['slab_thickness']}",
        f"lower_ground: {config['lower_ground']}",
        f"upper_ground: {config['upper_ground']}",
        f"atrium_floor: {config['atrium_floor']}",
        f"atrium_roof_base: {config['atrium_roof_base']}",
        f"atrium_roof_apex: {float(config['atrium_roof_base']) + float(config['atrium_roof_rise'])}",
        f"courtyard_drop: {config['courtyard_drop']}",
        "",
        "Validation",
        "Hex side lengths are equal to s.",
        "Exploded extension lengths are equal to s.",
        ("Courtyard shared edge matches atrium front edge." if metrics.get("courtyard_enabled") else "Courtyard disabled."),
        "",
        "Areas (sq ft)",
        f"Atrium: {areas['atrium']:.3f}",
        f"Wing A: {areas['wing_A']:.3f}",
        f"Wing B: {areas['wing_B']:.3f}",
        f"Wing C: {areas['wing_C']:.3f}",
        f"Total Wings: {areas['wings_total']:.3f}",
        f"Master Triangle: {areas['master_triangle']:.3f}",
        f"Triangle Room A: {float(room_areas.get('room_A', 0.0)):.3f}",
        f"Triangle Room B: {float(room_areas.get('room_B', 0.0)):.3f}",
        f"Triangle Room C: {float(room_areas.get('room_C', 0.0)):.3f}",
        f"Triangle Rooms Total: {float(room_areas.get('room_total', 0.0)):.3f}",
        f"Courtyard: {areas['courtyard']:.3f}",
        "",
        "Outputs",
        f"Plan SVG: {outputs['plan']}",
        f"Massing GLB: {outputs['glb']}",
        f"Summary TXT: {outputs['summary']}",
    ]

    if blender_available:
        if render_paths:
            lines.append(f"Renders: {', '.join(str(path) for path in render_paths)}")
            if quicklook_path is not None:
                lines.append(f"Quicklook PNG: {quicklook_path}")
        else:
            lines.append("Renders: Blender found, but no render outputs were created.")
    else:
        lines.append("Renders: Blender not found, skipped.")

    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

