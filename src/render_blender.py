from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import textwrap
import time
from typing import List, Tuple


def _resolve_blender_executable(blender_executable: str | None) -> str | None:
    if blender_executable:
        cleaned = blender_executable.strip().strip('"').strip("'")
        explicit = Path(cleaned).expanduser()
        if explicit.exists():
            return str(explicit)
        resolved = shutil.which(cleaned)
        if resolved:
            return resolved

    env_blender = os.environ.get("BLENDER_PATH", "").strip()
    if env_blender:
        env_path = Path(env_blender).expanduser()
        if env_path.exists():
            return str(env_path)
        resolved_env = shutil.which(env_blender)
        if resolved_env:
            return resolved_env

    return shutil.which("blender")


def render_if_available(
    glb_path: Path,
    render_dir: Path,
    blender_executable: str | None = None,
) -> Tuple[bool, List[Path], str | None]:
    blender = _resolve_blender_executable(blender_executable)
    if blender is None:
        return False, [], "Blender executable not found."

    render_dir.mkdir(parents=True, exist_ok=True)
    start_ts = time.time()
    before_pngs = {p.resolve() for p in render_dir.glob("*.png")}
    script = textwrap.dedent(
        f"""
        import bpy
        import math
        import mathutils
        import os

        GLB_PATH = {str(glb_path)!r}
        OUT_DIR = {str(render_dir)!r}
        os.makedirs(OUT_DIR, exist_ok=True)

        bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.ops.import_scene.gltf(filepath=GLB_PATH)

        scene = bpy.context.scene
        scene.render.engine = "CYCLES"
        scene.cycles.samples = 32
        scene.cycles.use_denoising = True
        scene.render.use_file_extension = True
        scene.render.resolution_x = 1800
        scene.render.resolution_y = 1200
        scene.render.image_settings.file_format = "PNG"

        meshes = [obj for obj in scene.objects if obj.type == "MESH"]
        if not meshes:
            raise RuntimeError("No mesh objects were imported from GLB.")

        all_coords = []
        for obj in meshes:
            for vertex in obj.data.vertices:
                all_coords.append(obj.matrix_world @ vertex.co)

        min_co = mathutils.Vector((
            min(v.x for v in all_coords),
            min(v.y for v in all_coords),
            min(v.z for v in all_coords),
        ))
        max_co = mathutils.Vector((
            max(v.x for v in all_coords),
            max(v.y for v in all_coords),
            max(v.z for v in all_coords),
        ))
        center = (min_co + max_co) * 0.5
        size = max_co - min_co
        max_dim = max(size.x, size.y, size.z)
        dist = max_dim * 2.4
        ortho_scale = max(size.x, size.y, size.z) * 1.4

        bpy.ops.object.light_add(type="SUN", location=(center.x + dist, center.y - dist, center.z + dist))
        sun = bpy.context.active_object
        sun.data.energy = 3.0

        world = scene.world
        if world is None:
            world = bpy.data.worlds.new("World")
            scene.world = world
        world.use_nodes = True
        bg = world.node_tree.nodes.get("Background")
        if bg is None:
            bg = world.node_tree.nodes.new("ShaderNodeBackground")
        bg.inputs[0].default_value = (0.95, 0.95, 0.97, 1.0)
        bg.inputs[1].default_value = 1.0

        def render_view(name, location):
            camera_data = bpy.data.cameras.new("Cam_" + name)
            camera_data.type = "ORTHO"
            camera_data.ortho_scale = ortho_scale
            camera_data.clip_start = 0.1
            camera_data.clip_end = max_dim * 20
            camera = bpy.data.objects.new("Cam_" + name, camera_data)
            scene.collection.objects.link(camera)
            camera.location = location
            direction = center - camera.location
            camera.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
            scene.camera = camera
            scene.render.filepath = os.path.join(OUT_DIR, name + ".png")
            render_result = bpy.ops.render.render(write_still=True)
            if "FINISHED" not in render_result:
                raise RuntimeError(f"Render did not finish for {{name}}: {{render_result}}")
            print("RENDERED", name, scene.render.filepath)
            bpy.data.objects.remove(camera, do_unlink=True)

        render_view("top", mathutils.Vector((center.x, center.y, center.z + dist)))
        render_view("front", mathutils.Vector((center.x, center.y - dist, center.z + dist * 0.15)))
        render_view("iso", mathutils.Vector((center.x + dist * 0.8, center.y - dist * 0.8, center.z + dist * 0.55)))
        """
    ).strip()

    with tempfile.TemporaryDirectory() as tmp_dir:
        script_path = Path(tmp_dir) / "render_tmp.py"
        script_path.write_text(script, encoding="utf-8")
        result = subprocess.run(
            [blender, "--background", "--python-exit-code", "1", "--python", str(script_path)],
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            stderr_tail = (result.stderr or result.stdout or "").strip()
            if len(stderr_tail) > 500:
                stderr_tail = stderr_tail[-500:]
            return True, [], (stderr_tail or "Blender render failed.")

    outputs = [render_dir / "top.png", render_dir / "iso.png", render_dir / "front.png"]
    existing = [path for path in outputs if path.exists()]
    if not existing:
        current_pngs = list(render_dir.glob("*.png"))
        new_pngs = [p for p in current_pngs if p.resolve() not in before_pngs and p.stat().st_mtime >= start_ts - 1]
        if new_pngs:
            existing = sorted(new_pngs, key=lambda p: p.stat().st_mtime, reverse=True)[:3]
    if not existing:
        out_tail = (result.stdout or "").strip()
        if len(out_tail) > 350:
            out_tail = out_tail[-350:]
        message = "Blender completed, but no render images were produced."
        if out_tail:
            message = f"{message} Output tail: {out_tail}"
        return True, [], message
    return True, existing, None

