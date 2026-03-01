"""Render verification: atrium floor-wall junction from center."""
import bpy, os
from mathutils import Vector

FT = 0.3048
out_dir = os.path.join(os.path.dirname(bpy.data.filepath) or "F:/home/exploded-hexagon-home", "renders")
os.makedirs(out_dir, exist_ok=True)

# Get or create camera
cam_obj = bpy.data.objects.get("VerifyCam")
if not cam_obj:
    cam_data = bpy.data.cameras.new("VerifyCam")
    cam_obj = bpy.data.objects.new("VerifyCam", cam_data)
    bpy.context.scene.collection.objects.link(cam_obj)

cam_data = cam_obj.data
cam_data.type = 'PERSP'
cam_data.lens = 24
cam_data.clip_start = 0.1
cam_data.clip_end = 500

bpy.context.scene.camera = cam_obj
bpy.context.scene.render.engine = 'CYCLES'
bpy.context.scene.cycles.samples = 128
bpy.context.scene.render.resolution_x = 1920
bpy.context.scene.render.resolution_y = 1080

# Position: center of atrium at eye level, looking toward Wing A (lower-right, toward v5-v0 edge)
eye = Vector((0, 0, -0.5)) * FT  # slightly below marble surface level to see junction
look = Vector((17.25, -9.96, -1.0)) * FT  # Wing A midpoint at floor level
cam_obj.location = eye
direction = look - eye
cam_obj.rotation_euler = direction.to_track_quat('-Z', 'Y').to_euler()

bpy.context.scene.render.filepath = os.path.join(out_dir, "_verify_wall_base.png")
bpy.ops.render.render(write_still=True)

# Also render looking at Wing B (lower-left)
look_b = Vector((-17.25, -9.96, -1.0)) * FT
direction_b = look_b - eye
cam_obj.rotation_euler = direction_b.to_track_quat('-Z', 'Y').to_euler()
bpy.context.scene.render.filepath = os.path.join(out_dir, "_verify_wall_base_b.png")
bpy.ops.render.render(write_still=True)

print("DONE: verification renders saved")
