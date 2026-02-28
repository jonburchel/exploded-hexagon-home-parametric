"""
Blender helper utilities for the architecture-3d skill.
Run inside Blender's Python environment.

Usage from skill:
  blender --background --python .github/skills/architecture-3d/blender_helpers.py -- <command> [args]
  
Commands:
  setup-materials <glb_path>   - Import GLB and set up PBR materials
  render-views <output_dir>    - Render top/iso/front views
  walkthrough <glb_path> <output_path> <fps> - Generate walkthrough animation
"""

import sys
import os

def get_args():
    """Get arguments passed after '--' in blender command line."""
    if "--" in sys.argv:
        return sys.argv[sys.argv.index("--") + 1:]
    return []


def setup_materials():
    """Set up high-quality PBR materials for architectural visualization."""
    import bpy

    materials = {
        "glass": {
            "base_color": (0.85, 0.92, 0.95, 0.3),
            "roughness": 0.05,
            "transmission": 0.9,
            "ior": 1.45,
            "metallic": 0.0,
            "blend_method": "BLEND",
        },
        "concrete": {
            "base_color": (0.65, 0.63, 0.60, 1.0),
            "roughness": 0.3,
            "transmission": 0.0,
            "ior": 1.5,
            "metallic": 0.0,
            "blend_method": "OPAQUE",
        },
        "ground": {
            "base_color": (0.25, 0.55, 0.20, 1.0),
            "roughness": 0.8,
            "transmission": 0.0,
            "ior": 1.5,
            "metallic": 0.0,
            "blend_method": "OPAQUE",
        },
        "roof_metal": {
            "base_color": (0.4, 0.4, 0.42, 1.0),
            "roughness": 0.2,
            "transmission": 0.0,
            "ior": 2.0,
            "metallic": 0.9,
            "blend_method": "OPAQUE",
        },
    }

    for name, props in materials.items():
        mat = bpy.data.materials.get(name)
        if mat is None:
            mat = bpy.data.materials.new(name=name)
        mat.use_nodes = True
        bsdf = mat.node_tree.nodes.get("Principled BSDF")
        if bsdf:
            bsdf.inputs["Base Color"].default_value = props["base_color"]
            bsdf.inputs["Roughness"].default_value = props["roughness"]
            if hasattr(bsdf.inputs, "Transmission"):
                bsdf.inputs["Transmission"].default_value = props["transmission"]
            bsdf.inputs["IOR"].default_value = props["ior"]
            bsdf.inputs["Metallic"].default_value = props["metallic"]

        if hasattr(mat, "blend_method"):
            mat.blend_method = props["blend_method"]

    print(f"Set up {len(materials)} PBR materials")


def setup_camera(view_type, scene_center, scene_radius):
    """Configure camera for a specific architectural view."""
    import bpy
    from mathutils import Vector
    import math

    cam = bpy.data.objects.get("Camera")
    if cam is None:
        cam_data = bpy.data.cameras.new("Camera")
        cam = bpy.data.objects.new("Camera", cam_data)
        bpy.context.collection.objects.link(cam)
    
    bpy.context.scene.camera = cam
    cam_data = cam.data
    margin = 1.15

    if view_type == "top":
        cam_data.type = "ORTHO"
        cam_data.ortho_scale = scene_radius * 2 * margin
        cam.location = Vector(scene_center) + Vector((0, 0, scene_radius * 3))
        cam.rotation_euler = (0, 0, 0)

    elif view_type == "iso":
        cam_data.type = "ORTHO"
        cam_data.ortho_scale = scene_radius * 2.5 * margin
        offset = scene_radius * 2
        cam.location = Vector(scene_center) + Vector((offset, -offset, offset))
        cam.rotation_euler = (math.radians(54.7), 0, math.radians(45))

    elif view_type == "front":
        cam_data.type = "ORTHO"
        cam_data.ortho_scale = scene_radius * 2 * margin
        cam.location = Vector(scene_center) + Vector((0, -scene_radius * 3, scene_radius * 0.3))
        cam.rotation_euler = (math.radians(85), 0, 0)

    elif view_type == "hero":
        cam_data.type = "PERSP"
        cam_data.lens = 28
        eye_height = 5.5
        cam.location = Vector(scene_center) + Vector((scene_radius * 1.5, -scene_radius * 1.8, eye_height))
        direction = Vector(scene_center) - cam.location
        cam.rotation_euler = direction.to_track_quat('-Z', 'Y').to_euler()

    return cam


