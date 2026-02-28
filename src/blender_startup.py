"""
Blender startup script for the exploded hexagon home project.

Sets up what GLB cannot store: lights, render settings, color management,
and upgrades flat GLB materials to rich procedural Blender materials.

Usage:
  blender --python src/blender_startup.py -- out/massing_s23_d7.glb
  (also works for detached launch from the CLI)
"""

import bpy
import math
import sys
import os
import json

# When exec()'d from Blender's Python console, __file__ is not defined.
# Provide a fallback so config/HDRI paths resolve correctly.
if '__file__' not in dir():
    __file__ = r"F:\home\exploded-hexagon-home\src\blender_startup.py"

# ---------------------------------------------------------------------------
# Parse args
# ---------------------------------------------------------------------------
argv = sys.argv
glb_path = None
if "--" in argv:
    custom_args = argv[argv.index("--") + 1:]
    if custom_args:
        glb_path = custom_args[0]

# ---------------------------------------------------------------------------
# Clean default scene (only when launched as startup script, not exec'd in console)
# ---------------------------------------------------------------------------
if glb_path:
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)

# ---------------------------------------------------------------------------
# Import GLB
# ---------------------------------------------------------------------------
if glb_path and os.path.exists(glb_path):
    bpy.ops.import_scene.gltf(filepath=glb_path)
    print(f"Imported: {glb_path}")
elif glb_path:
    print(f"Warning: GLB not found: {glb_path}")
else:
    print("Console mode: skipping import, applying settings to existing scene")

# ---------------------------------------------------------------------------
# Organize objects into labeled collections
# ---------------------------------------------------------------------------
def get_or_create_collection(name, parent=None):
    if name in bpy.data.collections:
        return bpy.data.collections[name]
    col = bpy.data.collections.new(name)
    if parent:
        parent.children.link(col)
    else:
        bpy.context.scene.collection.children.link(col)
    return col

# Create hierarchy
col_building = get_or_create_collection("Building")
col_atrium = get_or_create_collection("Atrium", col_building)
col_wing_a = get_or_create_collection("Wing A (front-right)", col_building)
col_wing_b = get_or_create_collection("Wing B (front-left)", col_building)
col_wing_c = get_or_create_collection("Wing C (back)", col_building)
col_triangle = get_or_create_collection("Master Triangle (upper)", col_building)
col_terrain = get_or_create_collection("Terrain & Ground", col_building)
col_garden = get_or_create_collection("Atrium Garden")
col_bedroom = get_or_create_collection("Wing B Bedroom")
col_lighting = get_or_create_collection("Lighting")

# Sort ALL objects into collections by name.
# GLB import puts everything in a default "Collection"; we need to iterate
# bpy.data.objects (the master list), not scene.collection.objects (often empty).
COLLECTION_MAP = {
    # Structural (from model.py component names)
    "atrium_f": col_atrium,     # atrium_floor, atrium_facade
    "atrium_r": col_atrium,     # atrium_roof
    "wing_a": col_wing_a,
    "wing_b": col_wing_b,
    "wing_c": col_wing_c,
    "master_triangle": col_triangle,
    "triangle": col_triangle,
    "terrain": col_terrain,
    "ground": col_terrain,
    "driveway": col_terrain,
    "courtyard": col_terrain,
    "motorcourt": col_terrain,
    "ClearingFloor": col_garden,
    "Path_": col_garden,
    # Garden elements
    "RealisticPlant": col_garden,
    "Fountain": col_garden,
    "Palm": col_garden,
    "Bush": col_garden,
    "Fern": col_garden,
    "Soil": col_garden,
    "PathStone": col_garden,
    # Bedroom furniture
    "Bed_": col_bedroom,
    "Nightstand": col_bedroom,
    "Chair_": col_bedroom,
    "ChairLeg": col_bedroom,
    "CoffeeTable": col_bedroom,
    "TableLeg": col_bedroom,
    "Lamp_": col_bedroom,
    "AreaRug": col_bedroom,
    "Pillow": col_bedroom,
    "Headboard": col_bedroom,
    "WingB_": col_bedroom,
}

