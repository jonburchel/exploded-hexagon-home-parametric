"""
Wing B bedroom furnishing script for Blender.

Creates: California King bed, 2 nightstands, 2 lounge chairs,
coffee table, and luxury area rug in the master triangle upper level
over Wing B.

NOTE: The interior wall between the bedroom and atrium (hex edge 3->4)
should be opaque (not glass). Wall material change handled in model.py.

Run after atrium_garden.py:
  blender --background --python src/furnish_wingb.py -- in.glb out.glb
"""

import bpy
import math
import sys
import os
import random

# ---------------------------------------------------------------------------
# Args
# ---------------------------------------------------------------------------
argv = sys.argv
glb_in = None
glb_out = None
if "--" in argv:
    args = argv[argv.index("--") + 1:]
    if len(args) >= 1:
        glb_in = os.path.abspath(args[0])
    if len(args) >= 2:
        glb_out = os.path.abspath(args[1])

if glb_in:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=glb_in)

# Clean up any existing bedroom furniture (allows re-run without duplicates)
_existing_col = bpy.data.collections.get("WingB_Bedroom")
if _existing_col:
    for _obj in list(_existing_col.objects):
        bpy.data.objects.remove(_obj, do_unlink=True)
    bpy.data.collections.remove(_existing_col)

# ---------------------------------------------------------------------------
# Geometry constants (from plan computation, converted to meters)
# ---------------------------------------------------------------------------
FT = 0.3048  # feet to meters conversion

# Wing B region on the triangle upper level
# Hex edge 3→4 midpoint: (-17.25, -9.96)  (interior wall)
# Nearest triangle vertex (t1): (-53.56, 4.46)
# Facing direction: 158.3° from hex midpoint toward triangle tip
#
# Bed flush against interior wall (hex edge 3→4).
# Hex edge 3→4 runs at -60°; outward perpendicular (into bedroom) at 210°.
# Bed center placed at (BED_L/2 + 0.05ft) from wall along outward normal.
# Wall midpoint: (-17.25, -9.96) ft
# Outward normal: (cos210°, sin210°) = (-0.866, -0.5)
# bed_center = midpoint + 3.385 * (-0.866, -0.5) = (-20.18, -11.65)
# Sitting area at 50% from wall to triangle tip, well inside room.
FLOOR_Z = 26.0 * FT  # master_triangle_elevation + slab

BED_CENTER = (-20.5 * FT, -11.85 * FT)
SITTING_CENTER = (-27.5 * FT, -5.9 * FT)

# Bed rotation_z = 120° so the box Y axis (depth/length) aligns with 210°
# (perpendicular to wall, into room), and X axis (width) aligns with 120°
# (parallel to hex edge 3→4). Headboard at -Y faces toward wall (30°).
FACING_ANGLE = math.radians(120.0)

# California King: 76" x 80" = 6.33' x 6.67'
BED_W = 6.33 * FT
BED_L = 6.67 * FT
BED_H = 2.0 * FT   # mattress + frame height
HEADBOARD_H = 4.0 * FT

# Nightstand: 2' x 1.5' x 2.2'
NS_W = 2.0 * FT
NS_D = 1.5 * FT
NS_H = 2.2 * FT

# Chair: 2.5' x 2.5' x 3'
CHAIR_W = 2.5 * FT
CHAIR_D = 2.5 * FT
CHAIR_H = 1.5 * FT
CHAIR_BACK_H = 3.0 * FT

# Coffee table: 4' x 2' x 1.4'
TABLE_W = 4.0 * FT
TABLE_D = 2.0 * FT
TABLE_H = 1.4 * FT

# Rug: 9' x 8' (sized to fit under bed area with wall clearance)
RUG_W = 9.0 * FT
RUG_L = 8.0 * FT

# ---------------------------------------------------------------------------
# Collection
# ---------------------------------------------------------------------------
bedroom_col = bpy.data.collections.new("WingB_Bedroom")
bpy.context.scene.collection.children.link(bedroom_col)

def link_to_bedroom(obj):
    bedroom_col.objects.link(obj)

