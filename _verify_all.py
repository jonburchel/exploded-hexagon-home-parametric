import bpy, math, os
from mathutils import Vector

FT = 0.3048
OUT = r"F:\home\exploded-hexagon-home\renders"

# Camera at atrium center, eye level above marble floor
cam_pos = Vector((0, 0, (-1 + 5.5) * FT))  # marble at z=-1ft, eye 5.5ft above

# Hex vertices (s=23, flat-top, CCW)
# v0=(23,0), v1=(11.5,19.92), v2=(-11.5,19.92), v3=(-23,0), v4=(-11.5,-19.92), v5=(11.5,-19.92)
targets = {
    # Non-wing glass edges (where the teal band was)
    "glass_v0v1": Vector(((23+11.5)/2*FT, (0+19.92)/2*FT, -1*FT)),    # upper-right
    "glass_v2v3": Vector(((-11.5-23)/2*FT, (19.92+0)/2*FT, -1*FT)),    # upper-left
    "glass_v4v5": Vector(((-11.5+11.5)/2*FT, (-19.92-19.92)/2*FT, -1*FT)),  # bottom
    # Wing edges (should already be clean)
    "wing_a": Vector(((11.5+23)/2*FT, (-19.92+0)/2*FT, -1*FT)),        # lower-right
    "wing_b": Vector(((-23-11.5)/2*FT, (0-19.92)/2*FT, -1*FT)),        # lower-left
}

cam = bpy.data.objects.get("VerifyCam")
if not cam:
    cam_data = bpy.data.cameras.new("VerifyCam")
    cam = bpy.data.objects.new("VerifyCam", cam_data)
    bpy.context.scene.collection.objects.link(cam)
cam.data.lens = 35
cam.data.clip_start = 0.01
cam.data.clip_end = 500

bpy.context.scene.camera = cam
bpy.context.scene.render.engine = 'CYCLES'
bpy.context.scene.cycles.samples = 64
bpy.context.scene.render.resolution_x = 1280
bpy.context.scene.render.resolution_y = 720

for name, target in targets.items():
    cam.location = cam_pos
    direction = target - cam_pos
    rot = direction.to_track_quat('-Z', 'Y')
    cam.rotation_euler = rot.to_euler()
    
    filepath = os.path.join(OUT, f"_verify_{name}.png")
    bpy.context.scene.render.filepath = filepath
    bpy.ops.render.render(write_still=True)
    print(f"Rendered: {filepath}")

print("All verification renders complete!")
