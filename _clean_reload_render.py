"""Clean reload GLB into Blender and render bright diagnostic views of Wing A/B wall base."""
import bpy
import math
import os

FT = 0.3048
PROJECT = r"F:\home\exploded-hexagon-home"
GLB = os.path.join(PROJECT, "out", "massing_s23_d7.glb")

# ---- Step 1: Remove ALL existing mesh objects ----
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)

# Also purge orphan data
bpy.ops.outliner.orphans_purge(do_local_ids=True, do_linked_ids=True, do_recursive=True)

print("[1] Cleared scene")

# ---- Step 2: Import fresh GLB ----
bpy.ops.import_scene.gltf(filepath=GLB)
imported = [o for o in bpy.context.scene.objects if o.type == 'MESH']
print(f"[2] Imported {len(imported)} mesh objects from GLB")

# Print all object names and their Z bounding boxes
for obj in sorted(imported, key=lambda o: o.name):
    bb = obj.bound_box
    zs = [obj.matrix_world @ bpy.app.driver_namespace.get('_', __import__('mathutils').Vector(v)) for v in bb]
    # Simpler: just use the object's world-space bounds
    ws_verts = [obj.matrix_world @ __import__('mathutils').Vector(v) for v in bb]
    zmin = min(v.z for v in ws_verts) / FT
    zmax = max(v.z for v in ws_verts) / FT
    print(f"  {obj.name}: z=[{zmin:.1f}, {zmax:.1f}] ft")

# ---- Step 3: Apply basic materials for visibility ----
# Create a simple gray material so everything is visible
mat_gray = bpy.data.materials.new("DiagGray")
mat_gray.use_nodes = True
bsdf = mat_gray.node_tree.nodes["Principled BSDF"]
bsdf.inputs["Base Color"].default_value = (0.6, 0.6, 0.6, 1.0)
bsdf.inputs["Roughness"].default_value = 0.5

mat_marble = bpy.data.materials.new("DiagMarble")
mat_marble.use_nodes = True
bsdf2 = mat_marble.node_tree.nodes["Principled BSDF"]
bsdf2.inputs["Base Color"].default_value = (0.9, 0.85, 0.8, 1.0)
bsdf2.inputs["Roughness"].default_value = 0.3

for obj in imported:
    if "atrium_floor" in obj.name.lower():
        obj.data.materials.clear()
        obj.data.materials.append(mat_marble)
    else:
        obj.data.materials.clear()
        obj.data.materials.append(mat_gray)

print("[3] Applied diagnostic materials")

# ---- Step 4: Set up bright lighting ----
# Sun lamp - very bright
sun = bpy.data.lights.new("DiagSun", 'SUN')
sun.energy = 8.0
sun.color = (1.0, 0.98, 0.95)
sun_obj = bpy.data.objects.new("DiagSun", sun)
bpy.context.collection.objects.link(sun_obj)
sun_obj.rotation_euler = (math.radians(45), math.radians(15), math.radians(-30))

# Area light from inside atrium pointing at Wing A wall
area = bpy.data.lights.new("DiagArea", 'AREA')
area.energy = 500
area.size = 10 * FT
area.color = (1.0, 1.0, 1.0)
area_obj = bpy.data.objects.new("DiagArea", area)
bpy.context.collection.objects.link(area_obj)
# Place in center of atrium at eye level, pointing toward Wing A
area_obj.location = (0, 0, 3 * FT)
area_obj.rotation_euler = (math.radians(90), 0, math.radians(-60))

# Another area light for Wing B
area2 = bpy.data.lights.new("DiagArea2", 'AREA')
area2.energy = 500
area2.size = 10 * FT
area2.color = (1.0, 1.0, 1.0)
area2_obj = bpy.data.objects.new("DiagArea2", area2)
bpy.context.collection.objects.link(area2_obj)
area2_obj.location = (0, 0, 3 * FT)
area2_obj.rotation_euler = (math.radians(90), 0, math.radians(60))

# White world background for maximum visibility
world = bpy.context.scene.world
if not world:
    world = bpy.data.worlds.new("DiagWorld")
    bpy.context.scene.world = world
