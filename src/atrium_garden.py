"""
Atrium garden generator: tropical plants, fountain, pathways.

Generates procedural geometry for the atrium interior:
- Central fountain with basin and water jet
- Circular clearing around the fountain
- Radial pathways from clearing to hex edges
- Tropical plants (palms, ferns, bushes) filling planting beds

Run in Blender:
  blender --background --python src/atrium_garden.py -- out/massing_s23_d7.glb out/massing_s23_d7_garden.glb
Or with live viewport:
  blender --python src/atrium_garden.py -- out/massing_s23_d7.glb
"""

import bpy
import bmesh
import sys
import os
import math
import random
from mathutils import Vector, Matrix

# ---------------------------------------------------------------------------
# Constants from plan geometry (s=23), converted to meters
# ---------------------------------------------------------------------------
FT = 0.3048  # feet to meters
HEX_S = 23.0 * FT
ATRIUM_FLOOR_Z = -2.0 * FT
SLAB_THICKNESS = 1.0 * FT
FLOOR_Z = ATRIUM_FLOOR_Z + SLAB_THICKNESS  # top of slab
ATRIUM_CENTER = Vector((0, 0, FLOOR_Z))

# Hex vertices (flat-top)
HEX_VERTS = []
for i in range(6):
    angle = math.radians(i * 60.0)
    HEX_VERTS.append(Vector((HEX_S * math.cos(angle), HEX_S * math.sin(angle), FLOOR_Z)))

# Garden layout
CLEARING_RADIUS = 8.0 * FT
FOUNTAIN_RADIUS = 3.5 * FT
PATHWAY_WIDTH = 3.0 * FT
PLANTER_INSET = 1.5 * FT

# ---------------------------------------------------------------------------
# Parse args
# ---------------------------------------------------------------------------
argv = sys.argv
args = argv[argv.index("--") + 1:] if "--" in argv else []
glb_in = args[0] if len(args) > 0 else "out/massing_s23_d7.glb"
glb_out = args[1] if len(args) > 1 else None

glb_in = os.path.abspath(glb_in)
if glb_out:
    glb_out = os.path.abspath(glb_out)

# ---------------------------------------------------------------------------
# Setup scene
# ---------------------------------------------------------------------------
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=glb_in)

# Create a garden collection
garden_col = bpy.data.collections.new("AtriumGarden")
bpy.context.scene.collection.children.link(garden_col)

random.seed(42)  # reproducible layout


# ---------------------------------------------------------------------------
# Materials
# ---------------------------------------------------------------------------
def make_material(name, color, roughness=0.5, metallic=0.0, alpha=1.0, transmission=0.0):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (*color, 1.0)
    bsdf.inputs["Roughness"].default_value = roughness
    bsdf.inputs["Metallic"].default_value = metallic
    if transmission > 0:
        bsdf.inputs["Transmission Weight"].default_value = transmission
        bsdf.inputs["IOR"].default_value = 1.33  # water
        mat.surface_render_method = 'DITHERED' if hasattr(mat, 'surface_render_method') else None
    if alpha < 1.0:
        mat.blend_method = "BLEND" if hasattr(mat, "blend_method") else None
        bsdf.inputs["Alpha"].default_value = alpha
    return mat


mat_stone = make_material("PathStone", (0.75, 0.72, 0.68), roughness=0.6)
mat_water = make_material("FountainWater", (0.15, 0.4, 0.55), roughness=0.02, alpha=0.5, transmission=0.85)
mat_fountain_stone = make_material("FountainStone", (0.82, 0.80, 0.76), roughness=0.3)
mat_trunk = make_material("PalmTrunk", (0.35, 0.22, 0.12), roughness=0.9)
mat_frond = make_material("PalmFrond", (0.15, 0.45, 0.12), roughness=0.7)
mat_bush = make_material("BushLeaf", (0.12, 0.38, 0.10), roughness=0.8)
mat_fern = make_material("FernLeaf", (0.18, 0.50, 0.15), roughness=0.75)
mat_soil = make_material("PlantingSoil", (0.22, 0.15, 0.08), roughness=0.95)


# ---------------------------------------------------------------------------
# Helper: link to garden collection
# ---------------------------------------------------------------------------
def link_to_garden(obj):
    garden_col.objects.link(obj)