moved = 0
for obj in list(bpy.data.objects):
    target = None
    obj_name = obj.name
    for key, col in COLLECTION_MAP.items():
        if key.lower() in obj_name.lower():
            target = col
            break
    if target is None:
        continue
    # Unlink from ALL current collections
    for old_col in list(obj.users_collection):
        try:
            old_col.objects.unlink(obj)
        except RuntimeError:
            pass
    # Also unlink from root scene collection
    try:
        bpy.context.scene.collection.objects.unlink(obj)
    except RuntimeError:
        pass
    # Link to target
    if obj.name not in target.objects:
        target.objects.link(obj)
    moved += 1

# Remove the now-empty default "Collection" from GLB import
for col in list(bpy.data.collections):
    if col.name.startswith("Collection") and len(col.objects) == 0 and len(col.children) == 0:
        bpy.data.collections.remove(col)

print(f"Organized {moved} objects into labeled collections")

# ---------------------------------------------------------------------------
# Load config for sun position
# ---------------------------------------------------------------------------
config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
cfg = {}
if os.path.exists(config_path):
    with open(config_path) as f:
        cfg = json.load(f)

# ---------------------------------------------------------------------------
# Sun Lamp (realistic solar position)
# ---------------------------------------------------------------------------
lat = cfg.get("site_latitude", 35.5)
lon = cfg.get("site_longitude", -80.0)
sun_month = int(cfg.get("sun_month", 6))
sun_day = int(cfg.get("sun_day", 21))
sun_hour = float(cfg.get("sun_hour", 14.0))
north_offset = float(cfg.get("site_north_offset_deg", 0.0))

# Solar position calculation
doy = sum([0, 31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][:sun_month]) + sun_day
B = math.radians((360 / 365) * (doy - 81))
dec = math.radians(23.45) * math.sin(B)
B2 = math.radians((360 / 365) * (doy - 1))
eot = 229.18 * (0.000075 + 0.001868 * math.cos(B2) - 0.032077 * math.sin(B2)
                - 0.014615 * math.cos(2 * B2) - 0.04089 * math.sin(2 * B2))
utc_off = -4.0 if 3 <= sun_month <= 10 else -5.0
st = (sun_hour - utc_off) + (lon / 15.0) + (eot / 60.0)
ha = math.radians((st - 12.0) * 15.0)
lat_r = math.radians(lat)
sin_alt = math.sin(lat_r) * math.sin(dec) + math.cos(lat_r) * math.cos(dec) * math.cos(ha)
alt = math.asin(max(-1, min(1, sin_alt)))
cos_az = (math.sin(dec) - math.sin(lat_r) * math.sin(alt)) / (math.cos(lat_r) * math.cos(alt) + 1e-10)
az = math.acos(max(-1, min(1, cos_az)))
if ha > 0:
    az = 2 * math.pi - az
az = (az + math.pi) % (2 * math.pi)
alt_d = math.degrees(alt)
az_d = math.degrees(az)

# Create Sun lamp
sun_data = bpy.data.lights.new(name="Sun", type='SUN')
sun_obj = bpy.data.objects.new("Sun", sun_data)
col_lighting.objects.link(sun_obj)
sun_obj.rotation_euler = (math.pi / 2 - alt, 0.0, -math.radians(az_d + north_offset))
sun_obj.data.energy = 1.0  # moderate with HDRI providing ambient
sun_obj.data.color = (1.0, 0.95, 0.88)  # warm daylight
sun_obj.data.angle = math.radians(0.545)
print(f"Sun: alt={alt_d:.1f}° az={az_d:.1f}° ({sun_month}/{sun_day} {sun_hour:.0f}h, {lat}°N)")

# Subtle fill light from opposite side
fill_data = bpy.data.lights.new(name="FillLight", type='SUN')
fill_obj = bpy.data.objects.new("FillLight", fill_data)
col_lighting.objects.link(fill_obj)
fill_obj.rotation_euler = (math.radians(70), 0, math.radians(180))
fill_obj.data.energy = 0.15  # very subtle
fill_obj.data.color = (0.85, 0.9, 1.0)  # cool fill

