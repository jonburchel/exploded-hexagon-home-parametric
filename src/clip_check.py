"""Comprehensive clipping / bounds check for all scene objects.

Run inside Blender via:
    .\\Send-Blender.ps1 -File src\\clip_check.py
"""

import math
import bpy
import mathutils

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
FT = 0.3048  # feet to meters

S_FT = 23.0         # hex side length in feet
D_FT = 7.0          # atrium-to-triangle clearance in feet
S = S_FT * FT       # hex side in meters
D = D_FT * FT       # clearance in meters
MARGIN = 0.5 * FT   # 0.5 ft inward margin for fixes

# Object name patterns
PLANT_KEYWORDS = ("Plant", "Palm", "Bush", "Fern", "Tree")
FURNITURE_KEYWORDS = (
    "Bed", "Chair", "Table", "Nightstand", "Lamp",
    "Rug", "Pillow", "Headboard", "Sofa",
)

# ---------------------------------------------------------------------------
# 2D geometry helpers (all in meters, XY plane)
# ---------------------------------------------------------------------------

def _hex_vertices(s):
    """Flat-top hex vertices CCW, centered at origin."""
    return [(s * math.cos(math.radians(i * 60)),
             s * math.sin(math.radians(i * 60))) for i in range(6)]


def _unit(vx, vy):
    mag = math.hypot(vx, vy)
    if mag < 1e-12:
        return (0.0, 0.0)
    return (vx / mag, vy / mag)


def _offset_edge_line(p0, p1, center, offset):
    """Offset an edge outward (away from center) by *offset*."""
    ex, ey = p1[0] - p0[0], p1[1] - p0[1]
    midpoint = ((p0[0] + p1[0]) * 0.5, (p0[1] + p1[1]) * 0.5)
    to_mid = (midpoint[0] - center[0], midpoint[1] - center[1])
    n1 = _unit(ey, -ex)
    n2 = _unit(-ey, ex)
    dot1 = n1[0] * to_mid[0] + n1[1] * to_mid[1]
    dot2 = n2[0] * to_mid[0] + n2[1] * to_mid[1]
    n = n1 if dot1 > dot2 else n2
    ox, oy = n[0] * offset, n[1] * offset
    return ((p0[0] + ox, p0[1] + oy), (p1[0] + ox, p1[1] + oy))


def _line_intersect(a0, a1, b0, b1):
    x1, y1 = a0;  x2, y2 = a1
    x3, y3 = b0;  x4, y4 = b1
    den = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
    if abs(den) < 1e-12:
        return None
    da = x1 * y2 - y1 * x2
    db = x3 * y4 - y3 * x4
    return ((da * (x3 - x4) - (x1 - x2) * db) / den,
            (da * (y3 - y4) - (y1 - y2) * db) / den)


def _rotate_point(pt, center, angle):
    px, py = pt[0] - center[0], pt[1] - center[1]
    c, s = math.cos(angle), math.sin(angle)
    return (center[0] + c * px - s * py, center[1] + s * px + c * py)


def _dist_point_to_line(pt, la, lb):
    ux, uy = lb[0] - la[0], lb[1] - la[1]
    vx, vy = pt[0] - la[0], pt[1] - la[1]
    return abs(ux * vy - uy * vx) / max(math.hypot(ux, uy), 1e-12)


def _ensure_ccw(pts):
    area = sum(pts[i][0] * pts[(i + 1) % len(pts)][1] -
               pts[(i + 1) % len(pts)][0] * pts[i][1] for i in range(len(pts)))
    return list(reversed(pts)) if area < 0 else pts


def _point_in_convex_polygon(px, py, poly):
    """True if (px, py) is inside the convex polygon (CCW winding)."""
    n = len(poly)
    for i in range(n):
        x0, y0 = poly[i]
        x1, y1 = poly[(i + 1) % n]
        cross = (x1 - x0) * (py - y0) - (y1 - y0) * (px - x0)
        if cross < -1e-6:
            return False
    return True


def _signed_dist_to_edge(px, py, e0, e1):
    """Signed distance from point to directed edge. Positive = left of edge."""
    ux, uy = e1[0] - e0[0], e1[1] - e0[1]
    vx, vy = px - e0[0], py - e0[1]
    return (ux * vy - uy * vx) / max(math.hypot(ux, uy), 1e-12)


