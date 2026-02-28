"""
Blender headless render script for architectural visualization.
Generates: plan view, 4 elevations, isometric site view, and 2 section cuts.
Usage: blender --background --python render_views.py
"""

import bpy
import math
import os
import mathutils

# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------
OBJ_PATH = r"F:\home\exploded-hexagon-home\houseplan_massing_s23_d7_site_v3_roof_panelized.obj"
OUT_DIR  = r"F:\home\exploded-hexagon-home\renders"
RES_X, RES_Y = 2400, 1800
SAMPLES = 64

os.makedirs(OUT_DIR, exist_ok=True)

# ---------------------------------------------------------------------------
# SCENE SETUP
# ---------------------------------------------------------------------------
# Clear default scene
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=True)

# Delete default collections' remaining objects
for obj in bpy.data.objects:
    bpy.data.objects.remove(obj, do_unlink=True)

# Import OBJ
bpy.ops.wm.obj_import(filepath=OBJ_PATH)

# Gather imported objects
imported = [o for o in bpy.context.scene.objects if o.type == 'MESH']

# OBJ uses feet with Z-up; Blender imported with Y-up conversion.
# Compute bounding box in world space after import.
all_coords = []
for obj in imported:
    for v in obj.data.vertices:
        all_coords.append(obj.matrix_world @ v.co)

min_co = mathutils.Vector((
    min(c.x for c in all_coords),
    min(c.y for c in all_coords),
    min(c.z for c in all_coords),
))
max_co = mathutils.Vector((
    max(c.x for c in all_coords),
    max(c.y for c in all_coords),
    max(c.z for c in all_coords),
))
center = (min_co + max_co) / 2
size = max_co - min_co
max_dim = max(size.x, size.y, size.z)

print(f"Model bounds: min={min_co}, max={max_co}")
print(f"Center: {center}, Size: {size}, Max dim: {max_dim}")

# ---------------------------------------------------------------------------
# MATERIALS - assign proper colors from MTL data
# ---------------------------------------------------------------------------
for obj in imported:
    for slot in obj.material_slots:
        mat = slot.material
        if mat and not mat.use_nodes:
            mat.use_nodes = True
        if mat and mat.use_nodes:
            bsdf = mat.node_tree.nodes.get("Principled BSDF")
            if bsdf:
                # Use diffuse color if available
                if hasattr(mat, 'diffuse_color'):
                    bsdf.inputs['Base Color'].default_value = mat.diffuse_color
                bsdf.inputs['Roughness'].default_value = 0.6
                bsdf.inputs['Specular IOR Level'].default_value = 0.3

# ---------------------------------------------------------------------------
# LIGHTING
# ---------------------------------------------------------------------------
# Sun light (key light)
bpy.ops.object.light_add(type='SUN', location=(center.x + max_dim, center.y + max_dim, center.z + max_dim * 2))
sun = bpy.context.active_object
sun.data.energy = 3.0
sun.data.angle = math.radians(5)
sun.rotation_euler = (math.radians(45), math.radians(15), math.radians(135))

# Fill light (softer, from opposite side)
bpy.ops.object.light_add(type='SUN', location=(center.x - max_dim, center.y - max_dim, center.z + max_dim))
fill = bpy.context.active_object
fill.data.energy = 1.2
fill.data.angle = math.radians(10)
fill.rotation_euler = (math.radians(60), math.radians(-15), math.radians(-45))

# Set world background to white-ish for architectural feel
world = bpy.data.worlds['World']
world.use_nodes = True
bg = world.node_tree.nodes.get('Background')
if bg:
    bg.inputs['Color'].default_value = (0.95, 0.95, 0.97, 1.0)
    bg.inputs['Strength'].default_value = 0.8

# ---------------------------------------------------------------------------
# RENDER SETTINGS
# ---------------------------------------------------------------------------
scene = bpy.context.scene
scene.render.engine = 'CYCLES'
scene.cycles.samples = SAMPLES
scene.cycles.use_denoising = True
scene.render.resolution_x = RES_X
scene.render.resolution_y = RES_Y
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = 'PNG'
scene.render.image_settings.color_mode = 'RGBA'
scene.render.film_transparent = True