# ---------------------------------------------------------------------------
# World / Sky: HDRI for realistic lighting, with sky texture fallback
# ---------------------------------------------------------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
HDRI_DIR = os.path.join(os.path.dirname(SCRIPT_DIR), "assets", "hdri")

world = bpy.context.scene.world
if world is None:
    world = bpy.data.worlds.new("World")
    bpy.context.scene.world = world
world.use_nodes = True
nodes = world.node_tree.nodes
links = world.node_tree.links
nodes.clear()

hdri_path = os.path.join(HDRI_DIR, "spaichingen_hill_4k.hdr")
if not os.path.exists(hdri_path):
    hdri_path = os.path.join(HDRI_DIR, "meadow_2_4k.hdr")
if not os.path.exists(hdri_path):
    hdri_path = os.path.join(HDRI_DIR, "spruit_sunrise_1k.hdr")
if os.path.exists(hdri_path):
    env_tex = nodes.new('ShaderNodeTexEnvironment')
    env_tex.image = bpy.data.images.load(hdri_path)

    mapping = nodes.new('ShaderNodeMapping')
    mapping.inputs['Rotation'].default_value = (0, 0, math.radians(120))

    tex_coord = nodes.new('ShaderNodeTexCoord')
    links.new(tex_coord.outputs['Generated'], mapping.inputs['Vector'])
    links.new(mapping.outputs['Vector'], env_tex.inputs['Vector'])

    bg = nodes.new('ShaderNodeBackground')
    bg.inputs['Strength'].default_value = 0.8
    links.new(env_tex.outputs['Color'], bg.inputs['Color'])

    output = nodes.new('ShaderNodeOutputWorld')
    links.new(bg.outputs['Background'], output.inputs['Surface'])
    print(f"HDRI loaded: {hdri_path}")
else:
    # Nishita sky texture fallback (photorealistic procedural sky)
    sky = nodes.new('ShaderNodeTexSky')
    sky.sky_type = 'NISHITA'
    sky.sun_elevation = math.radians(45)
    sky.sun_rotation = math.radians(180)

    bg = nodes.new('ShaderNodeBackground')
    bg.inputs['Strength'].default_value = 0.5
    links.new(sky.outputs['Color'], bg.inputs['Color'])

    output = nodes.new('ShaderNodeOutputWorld')
    links.new(bg.outputs['Background'], output.inputs['Surface'])
    print("Using Nishita sky texture (no HDRI found)")

# ---------------------------------------------------------------------------
# Color Management / Render Settings
# ---------------------------------------------------------------------------
scene = bpy.context.scene

# Unit system: GLB geometry is now in meters (converted during export).
# With system=METRIC and scale_length=1.0, Blender's native 1:1 mapping works
# correctly: walk height 1.7m = eye level, dimensions display in meters.
scene.unit_settings.system = 'METRIC'
scene.unit_settings.length_unit = 'METERS'
scene.unit_settings.scale_length = 1.0

# Color management (matched to production render settings)
scene.view_settings.view_transform = 'Filmic'
scene.view_settings.exposure = -1.0  # pull down to counter washout
if hasattr(scene.view_settings, 'look'):
    scene.view_settings.look = 'Medium High Contrast'
scene.view_settings.gamma = 1.0

# Cycles for quality renders (user can switch to EEVEE for fast viewport)
scene.render.engine = 'CYCLES'
scene.cycles.samples = 128  # good balance of speed/quality for viewport renders
scene.cycles.use_denoising = True
if hasattr(scene.cycles, 'denoiser'):
    scene.cycles.denoiser = 'OPENIMAGEDENOISE'