# ---------------------------------------------------------------------------
# Fountain
# ---------------------------------------------------------------------------
def create_fountain():
    """Central fountain: stone basin ring with water surface and column."""
    # Basin: torus ring
    bpy.ops.mesh.primitive_torus_add(
        major_radius=FOUNTAIN_RADIUS,
        minor_radius=0.6 * FT,
        location=(0, 0, FLOOR_Z + 0.6 * FT),
        major_segments=32, minor_segments=12
    )
    basin = bpy.context.active_object
    basin.name = "FountainBasin"
    basin.data.materials.append(mat_fountain_stone)
    bpy.context.scene.collection.objects.unlink(basin)
    link_to_garden(basin)

    # Inner basin wall (shorter cylinder)
    bpy.ops.mesh.primitive_cylinder_add(
        radius=FOUNTAIN_RADIUS - 0.3 * FT, depth=1.0 * FT,
        location=(0, 0, FLOOR_Z + 0.5 * FT),
        vertices=32
    )
    inner = bpy.context.active_object
    inner.name = "FountainInner"
    inner.data.materials.append(mat_fountain_stone)
    bpy.context.scene.collection.objects.unlink(inner)
    link_to_garden(inner)

    # Water surface inside basin
    bpy.ops.mesh.primitive_circle_add(
        radius=FOUNTAIN_RADIUS - 0.5 * FT,
        location=(0, 0, FLOOR_Z + 0.9 * FT),
        vertices=32, fill_type='NGON'
    )
    water = bpy.context.active_object
    water.name = "FountainWater"
    water.data.materials.append(mat_water)
    bpy.context.scene.collection.objects.unlink(water)
    link_to_garden(water)

    # Central column/spout
    bpy.ops.mesh.primitive_cylinder_add(
        radius=0.3 * FT, depth=4.0 * FT,
        location=(0, 0, FLOOR_Z + 2.5 * FT),
        vertices=16
    )
    spout = bpy.context.active_object
    spout.name = "FountainSpout"
    spout.data.materials.append(mat_fountain_stone)
    bpy.context.scene.collection.objects.unlink(spout)
    link_to_garden(spout)

    # Decorative top sphere
    bpy.ops.mesh.primitive_uv_sphere_add(
        radius=0.6 * FT,
        location=(0, 0, FLOOR_Z + 4.8 * FT),
        segments=16, ring_count=12
    )
    top = bpy.context.active_object
    top.name = "FountainTop"
    top.data.materials.append(mat_fountain_stone)
    bpy.context.scene.collection.objects.unlink(top)
    link_to_garden(top)

    print("  Created fountain")


# ---------------------------------------------------------------------------
# Pathways: 3 radial paths from clearing to hex edges (toward Wing gaps)
# ---------------------------------------------------------------------------
def create_pathways():
    """Three radial stone paths connecting clearing to hex edges."""
    # Paths go toward hex vertices 0, 2, 4 (the gaps between wings)
    path_angles = [math.radians(i * 120) for i in range(3)]
    # Plus the Wing C opening
    path_angles.append(math.radians(90))  # straight toward Wing C

    for idx, angle in enumerate(path_angles):
        dx = math.cos(angle)
        dy = math.sin(angle)
        half_w = PATHWAY_WIDTH / 2.0

        # Path from clearing edge to hex inradius
        inner_r = CLEARING_RADIUS
        outer_r = HEX_S * math.sqrt(3) / 2.0 - PLANTER_INSET

        # Perpendicular for width
        px, py = -dy, dx

        verts = [
            Vector((dx * inner_r + px * half_w, dy * inner_r + py * half_w, FLOOR_Z + 0.02 * FT)),
            Vector((dx * inner_r - px * half_w, dy * inner_r - py * half_w, FLOOR_Z + 0.02 * FT)),
            Vector((dx * outer_r - px * half_w, dy * outer_r - py * half_w, FLOOR_Z + 0.02 * FT)),
            Vector((dx * outer_r + px * half_w, dy * outer_r + py * half_w, FLOOR_Z + 0.02 * FT)),
        ]

        mesh = bpy.data.meshes.new(f"Path_{idx}")
        mesh.from_pydata([v[:] for v in verts], [], [(0, 1, 2, 3)])
        mesh.update()
        mesh.materials.append(mat_stone)
        obj = bpy.data.objects.new(f"Path_{idx}", mesh)
        link_to_garden(obj)

    # Circular clearing (ring path around fountain)
    bpy.ops.mesh.primitive_circle_add(
        radius=CLEARING_RADIUS,
        location=(0, 0, FLOOR_Z + 0.01 * FT),
        vertices=48, fill_type='NGON'
    )
    clearing = bpy.context.active_object
    clearing.name = "ClearingFloor"
    clearing.data.materials.append(mat_stone)
    bpy.context.scene.collection.objects.unlink(clearing)
    link_to_garden(clearing)

    print("  Created pathways and clearing")


