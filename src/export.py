from __future__ import annotations

import json
import math
from pathlib import Path
import struct
from typing import Callable, Dict, Iterable, List, Tuple

import numpy as np
from shapely.geometry import Point, Polygon

from .model import ModelData, Triangle3D
from .plan import PlanGeometry

Point2D = Tuple[float, float]
Point3D = Tuple[float, float, float]

MATERIALS: Dict[str, Dict[str, object]] = {
    "glass": {
        "pbrMetallicRoughness": {
            "baseColorFactor": [0.62, 0.79, 0.90, 0.35],
            "metallicFactor": 0.0,
            "roughnessFactor": 0.05,
        },
        "alphaMode": "BLEND",
        "doubleSided": True,
    },
    "concrete": {
        "pbrMetallicRoughness": {
            "baseColorFactor": [0.70, 0.70, 0.72, 1.0],
            "metallicFactor": 0.0,
            "roughnessFactor": 0.85,
        },
        "doubleSided": False,
    },
    "ground": {
        "pbrMetallicRoughness": {
            "baseColorFactor": [0.18, 0.43, 0.20, 1.0],
            "metallicFactor": 0.0,
            "roughnessFactor": 1.0,
        },
        "doubleSided": False,
    },
    "marble": {
        "pbrMetallicRoughness": {
            "baseColorFactor": [0.92, 0.90, 0.87, 1.0],
            "metallicFactor": 0.0,
            "roughnessFactor": 0.15,
        },
        "doubleSided": False,
    },
}


def _face_normal(a: Point3D, b: Point3D, c: Point3D) -> Point3D:
    ux, uy, uz = b[0] - a[0], b[1] - a[1], b[2] - a[2]
    vx, vy, vz = c[0] - a[0], c[1] - a[1], c[2] - a[2]
    nx = uy * vz - uz * vy
    ny = uz * vx - ux * vz
    nz = ux * vy - uy * vx
    mag = math.sqrt(nx * nx + ny * ny + nz * nz)
    if mag == 0:
        return (0.0, 0.0, 1.0)
    return nx / mag, ny / mag, nz / mag