# ---------------------------------------------------------------------------
# Materials
# ---------------------------------------------------------------------------
def make_mat(name, color, roughness=0.5, metallic=0.0):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (*color, 1.0)
    bsdf.inputs["Roughness"].default_value = roughness
    bsdf.inputs["Metallic"].default_value = metallic
    return mat

# Rich, luxurious materials
mat_bed_fabric = make_mat("BedFabric", (0.92, 0.90, 0.85), roughness=0.8)  # cream linen
mat_headboard = make_mat("Headboard", (0.20, 0.18, 0.22), roughness=0.4)   # dark upholstered
mat_wood_dark = make_mat("DarkWalnut", (0.22, 0.14, 0.08), roughness=0.3)  # dark walnut
mat_wood_light = make_mat("LightOak", (0.55, 0.40, 0.25), roughness=0.35) # light oak
mat_pillow = make_mat("Pillow", (0.95, 0.95, 0.93), roughness=0.85)        # white cotton
mat_chair_leather = make_mat("Leather", (0.15, 0.12, 0.10), roughness=0.35, metallic=0.05)  # dark leather
mat_metal_brass = make_mat("Brass", (0.72, 0.58, 0.30), roughness=0.2, metallic=0.9)  # brushed brass
mat_glass_table = make_mat("TableGlass", (0.90, 0.92, 0.93), roughness=0.02)
mat_rug = make_mat("LuxuryRug", (0.12, 0.15, 0.35), roughness=0.9)  # deep blue base

# Rug pattern: deep blue base with gold accents and burgundy highlights
rug_nodes = mat_rug.node_tree.nodes
rug_links = mat_rug.node_tree.links
tc = rug_nodes.new('ShaderNodeTexCoord')
mapping = rug_nodes.new('ShaderNodeMapping')
rug_links.new(tc.outputs['Generated'], mapping.inputs['Vector'])

# First wave: blend deep blue with gold
wave1 = rug_nodes.new('ShaderNodeTexWave')
wave1.inputs['Scale'].default_value = 6.0
wave1.inputs['Distortion'].default_value = 2.0
rug_links.new(mapping.outputs['Vector'], wave1.inputs['Vector'])
mix1 = rug_nodes.new('ShaderNodeMixRGB')
mix1.inputs['Fac'].default_value = 0.3
mix1.inputs['Color1'].default_value = (0.12, 0.15, 0.35, 1.0)   # deep blue
mix1.inputs['Color2'].default_value = (0.72, 0.58, 0.30, 1.0)   # gold accent
rug_links.new(wave1.outputs['Fac'], mix1.inputs['Fac'])

# Second wave: overlay burgundy highlights
wave2 = rug_nodes.new('ShaderNodeTexWave')
wave2.inputs['Scale'].default_value = 4.0
wave2.inputs['Distortion'].default_value = 3.5
wave2.wave_type = 'RINGS'
rug_links.new(mapping.outputs['Vector'], wave2.inputs['Vector'])
mix2 = rug_nodes.new('ShaderNodeMixRGB')
mix2.inputs['Fac'].default_value = 0.25
mix2.inputs['Color2'].default_value = (0.45, 0.12, 0.15, 1.0)   # burgundy
rug_links.new(mix1.outputs['Color'], mix2.inputs['Color1'])
rug_links.new(wave2.outputs['Fac'], mix2.inputs['Fac'])

bsdf_rug = rug_nodes["Principled BSDF"]
rug_links.new(mix2.outputs['Color'], bsdf_rug.inputs['Base Color'])

# ---------------------------------------------------------------------------
# Helper: create oriented box
# ---------------------------------------------------------------------------
def create_box(name, width, depth, height, location, material, rotation_z=0):
    """Create a box with rotation baked into vertices (no operators needed)."""
    hw, hd, hh = width / 2, depth / 2, height / 2
    ca, sa = math.cos(rotation_z), math.sin(rotation_z)
    verts = []
    for sx in (-1, 1):
        for sy in (-1, 1):
            for sz in (-1, 1):
                lx, ly = sx * hw, sy * hd
                verts.append((lx * ca - ly * sa, lx * sa + ly * ca, sz * hh))
    faces = [
        (0, 2, 3, 1), (4, 5, 7, 6),
        (0, 1, 5, 4), (2, 6, 7, 3),
        (0, 4, 6, 2), (1, 3, 7, 5),
    ]
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    obj.location = (location[0], location[1], location[2] + height / 2)
    obj.data.materials.append(material)
    link_to_bedroom(obj)
    return obj