# ---------------------------------------------------------------------------
# Plants
# ---------------------------------------------------------------------------
def create_palm(location, height=15.0 * FT, name="Palm"):
    """Procedural palm tree: cylinder trunk + cone fronds."""
    x, y, z = location

    # Trunk: tapered cylinder
    bpy.ops.mesh.primitive_cone_add(
        radius1=0.5 * FT, radius2=0.3 * FT, depth=height,
        location=(x, y, z + height / 2),
        vertices=8
    )
    trunk = bpy.context.active_object
    trunk.name = f"{name}_Trunk"
    trunk.data.materials.append(mat_trunk)
    bpy.context.scene.collection.objects.unlink(trunk)
    link_to_garden(trunk)

    # Fronds: 6-8 elongated cones radiating from top
    n_fronds = random.randint(6, 9)
    frond_len = height * 0.45
    for i in range(n_fronds):
        angle = math.radians(i * 360.0 / n_fronds + random.uniform(-10, 10))
        droop = math.radians(random.uniform(20, 50))

        bpy.ops.mesh.primitive_cone_add(
            radius1=0.8 * FT, radius2=0.0, depth=frond_len,
            vertices=6
        )
        frond = bpy.context.active_object
        frond.name = f"{name}_Frond_{i}"
        frond.data.materials.append(mat_frond)
        frond.location = (x, y, z + height - 0.5 * FT)
        frond.rotation_euler = (droop, 0, angle)
        # Pivot frond from base
        bpy.ops.object.origin_set(type='ORIGIN_CURSOR')
        bpy.context.scene.cursor.location = (x, y, z + height - 0.5 * FT)
        bpy.context.scene.collection.objects.unlink(frond)
        link_to_garden(frond)


def create_bush(location, radius=2.0 * FT, name="Bush"):
    """Cluster of spheres for a tropical bush."""
    x, y, z = location
    n_spheres = random.randint(3, 6)
    for i in range(n_spheres):
        r = radius * random.uniform(0.5, 1.0)
        ox = random.uniform(-radius * 0.4, radius * 0.4)
        oy = random.uniform(-radius * 0.4, radius * 0.4)
        oz = random.uniform(0, radius * 0.3)

        bpy.ops.mesh.primitive_uv_sphere_add(
            radius=r,
            location=(x + ox, y + oy, z + r * 0.7 + oz),
            segments=12, ring_count=8
        )
        sphere = bpy.context.active_object
        sphere.name = f"{name}_Leaf_{i}"
        sphere.data.materials.append(mat_bush)
        bpy.context.scene.collection.objects.unlink(sphere)
        link_to_garden(sphere)


def create_fern(location, name="Fern"):
    """Small fern: flattened sphere cluster."""
    x, y, z = location
    for i in range(random.randint(4, 7)):
        angle = math.radians(i * 51.4 + random.uniform(-15, 15))  # golden angle ish
        dist = random.uniform(0.3 * FT, 1.2 * FT)
        fx = x + math.cos(angle) * dist
        fy = y + math.sin(angle) * dist

        bpy.ops.mesh.primitive_uv_sphere_add(
            radius=random.uniform(0.4 * FT, 0.8 * FT),
            location=(fx, fy, z + 0.3 * FT),
            segments=8, ring_count=6
        )
        leaf = bpy.context.active_object
        leaf.name = f"{name}_Leaf_{i}"
        leaf.scale = (1.0, 1.0, 0.4)
        leaf.data.materials.append(mat_fern)
        bpy.context.scene.collection.objects.unlink(leaf)
        link_to_garden(leaf)