# Prefer GPU if available
prefs = bpy.context.preferences.addons.get('cycles')
if prefs:
    cprefs = prefs.preferences
    cprefs.compute_device_type = 'NONE'
    for dev_type in ['OPTIX', 'CUDA', 'HIP', 'ONEAPI']:
        try:
            cprefs.compute_device_type = dev_type
            cprefs.get_devices()
            has_gpu = any(d.type != 'CPU' for d in cprefs.devices)
            if has_gpu:
                for d in cprefs.devices:
                    d.use = True
                scene.cycles.device = 'GPU'
                print(f"Using GPU compute: {dev_type}")
                break
        except:
            continue

# ---------------------------------------------------------------------------
# CAMERA HELPER
# ---------------------------------------------------------------------------
def setup_camera_ortho(name, location, rotation, ortho_scale):
    """Create/reuse an orthographic camera aimed at the model."""
    cam_data = bpy.data.cameras.new(name)
    cam_data.type = 'ORTHO'
    cam_data.ortho_scale = ortho_scale
    cam_data.clip_start = 0.1
    cam_data.clip_end = max_dim * 10
    cam_obj = bpy.data.objects.new(name, cam_data)
    bpy.context.scene.collection.objects.link(cam_obj)
    cam_obj.location = location
    cam_obj.rotation_euler = rotation
    return cam_obj


def setup_camera_persp(name, location, rotation, lens=50):
    """Create a perspective camera."""
    cam_data = bpy.data.cameras.new(name)
    cam_data.type = 'PERSP'
    cam_data.lens = lens
    cam_data.clip_start = 0.1
    cam_data.clip_end = max_dim * 10
    cam_obj = bpy.data.objects.new(name, cam_data)
    bpy.context.scene.collection.objects.link(cam_obj)
    cam_obj.location = location
    cam_obj.rotation_euler = rotation
    return cam_obj


def render_view(cam_obj, filename):
    """Assign camera and render."""
    scene.camera = cam_obj
    scene.render.filepath = os.path.join(OUT_DIR, filename)
    print(f"Rendering {filename}...")
    bpy.ops.render.render(write_still=True)
    print(f"  Saved: {scene.render.filepath}.png")


# Padding factor for orthographic framing
pad = 1.2
dist = max_dim * 3  # camera distance from center

# ---------------------------------------------------------------------------
# 1. PLAN VIEW (Top-down orthographic)
# ---------------------------------------------------------------------------
print("\n=== PLAN VIEW ===")
cam_plan = setup_camera_ortho(
    "Cam_Plan",
    location=(center.x, center.y, center.z + dist),
    rotation=(0, 0, 0),
    ortho_scale=max(size.x, size.y) * pad
)
render_view(cam_plan, "01_plan_view")

# ---------------------------------------------------------------------------
# 2. ELEVATIONS (Front, Right, Back, Left)
# ---------------------------------------------------------------------------
elevations = [
    ("02_elevation_front",  (center.x, center.y - dist, center.z), (math.pi/2, 0, 0)),
    ("03_elevation_right",  (center.x + dist, center.y, center.z), (math.pi/2, 0, math.pi/2)),
    ("04_elevation_back",   (center.x, center.y + dist, center.z), (math.pi/2, 0, math.pi)),
    ("05_elevation_left",   (center.x - dist, center.y, center.z), (math.pi/2, 0, -math.pi/2)),
]

for name, loc, rot in elevations:
    print(f"\n=== {name.upper()} ===")
    cam = setup_camera_ortho(
        f"Cam_{name}",
        location=loc,
        rotation=rot,
        ortho_scale=max(size.x, size.y, size.z) * pad
    )
    render_view(cam, name)

# ---------------------------------------------------------------------------
# 3. SITE VIEW / ISOMETRIC (axonometric orthographic)
# ---------------------------------------------------------------------------
print("\n=== ISOMETRIC SITE VIEW ===")
# Classic architectural axonometric: 30 degree angle from above
iso_angle_h = math.radians(35.264)  # arctan(1/sqrt(2)) for true isometric
iso_angle_v = math.radians(45)
iso_dist = dist * 1.2
cam_iso = setup_camera_ortho(
    "Cam_Isometric",
    location=(
        center.x + iso_dist * math.cos(iso_angle_v) * math.cos(iso_angle_h),
        center.y - iso_dist * math.sin(iso_angle_v) * math.cos(iso_angle_h),
        center.z + iso_dist * math.sin(iso_angle_h),
    ),
    rotation=(math.radians(90 - 35.264), 0, math.radians(45)),
    ortho_scale=max(size.x, size.y, size.z) * pad * 1.1
)
render_view(cam_iso, "06_isometric_site")