# Try GPU rendering
prefs = bpy.context.preferences.addons.get('cycles')
if prefs:
    cprefs = prefs.preferences
    for device_type in ['OPTIX', 'CUDA', 'HIP', 'NONE']:
        try:
            cprefs.compute_device_type = device_type
            cprefs.get_devices()
            if device_type != 'NONE':
                scene.cycles.device = 'GPU'
                for d in cprefs.devices:
                    d.use = True
                print(f"GPU rendering: {device_type}")
            break
        except Exception:
            continue

scene.render.resolution_x = 1920
scene.render.resolution_y = 1080

print(f"Render: Cycles, Filmic, exposure=-1.0, Medium High Contrast, HDRI, units=METRIC")

# ---------------------------------------------------------------------------
# Upgrade GLB Materials to Procedural PBR
# ---------------------------------------------------------------------------
def upgrade_material(mat, mat_type):
    """Replace flat GLB material colors with rich procedural Blender materials."""
    if not mat or not mat.use_nodes:
        return

    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    bsdf = nodes.get("Principled BSDF")
    if not bsdf:
        return

    tex_coord = nodes.new('ShaderNodeTexCoord')
    mapping = nodes.new('ShaderNodeMapping')
    links.new(tex_coord.outputs['Generated'], mapping.inputs['Vector'])

    if mat_type == "concrete":
        # Polished concrete with subtle aggregate variation
        noise = nodes.new('ShaderNodeTexNoise')
        noise.inputs['Scale'].default_value = 8.0
        noise.inputs['Detail'].default_value = 6.0
        noise.inputs['Roughness'].default_value = 0.6
        links.new(mapping.outputs['Vector'], noise.inputs['Vector'])

        ramp = nodes.new('ShaderNodeValToRGB')
        ramp.color_ramp.elements[0].color = (0.55, 0.53, 0.50, 1.0)
        ramp.color_ramp.elements[0].position = 0.35
        ramp.color_ramp.elements[1].color = (0.72, 0.70, 0.67, 1.0)
        ramp.color_ramp.elements[1].position = 0.65
        links.new(noise.outputs['Fac'], ramp.inputs['Fac'])
        links.new(ramp.outputs['Color'], bsdf.inputs['Base Color'])

        bsdf.inputs['Roughness'].default_value = 0.25
        bsdf.inputs['Specular IOR Level'].default_value = 0.5

        # Subtle bump
        bump = nodes.new('ShaderNodeBump')
        bump.inputs['Strength'].default_value = 0.05
        links.new(noise.outputs['Fac'], bump.inputs['Height'])
        links.new(bump.outputs['Normal'], bsdf.inputs['Normal'])

    elif mat_type == "marble":
        # Marble with veining
        wave = nodes.new('ShaderNodeTexWave')
        wave.inputs['Scale'].default_value = 3.0
        wave.inputs['Distortion'].default_value = 8.0
        wave.inputs['Detail'].default_value = 4.0
        wave.inputs['Detail Scale'].default_value = 2.0
        links.new(mapping.outputs['Vector'], wave.inputs['Vector'])

        noise = nodes.new('ShaderNodeTexNoise')
        noise.inputs['Scale'].default_value = 12.0
        noise.inputs['Detail'].default_value = 8.0
        links.new(mapping.outputs['Vector'], noise.inputs['Vector'])

        mix = nodes.new('ShaderNodeMixRGB')
        mix.inputs['Fac'].default_value = 0.15
        mix.inputs['Color1'].default_value = (0.93, 0.91, 0.88, 1.0)  # warm white base
        mix.inputs['Color2'].default_value = (0.45, 0.43, 0.40, 1.0)  # dark veins
        links.new(wave.outputs['Fac'], mix.inputs['Fac'])
        links.new(mix.outputs['Color'], bsdf.inputs['Base Color'])

        bsdf.inputs['Roughness'].default_value = 0.08
        bsdf.inputs['Specular IOR Level'].default_value = 0.8

    elif mat_type == "glass":
        bsdf.inputs['Base Color'].default_value = (0.85, 0.92, 0.96, 1.0)
        bsdf.inputs['Roughness'].default_value = 0.02
        bsdf.inputs['Transmission Weight'].default_value = 0.92
        bsdf.inputs['IOR'].default_value = 1.45
        bsdf.inputs['Alpha'].default_value = 0.25
        if hasattr(mat, 'surface_render_method'):
            mat.surface_render_method = 'DITHERED'

    elif mat_type == "ground":
        # Grass with cellular variation
        voronoi = nodes.new('ShaderNodeTexVoronoi')
        voronoi.inputs['Scale'].default_value = 15.0
        links.new(mapping.outputs['Vector'], voronoi.inputs['Vector'])

        noise = nodes.new('ShaderNodeTexNoise')
        noise.inputs['Scale'].default_value = 25.0
        noise.inputs['Detail'].default_value = 5.0
        links.new(mapping.outputs['Vector'], noise.inputs['Vector'])

        ramp = nodes.new('ShaderNodeValToRGB')
        ramp.color_ramp.elements[0].color = (0.12, 0.35, 0.08, 1.0)  # dark grass
        ramp.color_ramp.elements[0].position = 0.3
        ramp.color_ramp.elements[1].color = (0.28, 0.55, 0.18, 1.0)  # light grass
        ramp.color_ramp.elements[1].position = 0.7
        links.new(noise.outputs['Fac'], ramp.inputs['Fac'])
        links.new(ramp.outputs['Color'], bsdf.inputs['Base Color'])

        bsdf.inputs['Roughness'].default_value = 0.85

        # Grass displacement
        bump = nodes.new('ShaderNodeBump')
        bump.inputs['Strength'].default_value = 0.15
        links.new(voronoi.outputs['Distance'], bump.inputs['Height'])
        links.new(bump.outputs['Normal'], bsdf.inputs['Normal'])