# ---------------------------------------------------------------------------
# Build boundary geometry (in meters, matching GLB coordinate space)
# ---------------------------------------------------------------------------

TRIANGLE_EDGE_INDICES = ((1, 2), (3, 4), (5, 0))
WING_EDGE_INDICES = {"A": (5, 0), "B": (3, 4), "C": (1, 2)}

hex_verts = _hex_vertices(S)
hex_verts = _ensure_ccw(hex_verts)

# Extension vertices (wing tips)
ext_verts = []
for vx, vy in hex_verts:
    ux, uy = _unit(vx, vy)
    ext_verts.append((vx + ux * S, vy + uy * S))

# Wing polygons (CCW)
wing_polys = {}
for name, (i0, i1) in WING_EDGE_INDICES.items():
    wing_polys[name] = _ensure_ccw([
        hex_verts[i0], hex_verts[i1],
        ext_verts[i1], ext_verts[i0],
    ])

# Master triangle
center = (0.0, 0.0)
offset_lines = []
for i0, i1 in TRIANGLE_EDGE_INDICES:
    offset_lines.append(_offset_edge_line(hex_verts[i0], hex_verts[i1], center, D))

top = _line_intersect(offset_lines[0][0], offset_lines[0][1],
                      offset_lines[1][0], offset_lines[1][1])
left = _line_intersect(offset_lines[1][0], offset_lines[1][1],
                       offset_lines[2][0], offset_lines[2][1])
right = _line_intersect(offset_lines[2][0], offset_lines[2][1],
                        offset_lines[0][0], offset_lines[0][1])
master_tri = _ensure_ccw([right, top, left])

# Apply same rotation as plan.py (align back edge to Wing C extension vertex)
tri_center = (sum(p[0] for p in master_tri) / 3.0,
              sum(p[1] for p in master_tri) / 3.0)
wing_c_top_right = ext_verts[1]
step = (2.0 * math.pi) / 7200.0
best_angle = 0.0
best_dist = float("inf")
for k in range(1, 7201):
    angle = k * step
    ra = _rotate_point(master_tri[0], tri_center, angle)
    rb = _rotate_point(master_tri[1], tri_center, angle)
    rc = _rotate_point(master_tri[2], tri_center, angle)
    for i in range(3):
        pts = [ra, rb, rc]
        ea, eb = pts[i], pts[(i + 1) % 3]
        dist = _dist_point_to_line(wing_c_top_right, ea, eb)
        if dist < best_dist:
            best_dist = dist
            best_angle = angle
    if best_dist <= 1e-3:
        break

# Refine with ternary search
lo, hi = max(0.0, best_angle - step), best_angle + step
for _ in range(40):
    m1 = lo + (hi - lo) / 3.0
    m2 = hi - (hi - lo) / 3.0
    pts1 = [_rotate_point(p, tri_center, m1) for p in master_tri]
    pts2 = [_rotate_point(p, tri_center, m2) for p in master_tri]
    d1 = min(_dist_point_to_line(wing_c_top_right, pts1[i], pts1[(i + 1) % 3]) for i in range(3))
    d2 = min(_dist_point_to_line(wing_c_top_right, pts2[i], pts2[(i + 1) % 3]) for i in range(3))
    if d1 <= d2:
        hi = m2
    else:
        lo = m1
best_angle = (lo + hi) * 0.5

master_tri = _ensure_ccw([_rotate_point(p, tri_center, best_angle) for p in master_tri])

# Apply down-shift (1 ft)
DOWN_SHIFT = 1.0 * FT
master_tri = _ensure_ccw([(p[0], p[1] - DOWN_SHIFT) for p in master_tri])

# Hex polygon for atrium checks
hex_poly = hex_verts  # already CCW

# ---------------------------------------------------------------------------
# Bounding box utilities
# ---------------------------------------------------------------------------

def get_world_bbox(obj):
    """Return (min_x, max_x, min_y, max_y, min_z, max_z) in world space."""
    bbox = [obj.matrix_world @ mathutils.Vector(corner) for corner in obj.bound_box]
    return (
        min(v.x for v in bbox), max(v.x for v in bbox),
        min(v.y for v in bbox), max(v.y for v in bbox),
        min(v.z for v in bbox), max(v.z for v in bbox),
    )