world.use_nodes = True
bg = world.node_tree.nodes.get("Background")
if bg:
    bg.inputs["Color"].default_value = (0.8, 0.8, 0.8, 1.0)
    bg.inputs["Strength"].default_value = 2.0

print("[4] Set up bright lighting")

# ---- Step 5: Configure render settings ----
scene = bpy.context.scene
scene.render.engine = 'CYCLES'
scene.cycles.device = 'GPU'
scene.cycles.samples = 64
scene.render.resolution_x = 1920
scene.render.resolution_y = 1080
scene.render.film_transparent = False
scene.view_settings.view_transform = 'Standard'

# ---- Step 6: Create camera and render diagnostic views ----
cam_data = bpy.data.cameras.new("DiagCam")
cam_data.type = 'PERSP'
cam_data.lens = 24  # wide angle
cam_data.clip_start = 0.01
cam_data.clip_end = 500
cam_obj = bpy.data.objects.new("DiagCam", cam_data)
bpy.context.collection.objects.link(cam_obj)
scene.camera = cam_obj

renders_dir = os.path.join(PROJECT, "renders")
os.makedirs(renders_dir, exist_ok=True)

# Wing A atrium edge midpoint: midpoint of v5→v0 = mid((11.5,-19.92),(23,0)) = (17.25, -9.96)
# Camera in atrium center (0,0) at standing height (5ft), looking toward Wing A wall base
# Look target: the wall base at the midpoint of Wing A atrium edge, at marble height

# View 1: Standing in atrium center, looking at Wing A wall-floor junction
cam_obj.location = (0, 0, 5.0 * FT)
# Point camera at Wing A midpoint at floor level
target_a = __import__('mathutils').Vector((17.25 * FT, -9.96 * FT, -0.5 * FT))
direction = target_a - cam_obj.location
rot_quat = direction.to_track_quat('-Z', 'Y')
cam_obj.rotation_euler = rot_quat.to_euler()

scene.render.filepath = os.path.join(renders_dir, "_diag_wing_a_base.png")
bpy.ops.render.render(write_still=True)
print(f"[5] Rendered Wing A base view: {scene.render.filepath}")

# View 2: Same for Wing B
# Wing B atrium edge midpoint: mid(v3→v4) = mid((-23,0),(-11.5,-19.92)) = (-17.25, -9.96)
target_b = __import__('mathutils').Vector((-17.25 * FT, -9.96 * FT, -0.5 * FT))
direction_b = target_b - cam_obj.location
rot_quat_b = direction_b.to_track_quat('-Z', 'Y')
cam_obj.rotation_euler = rot_quat_b.to_euler()

scene.render.filepath = os.path.join(renders_dir, "_diag_wing_b_base.png")
bpy.ops.render.render(write_still=True)
print(f"[6] Rendered Wing B base view: {scene.render.filepath}")

# View 3: Close-up of Wing A wall-floor junction from slightly closer
cam_obj.location = (8 * FT, -5 * FT, 2 * FT)
target_close = __import__('mathutils').Vector((17.25 * FT, -9.96 * FT, -0.5 * FT))
direction_c = target_close - cam_obj.location
rot_quat_c = direction_c.to_track_quat('-Z', 'Y')
cam_obj.rotation_euler = rot_quat_c.to_euler()

scene.render.filepath = os.path.join(renders_dir, "_diag_wing_a_closeup.png")
bpy.ops.render.render(write_still=True)
print(f"[7] Rendered Wing A closeup: {scene.render.filepath}")

# View 4: Wide panoramic from atrium center showing both wings
cam_data.lens = 18  # ultra wide
cam_obj.location = (0, -5 * FT, 4 * FT)
# Look straight back toward Wing C with wings visible on sides
target_wide = __import__('mathutils').Vector((0, 5 * FT, 0))
direction_w = target_wide - cam_obj.location
rot_quat_w = direction_w.to_track_quat('-Z', 'Y')
cam_obj.rotation_euler = rot_quat_w.to_euler()

scene.render.filepath = os.path.join(renders_dir, "_diag_wide_atrium.png")
bpy.ops.render.render(write_still=True)
print(f"[8] Rendered wide atrium view: {scene.render.filepath}")

print("\n=== ALL DIAGNOSTIC RENDERS COMPLETE ===")