def setup_lighting(preset="daylight"):
    """Configure scene lighting for architectural rendering."""
    import bpy
    from mathutils import Vector
    import math

    # Remove existing lights
    for obj in bpy.data.objects:
        if obj.type == "LIGHT":
            bpy.data.objects.remove(obj, do_unlink=True)

    if preset == "daylight":
        sun_data = bpy.data.lights.new("Sun", "SUN")
        sun_data.energy = 5.0
        sun_data.color = (1.0, 0.97, 0.92)
        sun_data.angle = math.radians(0.5)
        sun = bpy.data.objects.new("Sun", sun_data)
        bpy.context.collection.objects.link(sun)
        sun.rotation_euler = (math.radians(60), math.radians(15), math.radians(-30))

    elif preset == "golden_hour":
        sun_data = bpy.data.lights.new("Sun", "SUN")
        sun_data.energy = 3.0
        sun_data.color = (1.0, 0.85, 0.6)
        sun_data.angle = math.radians(1.0)
        sun = bpy.data.objects.new("Sun", sun_data)
        bpy.context.collection.objects.link(sun)
        sun.rotation_euler = (math.radians(8), 0, math.radians(-45))

    elif preset == "overcast":
        area_data = bpy.data.lights.new("AreaFill", "AREA")
        area_data.energy = 200.0
        area_data.color = (0.95, 0.95, 1.0)
        area_data.size = 50.0
        area = bpy.data.objects.new("AreaFill", area_data)
        bpy.context.collection.objects.link(area)
        area.location = (0, 0, 100)
        area.rotation_euler = (0, 0, 0)


def create_walkthrough_path(waypoints_ft, fps=30, speed_ft_per_sec=4.0):
    """Create a camera walkthrough animation along waypoints.
    
    Args:
        waypoints_ft: list of (x, y, z) tuples in feet
        fps: frames per second
        speed_ft_per_sec: walking speed in feet/second
    """
    import bpy
    from mathutils import Vector
    import math

    # Calculate total path length
    total_length = 0
    for i in range(1, len(waypoints_ft)):
        seg = Vector(waypoints_ft[i]) - Vector(waypoints_ft[i-1])
        total_length += seg.length

    total_seconds = total_length / speed_ft_per_sec
    total_frames = int(total_seconds * fps)

    # Create path curve
    curve_data = bpy.data.curves.new("WalkthroughPath", type="CURVE")
    curve_data.dimensions = "3D"
    spline = curve_data.splines.new("BEZIER")
    spline.bezier_points.add(len(waypoints_ft) - 1)

    for i, wp in enumerate(waypoints_ft):
        bp = spline.bezier_points[i]
        bp.co = Vector(wp)
        bp.handle_type = "AUTO"

    path_obj = bpy.data.objects.new("WalkthroughPath", curve_data)
    bpy.context.collection.objects.link(path_obj)
    curve_data.path_duration = total_frames

    # Set up camera constraint
    cam = bpy.data.objects.get("Camera")
    if cam is None:
        cam_data = bpy.data.cameras.new("Camera")
        cam_data.type = "PERSP"
        cam_data.lens = 24
        cam = bpy.data.objects.new("Camera", cam_data)
        bpy.context.collection.objects.link(cam)
    
    bpy.context.scene.camera = cam

    # Follow path constraint
    follow = cam.constraints.new("FOLLOW_PATH")
    follow.target = path_obj
    follow.use_fixed_location = True
    follow.offset_factor = 0.0
    follow.forward_axis = "FORWARD_Y"
    follow.up_axis = "UP_Z"

    # Keyframe the offset
    bpy.context.scene.frame_start = 1
    bpy.context.scene.frame_end = total_frames
    bpy.context.scene.render.fps = fps

    follow.offset_factor = 0.0
    follow.keyframe_insert("offset_factor", frame=1)
    follow.offset_factor = 1.0
    follow.keyframe_insert("offset_factor", frame=total_frames)

    # Smooth interpolation
    if cam.animation_data and cam.animation_data.action:
        for fc in cam.animation_data.action.fcurves:
            for kp in fc.keyframe_points:
                kp.interpolation = "BEZIER"
                kp.easing = "EASE_IN_OUT"

    print(f"Created walkthrough: {total_length:.0f} ft path, "
          f"{total_seconds:.1f} sec, {total_frames} frames @ {fps} fps")
    return path_obj


if __name__ == "__main__":
    args = get_args()
    if not args:
        print("Usage: blender --python blender_helpers.py -- <command> [args]")
        print("Commands: setup-materials, render-views, walkthrough")
        sys.exit(1)

    command = args[0]

    if command == "setup-materials":
        setup_materials()
    elif command == "render-views":
        output_dir = args[1] if len(args) > 1 else "renders/latest"
        os.makedirs(output_dir, exist_ok=True)
        setup_lighting("daylight")
        for view in ["top", "iso", "front"]:
            setup_camera(view, (0, 0, 10), 60)
            import bpy
            bpy.context.scene.render.filepath = os.path.join(output_dir, f"{view}.png")
            bpy.ops.render.render(write_still=True)
            print(f"Rendered {view}")
    elif command == "walkthrough":
        if len(args) < 3:
            print("Usage: walkthrough <glb_path> <output_path> [fps]")
            sys.exit(1)
        fps = int(args[3]) if len(args) > 3 else 30
        # Default walkthrough for the exploded hex home
        waypoints = [
            (0, -80, 5.5),
            (0, -40, 3.0),
            (0, -10, -1.0),
            (0, 5, -2.0),
            (15, 10, -2.0),
            (-15, 10, -2.0),
            (0, 25, -2.0),
        ]
        create_walkthrough_path(waypoints, fps=fps)
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)