# Map GLB material names to upgrade types
MATERIAL_UPGRADES = {
    "concrete": "concrete",
    "marble": "marble",
    "glass": "glass",
    "ground": "ground",
}

upgraded = 0
for mat in bpy.data.materials:
    mat_name = mat.name.lower()
    for key, mat_type in MATERIAL_UPGRADES.items():
        if key in mat_name:
            try:
                upgrade_material(mat, mat_type)
                upgraded += 1
                print(f"  Upgraded material: {mat.name} → {mat_type}")
            except Exception as e:
                print(f"  Skipped {mat.name}: {e}")
            break

print(f"Upgraded {upgraded} materials to procedural PBR")

# ---------------------------------------------------------------------------
# GLB file-watch for live reload (poll every 2 seconds)
# ---------------------------------------------------------------------------
if glb_path and not ("--background" in sys.argv or "-b" in sys.argv):
    _glb_abs = os.path.abspath(glb_path)
    _last_mtime = os.path.getmtime(_glb_abs) if os.path.exists(_glb_abs) else 0

    def _check_glb_update():
        global _last_mtime
        try:
            mt = os.path.getmtime(_glb_abs)
            if mt > _last_mtime:
                _last_mtime = mt
                # Remove old mesh objects (keep lights, cameras, garden)
                for obj in list(bpy.data.objects):
                    if obj.type == 'MESH' and "Garden" not in obj.name:
                        bpy.data.objects.remove(obj, do_unlink=True)
                bpy.ops.import_scene.gltf(filepath=_glb_abs)
                print(f"[reload] {_glb_abs}")
        except Exception:
            pass
        return 2.0  # check every 2 seconds

    bpy.app.timers.register(_check_glb_update)
    print("File-watch enabled: will auto-reload GLB on changes")

print("\n=== Scene ready ===")
print("Tip: Shift+` for walk mode, Numpad 5 for perspective toggle")

# ---------------------------------------------------------------------------
# Start remote console server (allows Copilot CLI to send commands directly)
# ---------------------------------------------------------------------------
_remote_script = os.path.join(SCRIPT_DIR, "blender_remote.py")
if os.path.exists(_remote_script):
    try:
        exec(open(_remote_script).read())
    except Exception as e:
        print(f"[Remote] Could not start: {e}")