def write_svg(
    plan: PlanGeometry,
    output_path: Path,
    include_labels: bool = True,
    include_courtyard: bool = True,
    config: Dict[str, float] | None = None,
    metrics: Dict[str, object] | None = None,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    all_points: List[Point2D] = (
        plan.master_triangle
        + plan.hex_vertices
        + (plan.courtyard_polygon if include_courtyard else [])
        + [pt for wing in plan.wing_polygons.values() for pt in wing]
    )
    min_x = min(p[0] for p in all_points)
    max_x = max(p[0] for p in all_points)
    min_y = min(p[1] for p in all_points)
    max_y = max(p[1] for p in all_points)

    scale = 8.0
    margin = 40.0
    legend_panel_w = 380 if include_labels else 0
    width = int((max_x - min_x) * scale + margin * 2 + legend_panel_w)
    height = int((max_y - min_y) * scale + margin * 2)

    def tx(pt: Point2D) -> Point2D:
        return ((pt[0] - min_x) * scale + margin, (max_y - pt[1]) * scale + margin)

    def svg_points(points: Iterable[Point2D]) -> str:
        return " ".join(f"{x:.2f},{y:.2f}" for x, y in (tx(p) for p in points))

    def label_point(points: List[Point2D]) -> Point2D:
        c = Polygon(points).centroid
        return tx((c.x, c.y))

    lines: List[str] = [
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?>",
        f"<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"{width}\" height=\"{height}\" viewBox=\"0 0 {width} {height}\">",
        "  <defs>",
        "    <marker id=\"arrow\" markerWidth=\"8\" markerHeight=\"8\" refX=\"4\" refY=\"4\" orient=\"auto\">",
        "      <path d=\"M0,0 L8,4 L0,8 Z\" fill=\"#2d2d2d\"/>",
        "    </marker>",
        "  </defs>",
        "  <rect x=\"0\" y=\"0\" width=\"100%\" height=\"100%\" fill=\"#ffffff\"/>",
    ]

    wing_colors = {"A": "#dbe6f4", "B": "#c8dbf0", "C": "#dbe6f4"}
    for wing_name in ("A", "B", "C"):
        lines.append(
            f"  <polygon points=\"{svg_points(plan.wing_polygons[wing_name])}\" "
            f"fill=\"{wing_colors[wing_name]}\" stroke=\"#304d6d\" stroke-width=\"1.5\"/>"
        )

    lines.append(
        f"  <polygon points=\"{svg_points(plan.hex_vertices)}\" fill=\"#f1f8ff\" stroke=\"#2f4f6f\" stroke-width=\"1.8\"/>"
    )
    if include_courtyard:
        lines.append(
            f"  <polygon points=\"{svg_points(plan.courtyard_polygon)}\" fill=\"#ececec\" stroke=\"#777777\" stroke-width=\"1.4\"/>"
        )
    lines.append(
        f"  <polygon points=\"{svg_points(plan.master_triangle)}\" fill=\"none\" stroke=\"#214d1f\" stroke-width=\"2.2\"/>"
    )

    def _distance(a: Point2D, b: Point2D) -> float:
        return math.hypot(a[0] - b[0], a[1] - b[1])

    def _draw_dimension(
        p0: Point2D,
        p1: Point2D,
        anchor: Point2D,
        offset_ft: float,
        label: str,
        color: str = "#2d2d2d",
        dashed: bool = False,
    ) -> None:
        ex, ey = p1[0] - p0[0], p1[1] - p0[1]
        mag = max(math.hypot(ex, ey), 1e-9)
        nx1, ny1 = ey / mag, -ex / mag
        nx2, ny2 = -ey / mag, ex / mag
        mx, my = (p0[0] + p1[0]) * 0.5, (p0[1] + p1[1]) * 0.5
        ax, ay = anchor[0] - mx, anchor[1] - my
        nx, ny = (nx1, ny1) if (nx1 * ax + ny1 * ay) > (nx2 * ax + ny2 * ay) else (nx2, ny2)
        q0 = (p0[0] + nx * offset_ft, p0[1] + ny * offset_ft)
        q1 = (p1[0] + nx * offset_ft, p1[1] + ny * offset_ft)
        s0x, s0y = tx(p0)
        s1x, s1y = tx(p1)
        q0x, q0y = tx(q0)
        q1x, q1y = tx(q1)
        dash = ' stroke-dasharray="4,4"' if dashed else ""
        lines.append(f"  <line x1=\"{s0x:.2f}\" y1=\"{s0y:.2f}\" x2=\"{q0x:.2f}\" y2=\"{q0y:.2f}\" stroke=\"{color}\" stroke-width=\"1\"{dash}/>")
        lines.append(f"  <line x1=\"{s1x:.2f}\" y1=\"{s1y:.2f}\" x2=\"{q1x:.2f}\" y2=\"{q1y:.2f}\" stroke=\"{color}\" stroke-width=\"1\"{dash}/>")
        lines.append(
            f"  <line x1=\"{q0x:.2f}\" y1=\"{q0y:.2f}\" x2=\"{q1x:.2f}\" y2=\"{q1y:.2f}\" stroke=\"{color}\" stroke-width=\"1.2\" marker-start=\"url(#arrow)\" marker-end=\"url(#arrow)\"{dash}/>"
        )
        lx, ly = (q0x + q1x) * 0.5, (q0y + q1y) * 0.5
        lines.append(
            f"  <text x=\"{lx:.2f}\" y=\"{ly - 6:.2f}\" text-anchor=\"middle\" style=\"font-family:Arial,sans-serif;font-size:12px;fill:{color};paint-order:stroke;stroke:#ffffff;stroke-width:3px\">{label}</text>"
        )

    hex_centroid = Polygon(plan.hex_vertices).centroid
    hex_c = (hex_centroid.x, hex_centroid.y)
    for i in range(len(plan.hex_vertices)):
        p0 = plan.hex_vertices[i]
        p1 = plan.hex_vertices[(i + 1) % len(plan.hex_vertices)]
        _draw_dimension(p0, p1, hex_c, 3.0, f"{_distance(p0, p1):.1f} ft", color="#4b5f72")

    tri_centroid = Polygon(plan.master_triangle).centroid
    tri_c = (tri_centroid.x, tri_centroid.y)
    for i in range(len(plan.master_triangle)):
        p0 = plan.master_triangle[i]
        p1 = plan.master_triangle[(i + 1) % len(plan.master_triangle)]
        _draw_dimension(p0, p1, tri_c, 4.0, f"{_distance(p0, p1):.1f} ft", color="#2a5727")

    triangle_boundary = Polygon(plan.master_triangle).boundary
    for i, hv in enumerate(plan.hex_vertices):
        s = triangle_boundary.project(Point(hv))
        np = triangle_boundary.interpolate(s)
        np_pt = (np.x, np.y)
        d = _distance(hv, np_pt)
        if d < 1e-3:
            continue
        _draw_dimension(hv, np_pt, hex_c, 1.8 + (i % 2) * 0.8, f"{d:.1f} ft", color="#7a2f2f", dashed=True)

    if include_labels:
        style = "font-family:Arial,sans-serif;font-size:14px;fill:#1f1f1f"
        ax, ay = label_point(plan.wing_polygons["A"])
        bx, by = label_point(plan.wing_polygons["B"])
        cx, cy = label_point(plan.wing_polygons["C"])
        atrium_centroid = Polygon(plan.hex_vertices).centroid
        triangle_centroid = Polygon(plan.master_triangle).centroid
        hx, hy = tx((atrium_centroid.x, atrium_centroid.y))
        txp, typ = tx((triangle_centroid.x, triangle_centroid.y))

        dx = txp - hx
        dy = typ - hy
        sep = math.hypot(dx, dy)
        min_sep_px = 36.0
        if sep < min_sep_px:
            shift = (min_sep_px - sep) * 0.6 if sep > 1e-6 else min_sep_px * 0.6
            ux, uy = (dx / sep, dy / sep) if sep > 1e-6 else (0.0, -1.0)
            txp += ux * shift
            typ += uy * shift
            hx -= ux * shift * 0.5
            hy -= uy * shift * 0.5
        lines.extend(
            [
                f"  <text x=\"{ax:.2f}\" y=\"{ay:.2f}\" style=\"{style}\" text-anchor=\"middle\">Wing A</text>",
                f"  <text x=\"{bx:.2f}\" y=\"{by:.2f}\" style=\"{style}\" text-anchor=\"middle\">Wing B</text>",
                f"  <text x=\"{cx:.2f}\" y=\"{cy:.2f}\" style=\"{style}\" text-anchor=\"middle\">Wing C</text>",
                f"  <text x=\"{hx:.2f}\" y=\"{hy:.2f}\" style=\"{style}\" text-anchor=\"middle\">Atrium</text>",
                f"  <text x=\"{txp:.2f}\" y=\"{typ:.2f}\" style=\"{style}\" text-anchor=\"middle\">Master Triangle</text>",
            ]
        )
        if include_courtyard:
            qx, qy = label_point(plan.courtyard_polygon)
            lines.append(f"  <text x=\"{qx:.2f}\" y=\"{qy:.2f}\" style=\"{style}\" text-anchor=\"middle\">Courtyard</text>")

        area_atrium = Polygon(plan.hex_vertices).area
        area_triangle = Polygon(plan.master_triangle).area
        area_wings = {name: Polygon(poly).area for name, poly in plan.wing_polygons.items()}
        area_courtyard = Polygon(plan.courtyard_polygon).area if include_courtyard else 0.0
        if metrics is not None and isinstance(metrics.get("areas"), dict):
            areas = metrics["areas"]
            area_atrium = float(areas.get("atrium", area_atrium))
            area_triangle = float(areas.get("master_triangle", area_triangle))
            area_wings["A"] = float(areas.get("wing_A", area_wings["A"]))
            area_wings["B"] = float(areas.get("wing_B", area_wings["B"]))
            area_wings["C"] = float(areas.get("wing_C", area_wings["C"]))
            area_courtyard = float(areas.get("courtyard", area_courtyard))
        total_plan_area = area_atrium + area_wings["A"] + area_wings["B"] + area_wings["C"] + area_triangle
        room_areas = {"A": 0.0, "B": 0.0, "C": 0.0}
        if metrics is not None and isinstance(metrics.get("triangle_room_areas"), dict):
            room_areas["A"] = float(metrics["triangle_room_areas"].get("room_A", 0.0))
            room_areas["B"] = float(metrics["triangle_room_areas"].get("room_B", 0.0))
            room_areas["C"] = float(metrics["triangle_room_areas"].get("room_C", 0.0))

        cfg = config or {}
        ceiling_h = float(cfg.get("ceiling_height", 12.0))
        slab_h = float(cfg.get("slab_thickness", 1.0))
        upper_ground = float(cfg.get("upper_ground", 13.0))
        lower_ground = float(cfg.get("lower_ground", 0.0))
        tri_elev = float(cfg.get("master_triangle_elevation", upper_ground + ceiling_h))
        atrium_floor = float(cfg.get("atrium_floor", -2.0))
        atrium_roof_base = float(cfg.get("atrium_roof_base", 43.0))
        atrium_roof_apex = atrium_roof_base + float(cfg.get("atrium_roof_rise", 6.0))

        legend_lines = [
            "Legend",
            f"Atrium area: {area_atrium:.1f} sf",
            f"Wing A area: {area_wings['A']:.1f} sf",
            f"Wing B area: {area_wings['B']:.1f} sf",
            f"Wing C area: {area_wings['C']:.1f} sf",
            f"Master triangle area: {area_triangle:.1f} sf",
            f"Triangle room A: {room_areas['A']:.1f} sf",
            f"Triangle room B: {room_areas['B']:.1f} sf",
            f"Triangle room C: {room_areas['C']:.1f} sf",
            f"Total plan area: {total_plan_area:.1f} sf",
            f"Courtyard area: {area_courtyard:.1f} sf",
            "Rotation preserves triangle area.",
            f"Ceiling height: {ceiling_h:.1f} ft",
            f"Slab thickness: {slab_h:.1f} ft",
            f"Upper ground: {upper_ground:.1f} ft",
            f"Lower ground: {lower_ground:.1f} ft",
            f"Triangle level base: {tri_elev:.1f} ft",
            f"Atrium floor: {atrium_floor:.1f} ft",
            f"Atrium roof: {atrium_roof_base:.1f} to {atrium_roof_apex:.1f} ft",
            "Dims shown:",
            "- Hex + triangle edge lengths",
            "- Atrium-to-triangle clearances",
        ]
        legend_x = width - legend_panel_w + 16
        legend_y = 20
        line_h = 17
        box_h = line_h * len(legend_lines) + 16
        lines.append(
            f"  <rect x=\"{legend_x - 8}\" y=\"{legend_y - 14}\" width=\"{legend_panel_w - 24}\" height=\"{box_h}\" fill=\"#f9fbff\" stroke=\"#b7c6d8\" stroke-width=\"1.2\" rx=\"6\" ry=\"6\"/>"
        )
        for i, text in enumerate(legend_lines):
            weight = "700" if i == 0 else "400"
            size = "14px" if i == 0 else "13px"
            lines.append(
                f"  <text x=\"{legend_x:.2f}\" y=\"{legend_y + i * line_h:.2f}\" style=\"font-family:Arial,sans-serif;font-size:{size};font-weight:{weight};fill:#1f2a36\">{text}</text>"
            )

    lines.append("</svg>")
    output_path.write_text("\n".join(lines), encoding="utf-8")


def _rotate_x(point: Point3D, degrees: float) -> Point3D:
    if abs(degrees) < 1e-9:
        return point
    r = math.radians(degrees)
    c = math.cos(r)
    s = math.sin(r)
    x, y, z = point
    return (x, y * c - z * s, y * s + z * c)


def write_glb(model: ModelData, output_path: Path, rotate_x_deg: float = 0.0, feet_to_meters: bool = True) -> None:
    """Export model as GLB. If feet_to_meters is True, scale all geometry by 0.3048."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    _scale = 0.3048 if feet_to_meters else 1.0

    component_map = model.triangles_by_component or {}
    if not component_map:
        component_map = {"model": model.triangles_by_material}

    material_order = [m for m in ("glass", "concrete", "ground", "marble")]
    for comp_data in component_map.values():
        for material_name in comp_data:
            if material_name not in material_order:
                material_order.append(material_name)
    material_order = [m for m in material_order if any(comp_data.get(m) for comp_data in component_map.values())]
    if not material_order:
        raise ValueError("No geometry found to export.")

    material_to_index = {name: i for i, name in enumerate(material_order)}

    binary = bytearray()
    buffer_views: List[Dict[str, object]] = []
    accessors: List[Dict[str, object]] = []
    meshes: List[Dict[str, object]] = []
    nodes: List[Dict[str, object]] = []

    def append_blob(data: bytes, target: int | None = None) -> int:
        offset = len(binary)
        binary.extend(data)
        while len(binary) % 4:
            binary.append(0)
        view: Dict[str, object] = {
            "buffer": 0,
            "byteOffset": offset,
            "byteLength": len(data),
        }
        if target is not None:
            view["target"] = target
        buffer_views.append(view)
        return len(buffer_views) - 1

    def add_accessor(
        buffer_view: int,
        component_type: int,
        count: int,
        value_type: str,
        min_vals: List[float] | None = None,
        max_vals: List[float] | None = None,
    ) -> int:
        accessor: Dict[str, object] = {
            "bufferView": buffer_view,
            "componentType": component_type,
            "count": count,
            "type": value_type,
        }
        if min_vals is not None:
            accessor["min"] = min_vals
        if max_vals is not None:
            accessor["max"] = max_vals
        accessors.append(accessor)
        return len(accessors) - 1

    sorted_components = sorted(component_map.keys())
    for component_name in sorted_components:
        comp_materials = component_map[component_name]
        primitives: List[Dict[str, object]] = []

        for material_name in material_order:
            triangles = comp_materials.get(material_name, [])
            if not triangles:
                continue

            positions: List[Point3D] = []
            normals: List[Point3D] = []
            indices: List[int] = []
            cursor = 0

            for tri in triangles:
                a, b, c = tri
                if rotate_x_deg:
                    a = _rotate_x(a, rotate_x_deg)
                    b = _rotate_x(b, rotate_x_deg)
                    c = _rotate_x(c, rotate_x_deg)
                if _scale != 1.0:
                    a = (a[0] * _scale, a[1] * _scale, a[2] * _scale)
                    b = (b[0] * _scale, b[1] * _scale, b[2] * _scale)
                    c = (c[0] * _scale, c[1] * _scale, c[2] * _scale)
                n = _face_normal(a, b, c)
                positions.extend((a, b, c))
                normals.extend((n, n, n))
                indices.extend((cursor, cursor + 1, cursor + 2))
                cursor += 3

            pos_arr = np.asarray(positions, dtype=np.float32)
            nrm_arr = np.asarray(normals, dtype=np.float32)
            idx_arr = np.asarray(indices, dtype=np.uint32)

            pos_view = append_blob(pos_arr.tobytes(), target=34962)
            nrm_view = append_blob(nrm_arr.tobytes(), target=34962)
            idx_view = append_blob(idx_arr.tobytes(), target=34963)

            pos_accessor = add_accessor(
                pos_view,
                component_type=5126,
                count=pos_arr.shape[0],
                value_type="VEC3",
                min_vals=[float(v) for v in np.min(pos_arr, axis=0)],
                max_vals=[float(v) for v in np.max(pos_arr, axis=0)],
            )
            nrm_accessor = add_accessor(
                nrm_view,
                component_type=5126,
                count=nrm_arr.shape[0],
                value_type="VEC3",
            )
            idx_accessor = add_accessor(
                idx_view,
                component_type=5125,
                count=idx_arr.shape[0],
                value_type="SCALAR",
            )

            primitives.append(
                {
                    "attributes": {
                        "POSITION": pos_accessor,
                        "NORMAL": nrm_accessor,
                    },
                    "indices": idx_accessor,
                    "material": material_to_index[material_name],
                }
            )

        if primitives:
            mesh_index = len(meshes)
            meshes.append({"name": component_name, "primitives": primitives})
            nodes.append({"mesh": mesh_index, "name": component_name})

    gltf = {
        "asset": {"version": "2.0", "generator": "exploded-hexagon-home/src.export.py"},
        "scene": 0,
        "scenes": [{"nodes": list(range(len(nodes)))}],
        "nodes": nodes,
        "meshes": meshes,
        "materials": [MATERIALS.get(name, MATERIALS["concrete"]) for name in material_order],
        "buffers": [{"byteLength": len(binary)}],
        "bufferViews": buffer_views,
        "accessors": accessors,
    }

    json_chunk = json.dumps(gltf, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    while len(json_chunk) % 4:
        json_chunk += b" "

    bin_chunk = bytes(binary)
    while len(bin_chunk) % 4:
        bin_chunk += b"\x00"

    total_len = 12 + 8 + len(json_chunk) + 8 + len(bin_chunk)
    with output_path.open("wb") as fh:
        fh.write(struct.pack("<4sII", b"glTF", 2, total_len))
        fh.write(struct.pack("<I4s", len(json_chunk), b"JSON"))
        fh.write(json_chunk)
        fh.write(struct.pack("<I4s", len(bin_chunk), b"BIN\x00"))
        fh.write(bin_chunk)