# ---------------------------------------------------------------------------
# 3b. PERSPECTIVE SITE VIEW (dramatic angle)
# ---------------------------------------------------------------------------
print("\n=== PERSPECTIVE SITE VIEW ===")
persp_dist = max_dim * 2.5
cam_persp = setup_camera_persp(
    "Cam_Perspective",
    location=(
        center.x + persp_dist * 0.7,
        center.y - persp_dist * 0.9,
        center.z + persp_dist * 0.5,
    ),
    rotation=(math.radians(60), 0, math.radians(38)),
    lens=35
)
render_view(cam_persp, "07_perspective_site")

# ---------------------------------------------------------------------------
# 4. SECTION CUTS (Boolean difference with a cutting plane)
# ---------------------------------------------------------------------------
print("\n=== SECTION CUTS ===")

def create_section_cut(cut_name, cut_axis, cut_position, cam_loc, cam_rot, ortho_scale):
    """
    Create a section cut using Boolean modifier.
    cut_axis: 'X', 'Y', or 'Z'
    cut_position: where to place the cutting plane along that axis
    """
    # Create a large cutting box
    cut_size = max_dim * 4
    bpy.ops.mesh.primitive_cube_add(size=1)
    cutter = bpy.context.active_object
    cutter.name = f"Cutter_{cut_name}"

    # Scale and position the cutter to slice away half
    if cut_axis == 'X':
        cutter.scale = (cut_size, cut_size, cut_size)
        cutter.location = (cut_position + cut_size/2, center.y, center.z)
    elif cut_axis == 'Y':
        cutter.scale = (cut_size, cut_size, cut_size)
        cutter.location = (center.x, cut_position + cut_size/2, center.z)
    else:  # Z
        cutter.scale = (cut_size, cut_size, cut_size)
        cutter.location = (center.x, center.y, cut_position + cut_size/2)

    # Duplicate all mesh objects and join them
    bpy.ops.object.select_all(action='DESELECT')
    mesh_objs = [o for o in imported if o.type == 'MESH']
    for o in mesh_objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = mesh_objs[0]
    bpy.ops.object.duplicate()
    duped = [o for o in bpy.context.selected_objects]

    if len(duped) > 1:
        bpy.context.view_layer.objects.active = duped[0]
        bpy.ops.object.join()
    section_obj = bpy.context.active_object
    section_obj.name = f"Section_{cut_name}"

    # Apply Boolean modifier
    bool_mod = section_obj.modifiers.new(name="SectionCut", type='BOOLEAN')
    bool_mod.operation = 'DIFFERENCE'
    bool_mod.object = cutter
    bpy.context.view_layer.objects.active = section_obj
    bpy.ops.object.modifier_apply(modifier="SectionCut")

    # Hide original objects and cutter for this render
    for o in imported:
        o.hide_render = True
    cutter.hide_render = True

    # Setup camera and render
    cam = setup_camera_ortho(
        f"Cam_{cut_name}",
        location=cam_loc,
        rotation=cam_rot,
        ortho_scale=ortho_scale
    )
    render_view(cam, cut_name)

    # Restore: show originals, delete section duplicate and cutter
    for o in imported:
        o.hide_render = False
    bpy.data.objects.remove(section_obj, do_unlink=True)
    bpy.data.objects.remove(cutter, do_unlink=True)


# Section A: Cut through the middle along Y axis (looking from front)
create_section_cut(
    "08_section_Y",
    cut_axis='Y',
    cut_position=center.y,
    cam_loc=(center.x, center.y - dist, center.z),
    cam_rot=(math.pi/2, 0, 0),
    ortho_scale=max(size.x, size.z) * pad
)

# Section B: Cut through the middle along X axis (looking from right)
create_section_cut(
    "09_section_X",
    cut_axis='X',
    cut_position=center.x,
    cam_loc=(center.x + dist, center.y, center.z),
    cam_rot=(math.pi/2, 0, math.pi/2),
    ortho_scale=max(size.y, size.z) * pad
)

print("\n=== ALL RENDERS COMPLETE ===")
print(f"Output directory: {OUT_DIR}")
for f in sorted(os.listdir(OUT_DIR)):
    print(f"  {f}")
