import bpy
import os

ft = 0.3048
Vector = __import__("mathutils").Vector
out_dir = r"F:\home\exploded-hexagon-home\renders"
os.makedirs(out_dir, exist_ok=True)

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

space.shading.type = "MATERIAL"
space.shading.use_scene_lights = False
space.shading.use_scene_world = False
r3d = space.region_3d
r3d.view_perspective = "PERSP"

target = Vector((-17.25 * ft, -9.96 * ft, 31.0 * ft))

# Atrium side view (should be concrete)
eye = Vector((-6.0 * ft, -4.0 * ft, 30.0 * ft))
fwd = (target - eye).normalized()
r3d.view_location = eye
r3d.view_rotation = fwd.to_track_quat("-Z", "Y")
r3d.view_distance = 0.0
out_path = os.path.join(out_dir, "accent_wall_atrium_side_material.png")
with bpy.context.temp_override(window=window, screen=screen, area=area, region=region):
    bpy.ops.screen.screenshot(filepath=out_path)
print(out_path)

# Room side view (should keep accent)
eye = Vector((-30.0 * ft, -17.0 * ft, 31.0 * ft))
fwd = (target - eye).normalized()
r3d.view_location = eye
r3d.view_rotation = fwd.to_track_quat("-Z", "Y")
r3d.view_distance = 0.0
out_path = os.path.join(out_dir, "accent_wall_room_side_material.png")
with bpy.context.temp_override(window=window, screen=screen, area=area, region=region):
    bpy.ops.screen.screenshot(filepath=out_path)
print(out_path)