def bbox_center_xy(bbox):
    """Return (cx, cy) of an AABB tuple."""
    return ((bbox[0] + bbox[1]) * 0.5, (bbox[2] + bbox[3]) * 0.5)


def bbox_corners_xy(bbox):
    """Return the four XY corners of the AABB."""
    return [
        (bbox[0], bbox[2]),
        (bbox[1], bbox[2]),
        (bbox[1], bbox[3]),
        (bbox[0], bbox[3]),
    ]


# ---------------------------------------------------------------------------
# Boundary containment checks
# ---------------------------------------------------------------------------

def max_overlap_outside_polygon(bbox, poly):
    """How far (meters) the AABB extends beyond the convex polygon.

    Returns (overlap_distance, direction_vector) or (0, None) if fully inside.
    """
    corners = bbox_corners_xy(bbox)
    max_penetration = 0.0
    worst_dir = None
    n = len(poly)
    for cx, cy in corners:
        for i in range(n):
            e0 = poly[i]
            e1 = poly[(i + 1) % n]
            sd = _signed_dist_to_edge(cx, cy, e0, e1)
            if sd < -1e-6:
                penetration = abs(sd)
                if penetration > max_penetration:
                    max_penetration = penetration
                    # inward normal of edge
                    ex, ey = e1[0] - e0[0], e1[1] - e0[1]
                    mag = max(math.hypot(ex, ey), 1e-12)
                    worst_dir = (ey / mag, -ex / mag)  # points inward
    return max_penetration, worst_dir


def find_containing_zone(cx, cy):
    """Identify which building zone a point is in: 'atrium', 'wing_X', 'triangle', or None."""
    if _point_in_convex_polygon(cx, cy, hex_poly):
        return "atrium"
    for name, poly in wing_polys.items():
        if _point_in_convex_polygon(cx, cy, poly):
            return f"wing_{name}"
    if _point_in_convex_polygon(cx, cy, master_tri):
        return "triangle"
    return None


# ---------------------------------------------------------------------------
# Issue detection and fixing
# ---------------------------------------------------------------------------

def classify_object(name):
    """Return 'plant', 'furniture', or None."""
    for kw in PLANT_KEYWORDS:
        if kw.lower() in name.lower():
            return "plant"
    for kw in FURNITURE_KEYWORDS:
        if kw.lower() in name.lower():
            return "furniture"
    return None


def check_plant(obj):
    """Check a plant/tree object for wall clipping. Returns list of issues."""
    issues = []
    bbox = get_world_bbox(obj)
    cx, cy = bbox_center_xy(bbox)
    zone = find_containing_zone(cx, cy)

    if zone == "atrium":
        # Should stay inside the hex
        overlap, direction = max_overlap_outside_polygon(bbox, hex_poly)
        if overlap > 1e-4:
            issues.append({
                "type": "plant_outside_hex",
                "object": obj.name,
                "zone": "atrium",
                "overlap_m": overlap,
                "overlap_ft": overlap / FT,
                "direction": direction,
            })
    elif zone and zone.startswith("wing_"):
        wing_name = zone.split("_")[1]
        poly = wing_polys[wing_name]
        overlap, direction = max_overlap_outside_polygon(bbox, poly)
        if overlap > 1e-4:
            issues.append({
                "type": "plant_outside_wing",
                "object": obj.name,
                "zone": zone,
                "overlap_m": overlap,
                "overlap_ft": overlap / FT,
                "direction": direction,
            })
    else:
        # Check against master triangle
        overlap, direction = max_overlap_outside_polygon(bbox, master_tri)
        if overlap > 1e-4:
            issues.append({
                "type": "plant_outside_building",
                "object": obj.name,
                "zone": "outside" if zone is None else zone,
                "overlap_m": overlap,
                "overlap_ft": overlap / FT,
                "direction": direction,
            })

    return issues