def create_cylinder(name, radius, height, location, material, rotation_z=0):
    """Create a cylinder with rotation baked into vertices."""
    n = 24
    hh = height / 2
    ca, sa = math.cos(rotation_z), math.sin(rotation_z)
    verts = []
    for i in range(n):
        a = 2 * math.pi * i / n
        lx, ly = radius * math.cos(a), radius * math.sin(a)
        rx, ry = lx * ca - ly * sa, lx * sa + ly * ca
        verts.append((rx, ry, -hh))
        verts.append((rx, ry, hh))
    faces = []
    for i in range(n):
        j = (i + 1) % n
        faces.append((i * 2, j * 2, j * 2 + 1, i * 2 + 1))
    faces.append(tuple(range(0, n * 2, 2)))
    faces.append(tuple(range(n * 2 - 1, -1, -2)))
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    obj.location = (location[0], location[1], location[2] + height / 2)
    obj.data.materials.append(material)
    link_to_bedroom(obj)
    return obj


# ---------------------------------------------------------------------------
# Transform helpers: place objects relative to room center + facing
# ---------------------------------------------------------------------------
def room_pos(center, dx, dy, angle):
    """Convert local (dx, dy) offset to world coords rotated by angle."""
    cos_a = math.cos(angle)
    sin_a = math.sin(angle)
    wx = center[0] + dx * cos_a - dy * sin_a
    wy = center[1] + dx * sin_a + dy * cos_a
    return (wx, wy, FLOOR_Z)


# ---------------------------------------------------------------------------
# Create bed
# ---------------------------------------------------------------------------
print("Furnishing Wing B bedroom...")

# Bed mattress
bed_pos = room_pos(BED_CENTER, 0, 0, FACING_ANGLE)
create_box("Bed_Mattress", BED_W, BED_L, BED_H, bed_pos, mat_bed_fabric, FACING_ANGLE)

# Bed frame (slightly larger, slightly below)
frame_pos = room_pos(BED_CENTER, 0, 0, FACING_ANGLE)
create_box("Bed_Frame", BED_W + 0.5*FT, BED_L + 0.5*FT, 0.8*FT, frame_pos, mat_wood_dark, FACING_ANGLE)

# Headboard (at the back of the bed)
hb_pos = room_pos(BED_CENTER, 0, -BED_L / 2 + 0.2*FT, FACING_ANGLE)
create_box("Headboard", BED_W + 0.5*FT, 0.5*FT, HEADBOARD_H, hb_pos, mat_headboard, FACING_ANGLE)

# Pillows (4 pillows across)
for i, px_off in enumerate([-2.0*FT, -0.7*FT, 0.7*FT, 2.0*FT]):
    p_pos = room_pos(BED_CENTER, px_off, -BED_L / 2 + 1.2*FT, FACING_ANGLE)
    create_box(f"Pillow_{i}", 1.5*FT, 1.0*FT, 0.5*FT, (p_pos[0], p_pos[1], FLOOR_Z + BED_H), mat_pillow, FACING_ANGLE)

print("  Bed placed")

