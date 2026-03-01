"""Diagnostic: reload GLB, render close-ups of Wing A/B wall bases from atrium center."""
import bpy, bmesh, math, os
from mathutils import Vector

FT = 0.3048
PROJECT = r"F:\home\exploded-hexagon-home"
GLB = os.path.join(PROJECT, "out", "massing_s23_d7.glb")

# --- Step 1: Reload GLB ---
for obj in list(bpy.data.objects):
    bpy.data.objects.remove(obj, do_unlink=True)
for m in list(bpy.data.meshes):
    bpy.data.meshes.remove(m)
for mat in list(bpy.data.materials):
    bpy.data.materials.remove(mat)

bpy.ops.import_scene.gltf(filepath=GLB)
print(f"Imported {len(bpy.data.objects)} objects")

# --- Step 2: List all objects near Wing A and B atrium edges ---
# Wing A atrium edge midpoint: (17.25, -9.96) * FT
# Wing B atrium edge midpoint: (-17.25, -9.96) * FT
wing_a_mid = Vector((17.25 * FT, -9.96 * FT, 0))
wing_b_mid = Vector((-17.25 * FT, -9.96 * FT, 0))

print("\n=== Objects near Wing A atrium edge ===")
for obj in bpy.data.objects:
    if obj.type != 'MESH':
        continue
    # Check if any vertices are near wing A edge
    me = obj.data
    near = False
    z_vals = []
    for v in me.vertices:
        wv = obj.matrix_world @ v.co
        dist_xy = math.hypot(wv.x - wing_a_mid.x, wv.y - wing_a_mid.y)
        if dist_xy < 2.0 * FT:
            near = True
            z_vals.append(wv.z)
    if near and z_vals:
        print(f"  {obj.name}: z={min(z_vals)/FT:.2f}' to {max(z_vals)/FT:.2f}' ({len(z_vals)} verts)")

print("\n=== Objects near Wing B atrium edge ===")
for obj in bpy.data.objects:
    if obj.type != 'MESH':
        continue
    me = obj.data
    near = False
    z_vals = []
    for v in me.vertices:
        wv = obj.matrix_world @ v.co
        dist_xy = math.hypot(wv.x - wing_b_mid.x, wv.y - wing_b_mid.y)
        if dist_xy < 2.0 * FT:
            near = True
            z_vals.append(wv.z)
    if near and z_vals:
        print(f"  {obj.name}: z={min(z_vals)/FT:.2f}' to {max(z_vals)/FT:.2f}' ({len(z_vals)} verts)")

# --- Step 3: Render from user's perspective ---
# User says "I'm in the middle of the atrium facing Wing C"
# That means looking toward +Y, with Wing A to right and Wing B to left
# Let's render with camera at atrium center, eye level, looking at Wing A wall base
# and another looking at Wing B wall base

bpy.context.scene.render.engine = 'CYCLES'
bpy.context.scene.cycles.device = 'GPU'
bpy.context.scene.cycles.samples = 64
bpy.context.scene.render.resolution_x = 1920
bpy.context.scene.render.resolution_y = 1080

cam_data = bpy.data.cameras.new("DiagCam")
cam_data.lens = 35
cam_obj = bpy.data.objects.new("DiagCam", cam_data)
bpy.context.scene.collection.objects.link(cam_obj)
bpy.context.scene.camera = cam_obj

# Add basic lighting
sun_data = bpy.data.lights.new("DiagSun", 'SUN')
sun_data.energy = 3.0
sun_obj = bpy.data.objects.new("DiagSun", sun_data)
sun_obj.rotation_euler = (math.radians(45), 0, math.radians(30))
bpy.context.scene.collection.objects.link(sun_obj)

# Apply textures
exec(open(os.path.join(PROJECT, "src", "apply_textures_v2.py")).read())

def look_at(cam, target, up=Vector((0, 0, 1))):
    direction = target - cam.location
    rot_quat = direction.to_track_quat('-Z', 'Y')
    cam.rotation_euler = rot_quat.to_euler()

renders_dir = os.path.join(PROJECT, "renders")

# View 1: From atrium center, looking toward Wing A wall base
# Camera at atrium center, slightly above marble (z=-0.5 ft), looking at Wing A edge at floor level
cam_pos = Vector((0, 0, -0.5 * FT))  # atrium center, just above marble
target_a = Vector((17.25 * FT, -9.96 * FT, -1.0 * FT))  # Wing A edge at marble level
cam_obj.location = cam_pos
look_at(cam_obj, target_a)
bpy.context.scene.render.filepath = os.path.join(renders_dir, "_gap_wing_a.png")
bpy.ops.render.render(write_still=True)
print(f"Rendered: _gap_wing_a.png")

# View 2: Looking at Wing B wall base
target_b = Vector((-17.25 * FT, -9.96 * FT, -1.0 * FT))
cam_obj.location = cam_pos
look_at(cam_obj, target_b)
bpy.context.scene.render.filepath = os.path.join(renders_dir, "_gap_wing_b.png")
bpy.ops.render.render(write_still=True)
print(f"Rendered: _gap_wing_b.png")

# View 3: From atrium center, looking toward Wing C, wider FOV to see Wing A and B bases on sides
cam_data.lens = 18  # wider FOV
cam_pos_wide = Vector((0, -5 * FT, 3 * FT))  # slightly back from center, 3ft above marble
target_c = Vector((0, 19.92 * FT, -1.0 * FT))  # toward Wing C
cam_obj.location = cam_pos_wide
look_at(cam_obj, target_c)
bpy.context.scene.render.filepath = os.path.join(renders_dir, "_gap_wide.png")
bpy.ops.render.render(write_still=True)
print(f"Rendered: _gap_wide.png")

# View 4: Higher up, looking down at the floor-wall junction for Wing A
cam_pos_high = Vector((10 * FT, -5 * FT, 5 * FT))
target_floor_a = Vector((17.25 * FT, -9.96 * FT, -1.0 * FT))
cam_obj.location = cam_pos_high
cam_data.lens = 50
look_at(cam_obj, target_floor_a)
bpy.context.scene.render.filepath = os.path.join(renders_dir, "_gap_wing_a_high.png")
bpy.ops.render.render(write_still=True)
print(f"Rendered: _gap_wing_a_high.png")

print("\n=== DONE - check renders/ for _gap_*.png ===")
