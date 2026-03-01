import bpy
from mathutils import Vector
import os

FT = 0.3048
OUT = r"F:\home\exploded-hexagon-home\renders"

scene = bpy.context.scene
scene.render.engine = 'BLENDER_EEVEE'
scene.render.resolution_x = 1280
scene.render.resolution_y = 720
scene.eevee.taa_render_samples = 64

cam = bpy.data.objects.get('Camera')
if not cam:
    cam_data = bpy.data.cameras.new('DiagCam')
    cam = bpy.data.objects.new('DiagCam', cam_data)
    bpy.context.collection.objects.link(cam)
else:
    cam_data = cam.data

cam_data.type = 'PERSP'
cam_data.lens = 24
scene.camera = cam

views = {
    'diag_corner_wingc': {
        'loc': (0, 0, -0.5 * FT),
        'target': (0, 19.92 * FT, 0),
    },
    'diag_corner_winga': {
        'loc': (0, 0, -0.5 * FT),
        'target': (23 * FT, 0, 0),
    },
    'diag_corner_wingb': {
        'loc': (0, 0, -0.5 * FT),
        'target': (-23 * FT, 0, 0),
    },
    'diag_wall_base_low': {
        'loc': (0, -5 * FT, -1.5 * FT),
        'target': (23 * FT, 0, -1 * FT),
    },
}

for name, v in views.items():
    cam.location = Vector(v['loc'])
    target = Vector(v['target'])
    direction = target - cam.location
    cam.rotation_euler = direction.to_track_quat('-Z', 'Y').to_euler()
    
    scene.render.filepath = os.path.join(OUT, f'{name}.png')
    bpy.ops.render.render(write_still=True)
    print(f'Rendered {name}')

print('All diagnostic views rendered')
