"""Diagnostic renders from atrium center to analyze wall issues."""
import bpy, os, math
from mathutils import Vector, Euler

out_dir = r"F:\home\exploded-hexagon-home\renders"
os.makedirs(out_dir, exist_ok=True)

scene = bpy.context.scene
scene.render.engine = 'BLENDER_EEVEE'
scene.render.resolution_x = 1920
scene.render.resolution_y = 1080

# Ensure we have a camera
cam = bpy.data.objects.get('DiagCam')
if cam is None:
    cam_data = bpy.data.cameras.new('DiagCam')
    cam = bpy.data.objects.new('DiagCam', cam_data)
    bpy.context.collection.objects.link(cam)
cam.data.type = 'PERSP'
cam.data.lens = 24  # wide angle for interior
scene.camera = cam

# Atrium center in Blender coords (meters, GLB has Y-up convention)
# Hex center is (0,0), atrium floor marble at z=-1ft = -0.3048m
# In Blender after GLB import: X=X, Y=Z(up), Z=-Y
FT = 0.3048
eye_height = 5.5 * FT  # standing height above marble floor
marble_z = -1 * FT
cam_y_blender = marble_z + eye_height  # Y is up in Blender after GLB import

# Camera at atrium center
cam_pos = Vector((0, cam_y_blender, 0))

views = {
    # Looking toward Wing C (hex v1→v2 edge, positive Z in plan = negative Z in Blender)
    "diag_toward_wingc": {
        "pos": Vector((0, cam_y_blender, 0)),
        "target": Vector((0, cam_y_blender, -20 * FT)),  # Wing C is in +Y plan direction = -Z Blender
    },
    # Looking toward Wing A (hex v5→v0 edge, plan direction ~(-30°) from +X)
    "diag_toward_winga": {
        "pos": Vector((0, cam_y_blender, 0)),
        "target": Vector((20 * FT, cam_y_blender, 10 * FT)),  # Wing A is in -Y plan direction = +Z Blender, +X
    },
    # Looking toward Wing B (hex v3→v4 edge)  
    "diag_toward_wingb": {
        "pos": Vector((0, cam_y_blender, 0)),
        "target": Vector((-20 * FT, cam_y_blender, 10 * FT)),  # Wing B is in -Y plan = +Z Blender, -X
    },
    # Looking DOWN at the floor near Wing A wall base
    "diag_floor_winga": {
        "pos": Vector((10 * FT, 3 * FT, 5 * FT)),
        "target": Vector((15 * FT, marble_z, 5 * FT)),
    },
    # Looking DOWN at the floor near Wing B wall base
    "diag_floor_wingb": {
        "pos": Vector((-10 * FT, 3 * FT, 5 * FT)),
        "target": Vector((-15 * FT, marble_z, 5 * FT)),
    },
    # Low angle from center toward Wing C, looking at wall-floor junction
    "diag_wingc_base": {
        "pos": Vector((0, 1 * FT, 2 * FT)),
        "target": Vector((0, marble_z, -15 * FT)),
    },
}

for name, v in views.items():
    cam.location = v["pos"]
    direction = v["target"] - v["pos"]
    rot = direction.to_track_quat('-Z', 'Y')
    cam.rotation_euler = rot.to_euler()
    
    filepath = os.path.join(out_dir, f"{name}.png")
    scene.render.filepath = filepath
    bpy.ops.render.render(write_still=True)
    print(f"Rendered: {filepath}")

print("All diagnostic renders complete")
