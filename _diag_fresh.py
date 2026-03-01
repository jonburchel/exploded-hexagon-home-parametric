import bpy, os, math

# Remove old DiagCam if exists
for o in list(bpy.data.objects):
    if o.name.startswith("DiagCam"):
        bpy.data.objects.remove(o, do_unlink=True)

cam_data = bpy.data.cameras.new("DiagCam")
cam_data.type = 'PERSP'
cam_data.lens = 24
cam_obj = bpy.data.objects.new("DiagCam", cam_data)
bpy.context.scene.collection.objects.link(cam_obj)

FT = 0.3048
cam_obj.location = (0 * FT, -5 * FT, 2 * FT)
cam_obj.rotation_euler = (math.radians(80), 0, 0)
bpy.context.scene.camera = cam_obj

bpy.context.scene.render.engine = 'BLENDER_EEVEE'
bpy.context.scene.render.resolution_x = 1280
bpy.context.scene.render.resolution_y = 720
bpy.context.scene.render.film_transparent = False

out = r"F:\home\exploded-hexagon-home\renders\diag_atrium_wing_c_fresh.png"
bpy.context.scene.render.filepath = out
bpy.ops.render.render(write_still=True)

cam_obj.rotation_euler = (math.radians(80), 0, math.radians(-60))
out2 = r"F:\home\exploded-hexagon-home\renders\diag_atrium_wing_a.png"
bpy.context.scene.render.filepath = out2
bpy.ops.render.render(write_still=True)

cam_obj.rotation_euler = (math.radians(80), 0, math.radians(60))
out3 = r"F:\home\exploded-hexagon-home\renders\diag_atrium_wing_b.png"
bpy.context.scene.render.filepath = out3
bpy.ops.render.render(write_still=True)

cam_obj.location = (0 * FT, 0 * FT, -0.5 * FT)
cam_obj.rotation_euler = (math.radians(90), 0, math.radians(-60))
out4 = r"F:\home\exploded-hexagon-home\renders\diag_wall_base.png"
bpy.context.scene.render.filepath = out4
bpy.ops.render.render(write_still=True)

bpy.data.objects.remove(cam_obj, do_unlink=True)
bpy.data.cameras.remove(cam_data)
print("DIAG_DONE")