def check_furniture(obj):
    """Check furniture for wall/floor/ceiling clipping. Returns list of issues."""
    issues = []
    bbox = get_world_bbox(obj)
    cx, cy = bbox_center_xy(bbox)
    zone = find_containing_zone(cx, cy)

    # Wall clipping check
    if zone == "atrium":
        overlap, direction = max_overlap_outside_polygon(bbox, hex_poly)
        if overlap > 1e-4:
            issues.append({
                "type": "furniture_wall_clip",
                "object": obj.name,
                "zone": "atrium",
                "overlap_m": overlap,
                "overlap_ft": overlap / FT,
                "direction": direction,
            })
    elif zone and zone.startswith("wing_"):
        wing_name = zone.split("_")[1]
        poly = wing_polys[wing_name]
        overlap, direction = max_overlap_outside_polygon(bbox, poly)
        if overlap > 1e-4:
            issues.append({
                "type": "furniture_wall_clip",
                "object": obj.name,
                "zone": zone,
                "overlap_m": overlap,
                "overlap_ft": overlap / FT,
                "direction": direction,
            })
    elif zone == "triangle":
        overlap, direction = max_overlap_outside_polygon(bbox, master_tri)
        if overlap > 1e-4:
            issues.append({
                "type": "furniture_wall_clip",
                "object": obj.name,
                "zone": "triangle",
                "overlap_m": overlap,
                "overlap_ft": overlap / FT,
                "direction": direction,
            })

    # Floor/ceiling clipping (basic Z-range check)
    min_z, max_z = bbox[4], bbox[5]
    if min_z < -3.0 * FT:  # more than 3 ft below ground is suspect
        issues.append({
            "type": "furniture_floor_clip",
            "object": obj.name,
            "zone": zone or "unknown",
            "overlap_m": abs(min_z + 3.0 * FT),
            "overlap_ft": abs(min_z + 3.0 * FT) / FT,
            "direction": None,
        })
    # Ceiling check: atrium roof ~43 ft, wings ~25 ft
    ceiling_z = 43.0 * FT if zone == "atrium" else 25.0 * FT
    if max_z > ceiling_z:
        issues.append({
            "type": "furniture_ceiling_clip",
            "object": obj.name,
            "zone": zone or "unknown",
            "overlap_m": max_z - ceiling_z,
            "overlap_ft": (max_z - ceiling_z) / FT,
            "direction": None,
        })

    return issues


def fix_issue(issue):
    """Attempt to fix a detected clipping issue. Returns description of fix or None."""
    obj = bpy.data.objects.get(issue["object"])
    if obj is None:
        return None

    overlap = issue["overlap_m"]
    direction = issue.get("direction")
    itype = issue["type"]

    if itype in ("plant_outside_hex", "plant_outside_wing", "plant_outside_building"):
        if direction:
            # Move inward by overlap + margin
            shift = overlap + MARGIN
            obj.location.x += direction[0] * shift
            obj.location.y += direction[1] * shift
            return (f"Moved {obj.name} inward by {shift / FT:.1f} ft "
                    f"(direction {direction[0]:.2f}, {direction[1]:.2f})")
        else:
            # Scale down to fit
            bbox = get_world_bbox(obj)
            w = bbox[1] - bbox[0]
            h = bbox[3] - bbox[2]
            max_dim = max(w, h, 1e-6)
            safe_dim = max_dim - 2 * overlap
            if safe_dim > 0:
                factor = safe_dim / max_dim
                obj.scale *= factor
                return f"Scaled {obj.name} by {factor:.2f} to fit boundary"
            return None

    elif itype == "furniture_wall_clip":
        if direction:
            shift = overlap + MARGIN
            obj.location.x += direction[0] * shift
            obj.location.y += direction[1] * shift
            return (f"Moved {obj.name} inward by {shift / FT:.1f} ft "
                    f"to clear wall")
        return None

    elif itype == "furniture_floor_clip":
        obj.location.z += overlap
        return f"Raised {obj.name} by {overlap / FT:.1f} ft to clear floor"

    elif itype == "furniture_ceiling_clip":
        obj.location.z -= overlap + MARGIN
        return f"Lowered {obj.name} by {(overlap + MARGIN) / FT:.1f} ft to clear ceiling"

    return None


# ---------------------------------------------------------------------------
# Main scan
# ---------------------------------------------------------------------------

