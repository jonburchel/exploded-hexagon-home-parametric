import bpy, math, os
from mathutils import Vector

FT = 0.3048

# Camera setup - looking from atrium center toward Wing A wall base
cam = bpy.data.objects.get('VerifyCam')
if cam is None:
    cam_data = bpy.data.cameras.new('VerifyCam')
    cam = bpy.data.objects.new('VerifyCam', cam_data)
    bpy.context.scene.collection.objects.link(cam)

cam_data = cam.data
cam_data.type = 'PERSP'
cam_data.lens = 24

# Position at atrium center, eye level above the marble floor (-1ft surface)
cam.location = (0, 0, (-1 + 5.5) * FT)  # 5.5ft above marble

# Look toward Wing A (which is in the +X, -Y direction)
# hex vertex 5 is at (11.5, -19.92), vertex 0 at (23, 0)
# Midpoint of Wing A atrium edge: midpoint of v5 to v0
target_x = (11.5 + 23) / 2 * FT   # ~17.25ft converted
target_y = (-19.92 + 0) / 2 * FT   # ~-9.96ft converted
target_z = -1 * FT                  # marble floor level

direction = Vector((target_x, target_y, target_z)) - cam.location
rot = direction.to_track_quat('-Z', 'Y')
cam.rotation_euler = rot.to_euler()

bpy.context.scene.camera = cam

# Render settings
scene = bpy.context.scene
scene.render.engine = 'CYCLES'
scene.cycles.samples = 128
scene.render.resolution_x = 1280
scene.render.resolution_y = 720
scene.cycles.use_denoising = True

# Render Wing A view
out_a = r"F:\home\exploded-hexagon-home\renders\_verify_wall_base_a.png"
scene.render.filepath = out_a
bpy.ops.render.render(write_still=True)
print(f"Rendered: {out_a}")

# Now look at Wing B (mirror: +X, +Y direction)
target_x_b = (11.5 + 23) / 2 * FT
target_y_b = (19.92 + 0) / 2 * FT
target_z_b = -1 * FT
direction_b = Vector((target_x_b, target_y_b, target_z_b)) - cam.location
rot_b = direction_b.to_track_quat('-Z', 'Y')
cam.rotation_euler = rot_b.to_euler()

out_b = r"F:\home\exploded-hexagon-home\renders\_verify_wall_base_b.png"
scene.render.filepath = out_b
bpy.ops.render.render(write_still=True)
print(f"Rendered: {out_b}")

# Also look straight at Wing C (the center, -X direction)
target_x_c = -23 * FT
target_y_c = 0
target_z_c = -1 * FT
direction_c = Vector((target_x_c, target_y_c, target_z_c)) - cam.location
rot_c = direction_c.to_track_quat('-Z', 'Y')
cam.rotation_euler = rot_c.to_euler()

out_c = r"F:\home\exploded-hexagon-home\renders\_verify_wall_base_c.png"
scene.render.filepath = out_c
bpy.ops.render.render(write_still=True)
print(f"Rendered: {out_c}")