def is_in_planting_zone(x, y):
    """Check if a point is inside the hex, outside clearing, and not on a pathway."""
    # Point-in-hex test using cross product method
    def _cross_2d(ox, oy, ax, ay, bx, by):
        return (ax - ox) * (by - oy) - (ay - oy) * (bx - ox)

    n = len(HEX_VERTS)
    inside = True
    for i in range(n):
        ax, ay = HEX_VERTS[i].x, HEX_VERTS[i].y
        bx, by = HEX_VERTS[(i + 1) % n].x, HEX_VERTS[(i + 1) % n].y
        if _cross_2d(ax, ay, bx, by, x, y) < 0:
            inside = False
            break
    if not inside:
        return False

    dist_to_center = math.hypot(x, y)
    if dist_to_center < CLEARING_RADIUS + 1.0 * FT:
        return False

    # Check pathway exclusion
    path_angles = [math.radians(i * 120) for i in range(3)]
    path_angles.append(math.radians(90))
    for angle in path_angles:
        dx = math.cos(angle)
        dy = math.sin(angle)
        # Distance from point to path centerline
        cross = abs(x * dy - y * dx)
        dot = x * dx + y * dy
        if cross < PATHWAY_WIDTH / 2 + 1.0 * FT and dot > 0:
            return False

    return True


def populate_plants():
    """Fill planting beds with tropical plants."""
    plant_count = 0

    # Large palms around clearing perimeter
    palm_ring_r = CLEARING_RADIUS + 3.5 * FT
    for i in range(5):
        angle = math.radians(i * 72 + 15)
        px = palm_ring_r * math.cos(angle)
        py = palm_ring_r * math.sin(angle)
        if is_in_planting_zone(px, py):
            h = random.uniform(14 * FT, 22 * FT)
            create_palm((px, py, FLOOR_Z), height=h, name=f"Palm_Ring_{i}")
            plant_count += 1

    # Scattered tall palms throughout
    for i in range(8):
        for _ in range(20):
            angle = random.uniform(0, 2 * math.pi)
            dist = random.uniform(CLEARING_RADIUS + 4 * FT, HEX_S * 0.8)
            px = dist * math.cos(angle)
            py = dist * math.sin(angle)
            if is_in_planting_zone(px, py):
                h = random.uniform(10 * FT, 25 * FT)
                create_palm((px, py, FLOOR_Z), height=h, name=f"Palm_Scatter_{i}")
                plant_count += 1
                break

    # Bushes filling mid-ground
    for i in range(15):
        for _ in range(30):
            angle = random.uniform(0, 2 * math.pi)
            dist = random.uniform(CLEARING_RADIUS + 2 * FT, HEX_S * 0.85)
            px = dist * math.cos(angle)
            py = dist * math.sin(angle)
            if is_in_planting_zone(px, py):
                r = random.uniform(1.5 * FT, 3.0 * FT)
                create_bush((px, py, FLOOR_Z), radius=r, name=f"Bush_{i}")
                plant_count += 1
                break

    # Ferns as ground cover, especially around fountain
    for i in range(20):
        for _ in range(30):
            angle = random.uniform(0, 2 * math.pi)
            dist = random.uniform(CLEARING_RADIUS + 1.5 * FT, HEX_S * 0.75)
            px = dist * math.cos(angle)
            py = dist * math.sin(angle)
            if is_in_planting_zone(px, py):
                create_fern((px, py, FLOOR_Z), name=f"Fern_{i}")
                plant_count += 1
                break

    # Ring of small plants around fountain base
    for i in range(12):
        angle = math.radians(i * 30 + random.uniform(-5, 5))
        r = FOUNTAIN_RADIUS + 0.8 * FT
        px = r * math.cos(angle)
        py = r * math.sin(angle)
        create_fern((px, py, FLOOR_Z), name=f"FountainFern_{i}")
        plant_count += 1

    print(f"  Placed {plant_count} plant groups")


# ---------------------------------------------------------------------------
# Soil bed (dark ground plane for planting areas)
# ---------------------------------------------------------------------------
def create_soil_bed():
    """Dark soil plane covering planting areas (under plants, not pathways)."""
    # Just a hex-shaped plane at floor level, slightly below path level
    verts = [(v.x, v.y, FLOOR_Z - 0.01 * FT) for v in HEX_VERTS]
    faces = [list(range(len(verts)))]  # single n-gon

    mesh = bpy.data.meshes.new("SoilBed")
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    mesh.materials.append(mat_soil)
    obj = bpy.data.objects.new("SoilBed", mesh)
    link_to_garden(obj)
    print("  Created soil bed")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