# ---------------------------------------------------------------------------
# Nightstands
# ---------------------------------------------------------------------------
for side, sx in [("Left", -(BED_W / 2 + NS_W / 2 + 0.5*FT)), ("Right", (BED_W / 2 + NS_W / 2 + 0.5*FT))]:
    ns_pos = room_pos(BED_CENTER, sx, -BED_L / 2 + NS_D / 2, FACING_ANGLE)
    create_box(f"Nightstand_{side}", NS_W, NS_D, NS_H, ns_pos, mat_wood_dark, FACING_ANGLE)
    # Lamp on nightstand
    lamp_pos = room_pos(BED_CENTER, sx, -BED_L / 2 + NS_D / 2, FACING_ANGLE)
    create_cylinder(f"Lamp_{side}_Base", 0.3*FT, 0.1*FT, (lamp_pos[0], lamp_pos[1], FLOOR_Z + NS_H), mat_metal_brass, FACING_ANGLE)
    create_cylinder(f"Lamp_{side}_Shade", 0.5*FT, 1.0*FT, (lamp_pos[0], lamp_pos[1], FLOOR_Z + NS_H + 0.5*FT), mat_bed_fabric, FACING_ANGLE)

print("  Nightstands placed")

# ---------------------------------------------------------------------------
# Sitting area (near triangle point, facing outward)
# ---------------------------------------------------------------------------
# Two chairs flanking a coffee table
for side, sx in [("Left", -3.5*FT), ("Right", 3.5*FT)]:
    ch_pos = room_pos(SITTING_CENTER, sx, 0, FACING_ANGLE)
    # Seat cushion
    create_box(f"Chair_{side}_Seat", CHAIR_W, CHAIR_D, CHAIR_H, ch_pos, mat_chair_leather, FACING_ANGLE)
    # Chair back
    back_pos = room_pos(SITTING_CENTER, sx, -CHAIR_D / 2 + 0.2*FT, FACING_ANGLE)
    create_box(f"Chair_{side}_Back", CHAIR_W, 0.4*FT, CHAIR_BACK_H,
               (back_pos[0], back_pos[1], FLOOR_Z), mat_chair_leather, FACING_ANGLE)
    # Brass legs (4 corners)
    for lx, ly in [(-0.9, -0.9), (0.9, -0.9), (-0.9, 0.9), (0.9, 0.9)]:
        leg_pos = room_pos(SITTING_CENTER, sx + lx * 0.5*FT, ly * 0.5*FT, FACING_ANGLE)
        create_cylinder(f"ChairLeg_{side}_{lx}_{ly}", 0.08*FT, CHAIR_H,
                        (leg_pos[0], leg_pos[1], FLOOR_Z), mat_metal_brass)

# Coffee table between chairs
ct_pos = room_pos(SITTING_CENTER, 0, 1.0*FT, FACING_ANGLE)
# Glass top
create_box("CoffeeTable_Top", TABLE_W, TABLE_D, 0.15*FT, (ct_pos[0], ct_pos[1], FLOOR_Z + TABLE_H - 0.15*FT), mat_glass_table, FACING_ANGLE)
# Metal frame
create_box("CoffeeTable_Frame", TABLE_W - 0.3*FT, TABLE_D - 0.3*FT, 0.1*FT,
           (ct_pos[0], ct_pos[1], FLOOR_Z + TABLE_H / 2), mat_metal_brass, FACING_ANGLE)
# Legs
for lx, ly in [(-1.5, -0.7), (1.5, -0.7), (-1.5, 0.7), (1.5, 0.7)]:
    leg_pos = room_pos(SITTING_CENTER, lx*FT, 1.0*FT + ly*FT, FACING_ANGLE)
    create_cylinder(f"TableLeg_{lx}_{ly}", 0.06*FT, TABLE_H,
                    (leg_pos[0], leg_pos[1], FLOOR_Z), mat_metal_brass)

print("  Sitting area placed")

# ---------------------------------------------------------------------------
# Area rug (under the bed and sitting area)
# ---------------------------------------------------------------------------
# Area rug centered under the bed
rug_pos = (BED_CENTER[0], BED_CENTER[1], FLOOR_Z + 0.02*FT)  # just above floor

create_box("AreaRug", RUG_W, RUG_L, 0.04*FT, rug_pos, mat_rug, FACING_ANGLE)

print("  Rug placed")
print("Wing B bedroom furnishing complete!")

# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------
if glb_out:
    print(f"Exporting to {glb_out}...")
    bpy.ops.export_scene.gltf(
        filepath=glb_out,
        export_format='GLB',
        use_selection=False,
        export_apply=True,
    )
    print(f"Saved: {glb_out}")
