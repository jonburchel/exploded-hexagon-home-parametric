import bpy
import os
import mathutils

ft = 0.3048
out_path = r"F:\home\exploded-hexagon-home\renders\gap_review_atrium_eye56_material.png"

window = None
screen = None
area = None
region = None
space = None

for w in bpy.context.window_manager.windows:
    s = w.screen
    for a in s.areas:
        if a.type != "VIEW_3D":
            continue
        for r in a.regions:
            if r.type == "WINDOW":
                window = w
                screen = s
                area = a
                region = r
                space = a.spaces.active
                break
        if area is not None:
            break
    if area is not None:
        break

if area is None:
    raise RuntimeError("No VIEW_3D area found; open a 3D viewport and retry.")

eye = mathutils.Vector((0.0, 0.0, (-1.0 + 5.5) * ft))
# Atrium center, facing Wing C midpoint (v1↔v2), slightly below horizon.
target = mathutils.Vector((0.0, ((19.918584 + 19.918584) * 0.5) * ft, 3.0 * ft))
forward = (target - eye).normalized()
quat = forward.to_track_quat("-Z", "Y")

region_3d = space.region_3d
region_3d.view_perspective = "PERSP"
region_3d.view_location = eye
region_3d.view_rotation = quat
region_3d.view_distance = 0.0

space.shading.type = "MATERIAL"
space.shading.use_scene_lights = False
space.shading.use_scene_world = False

os.makedirs(os.path.dirname(out_path), exist_ok=True)
with bpy.context.temp_override(window=window, screen=screen, area=area, region=region):
    bpy.ops.screen.screenshot(filepath=out_path)
print(out_path)