print("Generating atrium garden...")
create_fountain()
create_pathways()
create_soil_bed()
populate_plants()
print("Atrium garden complete!")

# Apply sun position from config
try:
    config_path = os.path.join(os.path.dirname(__file__), "config.json")
    import json
    with open(config_path) as f:
        cfg = json.load(f)
    _lat = cfg.get("site_latitude", 35.5)
    _lon = cfg.get("site_longitude", -80.0)
    _month = int(cfg.get("sun_month", 6))
    _day = int(cfg.get("sun_day", 21))
    _hour = float(cfg.get("sun_hour", 14.0))
    _north = float(cfg.get("site_north_offset_deg", 0.0))

    # Inline solar calc (no shapely in Blender)
    _doy = sum([0,31,28,31,30,31,30,31,31,30,31,30,31][:_month]) + _day
    _B = math.radians((360/365)*(_doy - 81))
    _dec = math.radians(23.45) * math.sin(_B)
    _B2 = math.radians((360/365)*(_doy - 1))
    _eot = 229.18*(0.000075+0.001868*math.cos(_B2)-0.032077*math.sin(_B2)
                    -0.014615*math.cos(2*_B2)-0.04089*math.sin(2*_B2))
    _utc_off = -4.0 if 3 <= _month <= 10 else -5.0
    _st = (_hour - _utc_off) + (_lon/15.0) + (_eot/60.0)
    _ha = math.radians((_st - 12.0)*15.0)
    _lat_r = math.radians(_lat)
    _sin_alt = math.sin(_lat_r)*math.sin(_dec)+math.cos(_lat_r)*math.cos(_dec)*math.cos(_ha)
    _alt = math.asin(max(-1,min(1,_sin_alt)))
    _cos_az = (math.sin(_dec)-math.sin(_lat_r)*math.sin(_alt))/(math.cos(_lat_r)*math.cos(_alt)+1e-10)
    _az = math.acos(max(-1,min(1,_cos_az)))
    if _ha > 0:
        _az = 2*math.pi - _az
    _az = (_az + math.pi) % (2*math.pi)

    _alt_d = math.degrees(_alt)
    _az_d = math.degrees(_az)

    # Create/update Sun lamp
    sun_obj = None
    for obj in bpy.data.objects:
        if obj.type == 'LIGHT' and obj.data.type == 'SUN':
            sun_obj = obj
            break
    if sun_obj is None:
        sun_data = bpy.data.lights.new(name="Sun", type='SUN')
        sun_obj = bpy.data.objects.new("Sun", sun_data)
        bpy.context.collection.objects.link(sun_obj)

    _rot_x = math.pi/2 - _alt
    _rot_z = -math.radians(_az_d + _north)
    sun_obj.rotation_euler = (_rot_x, 0.0, _rot_z)
    sun_obj.data.energy = 2.0 * (0.3 if _alt_d < 10 else 0.6 if _alt_d < 25 else 1.0)
    sun_obj.data.color = (1.0, 0.98, 0.95)
    sun_obj.data.angle = math.radians(0.545)

    # Remove any other lights (default Blender point/spot lights that stack)
    for obj in list(bpy.data.objects):
        if obj.type == 'LIGHT' and obj is not sun_obj:
            bpy.data.objects.remove(obj, do_unlink=True)

    print(f"  Sun: alt={_alt_d:.1f}° az={_az_d:.1f}° ({_month}/{_day} {_hour:.0f}h, {_lat}°N)")
    # NOTE: World background and render settings are handled by blender_startup.py.
    # Do NOT set them here or they will overwrite the HDRI environment.
except Exception as e:
    print(f"  Sun positioning skipped: {e}")

# Export if output path specified
if glb_out:
    print(f"Exporting to {glb_out}...")
    bpy.ops.export_scene.gltf(
        filepath=glb_out,
        export_format='GLB',
        use_selection=False,
        export_apply=True,
    )
    print(f"Saved: {glb_out}")
elif "--background" not in sys.argv and "-b" not in sys.argv:
    print("Scene ready for viewport exploration.")
    print("Tip: press Numpad 5 for perspective, then use middle-mouse to orbit.")
