"""Reload GLB and render close-up diagnostic of Wing A and Wing B
atrium-facing walls from inside the atrium, focusing on the floor junction."""
import bpy, math, os

FT = 0.3048
GLB = r"F:\home\exploded-hexagon-home\out\massing_s23_d7.glb"
OUT_DIR = r"F:\home\exploded-hexagon-home\renders"

# --- Reload GLB ---
# Remove old building objects
for obj in list(bpy.data.objects):
    if obj.type == 'MESH':
        bpy.data.objects.remove(obj, do_unlink=True)
for m in list(bpy.data.meshes):
    if m.users == 0:
        bpy.data.meshes.remove(m)

bpy.ops.import_scene.gltf(filepath=GLB)
print(f"Imported GLB: {len([o for o in bpy.data.objects if o.type=='MESH'])} mesh objects")

# List all mesh objects to see what's in the scene
for obj in sorted(bpy.data.objects, key=lambda o: o.name):
    if obj.type == 'MESH':
        bb = obj.bound_box
        zs = [v[2] for v in bb]
        print(f"  {obj.name}: z=[{min(zs)/FT:.1f}, {max(zs)/FT:.1f}]ft")

# --- Apply textures ---
ns = {"__name__": "__main__"}
exec(open(r"F:\home\exploded-hexagon-home\src\apply_textures_v2.py").read(), ns)

# --- Setup render ---
scene = bpy.context.scene
scene.render.engine = 'CYCLES'
scene.cycles.samples = 128
scene.render.resolution_x = 1920
scene.render.resolution_y = 1080
scene.cycles.device = 'GPU'

# Get or create camera
cam = bpy.data.objects.get("DiagCam")
if cam is None:
    cam_data = bpy.data.cameras.new("DiagCam")
    cam = bpy.data.objects.new("DiagCam", cam_data)
    bpy.context.collection.objects.link(cam)
cam_data = cam.data
cam_data.type = 'PERSP'
cam_data.lens = 24  # wide angle for interior
scene.camera = cam

# Wing A atrium edge midpoint: midpoint of v5=(11.5,-19.92) and v0=(23,0)
# = (17.25, -9.96)
# Wing B atrium edge midpoint: midpoint of v3=(-23,0) and v4=(-11.5,-19.92)
# = (-17.25, -9.96)

# Camera at atrium center (0, 0, -1ft) = at marble surface level
# Looking toward Wing A wall base
views = {
    "wing_a_base": {
        "loc": (0, 0, -0.5 * FT),  # slightly above marble surface
        "target": (17.25 * FT, -9.96 * FT, -1.0 * FT),  # marble surface at wing A edge
    },
    "wing_b_base": {
        "loc": (0, 0, -0.5 * FT),
        "target": (-17.25 * FT, -9.96 * FT, -1.0 * FT),
    },
    "wing_c_base": {
        "loc": (0, 0, -0.5 * FT),
        "target": (0, 19.92 * FT, -1.0 * FT),  # Wing C edge midpoint
    },
}

from mathutils import Vector

for name, v in views.items():
    loc = Vector(v["loc"])
    tgt = Vector(v["target"])
    cam.location = loc
    direction = tgt - loc
    rot = direction.to_track_quat('-Z', 'Y')
    cam.rotation_euler = rot.to_euler()
    
    # Tilt camera down to look at the floor junction
    cam.rotation_euler.x += math.radians(15)  # tilt down more
    
    scene.render.filepath = os.path.join(OUT_DIR, f"_diag_{name}.png")
    bpy.ops.render.render(write_still=True)
    print(f"Rendered: {name}")

print("DONE - all diagnostic renders complete")
