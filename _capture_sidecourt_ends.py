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

# Right side courtyard outer wall termination
eye = Vector((62.0 * ft, 12.0 * ft, 8.0 * ft))
target = Vector((46.0 * ft, 39.8 * ft, 4.0 * ft))
forward = (target - eye).normalized()
r3d.view_location = eye
r3d.view_rotation = forward.to_track_quat("-Z", "Y")
r3d.view_distance = 0.0
out_path = os.path.join(out_dir, "side_court_right_end_material.png")
with bpy.context.temp_override(window=window, screen=screen, area=area, region=region):
    bpy.ops.screen.screenshot(filepath=out_path)
print(out_path)

# Left side courtyard outer wall termination
eye = Vector((-62.0 * ft, 12.0 * ft, 8.0 * ft))
target = Vector((-46.0 * ft, 39.8 * ft, 4.0 * ft))
forward = (target - eye).normalized()
r3d.view_location = eye
r3d.view_rotation = forward.to_track_quat("-Z", "Y")
r3d.view_distance = 0.0
out_path = os.path.join(out_dir, "side_court_left_end_material.png")
with bpy.context.temp_override(window=window, screen=screen, area=area, region=region):
    bpy.ops.screen.screenshot(filepath=out_path)
print(out_path)
