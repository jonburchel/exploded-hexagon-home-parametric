import bpy
import os

out_dir = r'F:\home\exploded-hexagon-home\renders'
os.makedirs(out_dir, exist_ok=True)

scene = bpy.context.scene
scene.render.engine = 'BLENDER_EEVEE'
scene.render.resolution_x = 1280
scene.render.resolution_y = 720

# Get or create camera
cam = bpy.data.objects.get('DiagCam')
if cam is None:
    cam_data = bpy.data.cameras.new('DiagCam')
    cam = bpy.data.objects.new('DiagCam', cam_data)
    bpy.context.collection.objects.link(cam)
cam_data = cam.data
cam_data.type = 'PERSP'
cam_data.lens = 24

from mathutils import Vector, Euler
import math

FT = 0.3048
scene.camera = cam

# View 1: Inside atrium facing Wing C (the user's POV from screenshots)
cam.location = Vector((0, -5*FT, 3*FT))
cam.rotation_euler = Euler((math.radians(80), 0, 0), 'XYZ')
scene.render.filepath = os.path.join(out_dir, 'diag_atrium_wing_c.png')
bpy.ops.render.render(write_still=True)

# View 2: Inside atrium looking LEFT (toward Wing B / wall base)
cam.location = Vector((0, 5*FT, 0*FT))
cam.rotation_euler = Euler((math.radians(90), 0, math.radians(-90)), 'XYZ')
scene.render.filepath = os.path.join(out_dir, 'diag_atrium_left.png')
bpy.ops.render.render(write_still=True)

# View 3: Inside atrium looking RIGHT (toward Wing A / wall base)
cam.location = Vector((0, 5*FT, 0*FT))
cam.rotation_euler = Euler((math.radians(90), 0, math.radians(90)), 'XYZ')
scene.render.filepath = os.path.join(out_dir, 'diag_atrium_right.png')
bpy.ops.render.render(write_still=True)

# View 4: Low angle looking at wing A/B base walls from atrium center
cam.location = Vector((0, 0, -0.5*FT))
cam.rotation_euler = Euler((math.radians(95), 0, math.radians(45)), 'XYZ')
scene.render.filepath = os.path.join(out_dir, 'diag_atrium_base.png')
bpy.ops.render.render(write_still=True)

print('Diagnostic renders complete: 4 views')