def run_clip_check():
    print("\n" + "=" * 70)
    print("  CLIP CHECK: Scanning all objects for boundary violations")
    print("=" * 70)

    # Print boundary info
    print(f"\nBuilding parameters: s = {S_FT} ft ({S:.3f} m), d = {D_FT} ft ({D:.3f} m)")
    print(f"Master triangle vertices (m):")
    for i, v in enumerate(master_tri):
        print(f"  T{i}: ({v[0]:.3f}, {v[1]:.3f})")
    print(f"Hex vertices (m):")
    for i, v in enumerate(hex_verts):
        print(f"  H{i}: ({v[0]:.3f}, {v[1]:.3f})")

    all_issues = []
    checked = []
    fixes = []

    mesh_objects = [o for o in bpy.data.objects if o.type == 'MESH']
    print(f"\nTotal mesh objects in scene: {len(mesh_objects)}")

    # Scan plants
    print("\n--- Checking plants/trees ---")
    plant_count = 0
    for obj in mesh_objects:
        cls = classify_object(obj.name)
        if cls != "plant":
            continue
        plant_count += 1
        bbox = get_world_bbox(obj)
        cx, cy = bbox_center_xy(bbox)
        zone = find_containing_zone(cx, cy)
        checked.append({"name": obj.name, "type": "plant", "zone": zone or "outside"})

        issues = check_plant(obj)
        if issues:
            for iss in issues:
                print(f"  [ISSUE] {obj.name}: {iss['type']} in {iss['zone']}, "
                      f"overlap = {iss['overlap_ft']:.2f} ft")
                all_issues.append(iss)
        else:
            print(f"  [OK]    {obj.name} (zone: {zone or 'outside'})")

    if plant_count == 0:
        print("  No plant/tree objects found.")

    # Scan furniture
    print("\n--- Checking furniture ---")
    furn_count = 0
    for obj in mesh_objects:
        cls = classify_object(obj.name)
        if cls != "furniture":
            continue
        furn_count += 1
        bbox = get_world_bbox(obj)
        cx, cy = bbox_center_xy(bbox)
        zone = find_containing_zone(cx, cy)
        checked.append({"name": obj.name, "type": "furniture", "zone": zone or "outside"})

        issues = check_furniture(obj)
        if issues:
            for iss in issues:
                print(f"  [ISSUE] {obj.name}: {iss['type']} in {iss['zone']}, "
                      f"overlap = {iss['overlap_ft']:.2f} ft")
                all_issues.append(iss)
        else:
            print(f"  [OK]    {obj.name} (zone: {zone or 'outside'})")

    if furn_count == 0:
        print("  No furniture objects found.")

    # Fix issues
    if all_issues:
        print(f"\n--- Fixing {len(all_issues)} issues ---")
        for iss in all_issues:
            result = fix_issue(iss)
            if result:
                fixes.append(result)
                print(f"  [FIXED] {result}")
            else:
                print(f"  [SKIP]  Could not auto-fix {iss['object']}: {iss['type']}")

        # Re-check after fixes
        print("\n--- Re-checking fixed objects ---")
        remaining = 0
        for iss in all_issues:
            obj = bpy.data.objects.get(iss["object"])
            if obj is None:
                continue
            cls = classify_object(obj.name)
            recheck = check_plant(obj) if cls == "plant" else check_furniture(obj)
            if recheck:
                remaining += len(recheck)
                for r in recheck:
                    print(f"  [STILL] {obj.name}: {r['type']}, "
                          f"overlap = {r['overlap_ft']:.2f} ft")
        if remaining == 0:
            print("  All issues resolved.")
        else:
            print(f"  {remaining} issue(s) remain after auto-fix.")

    # Summary
    print("\n" + "=" * 70)
    print("  SUMMARY")
    print("=" * 70)
    print(f"  Objects checked: {len(checked)}")
    print(f"    Plants/trees:  {plant_count}")
    print(f"    Furniture:     {furn_count}")
    print(f"  Issues found:    {len(all_issues)}")
    print(f"  Fixes applied:   {len(fixes)}")
    if fixes:
        print("\n  Fixes applied:")
        for f in fixes:
            print(f"    - {f}")
    print(f"\nClip check complete: {len(all_issues)} issues found, {len(fixes)} fixed")
    print("=" * 70 + "\n")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    run_clip_check()
else:
    run_clip_check()
