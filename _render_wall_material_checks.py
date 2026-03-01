import bpy
import os

Vector = __import__("mathutils").Vector
ft = 0.3048
out_dir = r"F:\home\exploded-hexagon-home\renders"
os.makedirs(out_dir, exist_ok=True)

scene = bpy.context.scene
scene.render.engine = "CYCLES"
scene.cycles.samples = 48
scene.render.resolution_x = 1280
scene.render.resolution_y = 720
scene.render.image_settings.file_format = "PNG"

cam = bpy.data.objects.get("MatCheckCam")
if cam is None:
    cam_data = bpy.data.cameras.new("MatCheckCam")
    cam = bpy.data.objects.new("MatCheckCam", cam_data)
    scene.collection.objects.link(cam)
cam.data.type = "PERSP"
cam.data.lens = 32
cam.data.clip_start = 0.01
cam.data.clip_end = 500
scene.camera = cam


def _render(name: str, eye: Vector, target: Vector) -> None:
    cam.location = eye
    cam.rotation_euler = (target - eye).to_track_quat("-Z", "Y").to_euler()
    scene.render.filepath = os.path.join(out_dir, name)
    bpy.ops.render.render(write_still=True)
    print(scene.render.filepath)


obj = bpy.data.objects.get("bedroom_accent_wall")
if obj:
    bbox = []
    for bb in obj.bound_box:
        bbox.append(obj.matrix_world @ Vector(bb))
    accum = Vector((0.0, 0.0, 0.0))
    min_x = 1e9
    max_x = -1e9
    min_y = 1e9
    max_y = -1e9
    min_z = 1e9
    max_z = -1e9
    for v in bbox:
        accum += v
        if v.x < min_x:
            min_x = v.x
        if v.x > max_x:
            max_x = v.x
        if v.y < min_y:
            min_y = v.y
        if v.y > max_y:
            max_y = v.y
        if v.z < min_z:
            min_z = v.z
        if v.z > max_z:
            max_z = v.z
    center = accum / max(len(bbox), 1)
    sx = max_x - min_x
    sy = max_y - min_y
    sz = max_z - min_z
    span = max(sx, sy, sz)
    room_dir = Vector((-0.8660254, -0.5, 0.0)).normalized()
    target = center + Vector((0.0, 0.0, sz * 0.08))
    _render("accent_wall_atrium_side_material.png", center - room_dir * (span * 1.8), target)
    _render("accent_wall_room_side_material.png", center + room_dir * (span * 1.8), target)
else:
    print("bedroom_accent_wall not found")

eye = Vector((0.0, 0.0, 5.5 * ft))
_render("atrium_top_band_nonwing_material.png", eye, Vector((17.25 * ft, 9.96 * ft, 41.0 * ft)))
_render("atrium_top_band_wingb_material.png", eye, Vector((-17.25 * ft, -9.96 * ft, 41.0 * ft)))
