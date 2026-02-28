"""
Production render script for the exploded hexagon home.

Produces high-quality Cycles renders with HDRI lighting, proper exposure,
and rich materials. Renders multiple camera angles into renders/latest/.

Usage:
  blender --background --python src/render_production.py -- out/massing_s23_d7.glb

Does NOT touch the user's live Blender session.
"""

import bpy
import math
import os
import sys
import json

# ---------------------------------------------------------------------------
# Parse args
# ---------------------------------------------------------------------------
argv = sys.argv
glb_path = None
if "--" in argv:
    custom_args = argv[argv.index("--") + 1:]
    if custom_args:
        glb_path = custom_args[0]

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
HDRI_DIR = os.path.join(PROJECT_DIR, "assets", "hdri")
RENDER_DIR = os.path.join(PROJECT_DIR, "renders", "latest")
os.makedirs(RENDER_DIR, exist_ok=True)

# Load config
config_path = os.path.join(SCRIPT_DIR, "config.json")
cfg = {}
if os.path.exists(config_path):
    with open(config_path) as f:
        cfg = json.load(f)

# ---------------------------------------------------------------------------
# Clean and import
# ---------------------------------------------------------------------------
for obj in list(bpy.data.objects):
    bpy.data.objects.remove(obj, do_unlink=True)

if glb_path and os.path.exists(glb_path):
    bpy.ops.import_scene.gltf(filepath=glb_path)
    print(f"Imported: {glb_path}")

# ---------------------------------------------------------------------------
# Unit system (model uses feet)
# ---------------------------------------------------------------------------
scene = bpy.context.scene
scene.unit_settings.system = 'METRIC'
scene.unit_settings.length_unit = 'METERS'
scene.unit_settings.scale_length = 1.0

# ---------------------------------------------------------------------------
# Render engine: Cycles for quality
# ---------------------------------------------------------------------------
scene.render.engine = 'CYCLES'
scene.cycles.samples = 256
scene.cycles.use_denoising = True
if hasattr(scene.cycles, 'denoiser'):
    scene.cycles.denoiser = 'OPENIMAGEDENOISE'

# Try GPU rendering
prefs = bpy.context.preferences.addons.get('cycles')
if prefs:
    cprefs = prefs.preferences
    # Try CUDA/OptiX first, fall back to CPU
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

scene.render.resolution_x = 2560
scene.render.resolution_y = 1440
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = 'PNG'
scene.render.image_settings.color_depth = '16'
scene.render.film_transparent = False

# ---------------------------------------------------------------------------
# Color management: THIS IS THE KEY FIX
# ---------------------------------------------------------------------------
scene.view_settings.view_transform = 'Filmic'
scene.view_settings.exposure = -1.0  # pull down hard to counter washout
if hasattr(scene.view_settings, 'look'):
    scene.view_settings.look = 'Medium High Contrast'
scene.view_settings.gamma = 1.0
scene.sequencer_colorspace_settings.name = 'sRGB'

print("Color management: Filmic, exposure=-1.0, Medium High Contrast")

# ---------------------------------------------------------------------------
# HDRI environment lighting (replaces flat background)
# ---------------------------------------------------------------------------
world = bpy.context.scene.world
if world is None:
    world = bpy.data.worlds.new("World")
    bpy.context.scene.world = world
world.use_nodes = True
nodes = world.node_tree.nodes
links = world.node_tree.links
nodes.clear()

# Try HDRI first, fall back to sky texture
hdri_path = os.path.join(HDRI_DIR, "spaichingen_hill_4k.hdr")
if not os.path.exists(hdri_path):
    hdri_path = os.path.join(HDRI_DIR, "meadow_2_4k.hdr")
if not os.path.exists(hdri_path):
    hdri_path = os.path.join(HDRI_DIR, "spruit_sunrise_1k.hdr")
if os.path.exists(hdri_path):
    env_tex = nodes.new('ShaderNodeTexEnvironment')
    env_tex.image = bpy.data.images.load(hdri_path)

    mapping = nodes.new('ShaderNodeMapping')
    mapping.inputs['Rotation'].default_value = (0, 0, math.radians(120))  # rotate for best angle

    tex_coord = nodes.new('ShaderNodeTexCoord')
    links.new(tex_coord.outputs['Generated'], mapping.inputs['Vector'])
    links.new(mapping.outputs['Vector'], env_tex.inputs['Vector'])

    bg = nodes.new('ShaderNodeBackground')
    bg.inputs['Strength'].default_value = 0.8  # moderate HDRI brightness
    links.new(env_tex.outputs['Color'], bg.inputs['Color'])

    output = nodes.new('ShaderNodeOutputWorld')
    links.new(bg.outputs['Background'], output.inputs['Surface'])
    print(f"HDRI loaded: {hdri_path}")
else:
    # Sky texture fallback
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
# Sun lamp (calibrated, NOT overwhelming)
# ---------------------------------------------------------------------------
# Remove any existing lights first
for obj in list(bpy.data.objects):
    if obj.type == 'LIGHT':
        bpy.data.objects.remove(obj, do_unlink=True)

# Solar position
lat = cfg.get("site_latitude", 35.5)
lon = cfg.get("site_longitude", -80.0)
sun_month = int(cfg.get("sun_month", 6))
sun_day = int(cfg.get("sun_day", 21))
sun_hour = float(cfg.get("sun_hour", 14.0))
north_offset = float(cfg.get("site_north_offset_deg", 0.0))

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

sun_data = bpy.data.lights.new(name="Sun", type='SUN')
sun_obj = bpy.data.objects.new("Sun", sun_data)
bpy.context.scene.collection.objects.link(sun_obj)
sun_obj.rotation_euler = (math.pi / 2 - alt, 0.0, -math.radians(az_d + north_offset))
# Key fix: MUCH lower sun energy with HDRI providing ambient
sun_obj.data.energy = 1.0
sun_obj.data.color = (1.0, 0.95, 0.88)  # warm daylight
sun_obj.data.angle = math.radians(0.545)
print(f"Sun: alt={alt_d:.1f} az={az_d:.1f} energy=1.0")

# Subtle cool fill from opposite side
fill_data = bpy.data.lights.new(name="FillLight", type='SUN')
fill_obj = bpy.data.objects.new("FillLight", fill_data)
bpy.context.scene.collection.objects.link(fill_obj)
fill_obj.rotation_euler = (math.radians(70), 0, math.radians(180))
fill_obj.data.energy = 0.15  # very subtle
fill_obj.data.color = (0.85, 0.9, 1.0)

# ---------------------------------------------------------------------------
# Material upgrades (same as startup but more aggressive for production)
# ---------------------------------------------------------------------------
def upgrade_material(mat, mat_type):
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
        noise = nodes.new('ShaderNodeTexNoise')
        noise.inputs['Scale'].default_value = 8.0
        noise.inputs['Detail'].default_value = 6.0
        noise.inputs['Roughness'].default_value = 0.6
        links.new(mapping.outputs['Vector'], noise.inputs['Vector'])
        ramp = nodes.new('ShaderNodeValToRGB')
        ramp.color_ramp.elements[0].color = (0.45, 0.43, 0.40, 1.0)
        ramp.color_ramp.elements[0].position = 0.35
        ramp.color_ramp.elements[1].color = (0.62, 0.60, 0.57, 1.0)
        ramp.color_ramp.elements[1].position = 0.65
        links.new(noise.outputs['Fac'], ramp.inputs['Fac'])
        links.new(ramp.outputs['Color'], bsdf.inputs['Base Color'])
        bsdf.inputs['Roughness'].default_value = 0.35
        bump = nodes.new('ShaderNodeBump')
        bump.inputs['Strength'].default_value = 0.08
        links.new(noise.outputs['Fac'], bump.inputs['Height'])
        links.new(bump.outputs['Normal'], bsdf.inputs['Normal'])

    elif mat_type == "marble":
        wave = nodes.new('ShaderNodeTexWave')
        wave.inputs['Scale'].default_value = 3.0
        wave.inputs['Distortion'].default_value = 8.0
        wave.inputs['Detail'].default_value = 4.0
        links.new(mapping.outputs['Vector'], wave.inputs['Vector'])
        mix = nodes.new('ShaderNodeMixRGB')
        mix.inputs['Fac'].default_value = 0.15
        mix.inputs['Color1'].default_value = (0.85, 0.82, 0.78, 1.0)
        mix.inputs['Color2'].default_value = (0.35, 0.33, 0.30, 1.0)
        links.new(wave.outputs['Fac'], mix.inputs['Fac'])
        links.new(mix.outputs['Color'], bsdf.inputs['Base Color'])
        bsdf.inputs['Roughness'].default_value = 0.08

    elif mat_type == "glass":
        bsdf.inputs['Base Color'].default_value = (0.7, 0.82, 0.88, 1.0)
        bsdf.inputs['Roughness'].default_value = 0.02
        bsdf.inputs['Transmission Weight'].default_value = 0.92
        bsdf.inputs['IOR'].default_value = 1.45
        bsdf.inputs['Alpha'].default_value = 0.3
        if hasattr(mat, 'surface_render_method'):
            mat.surface_render_method = 'DITHERED'

    elif mat_type == "ground":
        voronoi = nodes.new('ShaderNodeTexVoronoi')
        voronoi.inputs['Scale'].default_value = 15.0
        links.new(mapping.outputs['Vector'], voronoi.inputs['Vector'])
        noise = nodes.new('ShaderNodeTexNoise')
        noise.inputs['Scale'].default_value = 25.0
        noise.inputs['Detail'].default_value = 5.0
        links.new(mapping.outputs['Vector'], noise.inputs['Vector'])
        ramp = nodes.new('ShaderNodeValToRGB')
        ramp.color_ramp.elements[0].color = (0.08, 0.25, 0.05, 1.0)
        ramp.color_ramp.elements[0].position = 0.3
        ramp.color_ramp.elements[1].color = (0.18, 0.42, 0.12, 1.0)
        ramp.color_ramp.elements[1].position = 0.7
        links.new(noise.outputs['Fac'], ramp.inputs['Fac'])
        links.new(ramp.outputs['Color'], bsdf.inputs['Base Color'])
        bsdf.inputs['Roughness'].default_value = 0.85
        bump = nodes.new('ShaderNodeBump')
        bump.inputs['Strength'].default_value = 0.15
        links.new(voronoi.outputs['Distance'], bump.inputs['Height'])
        links.new(bump.outputs['Normal'], bsdf.inputs['Normal'])

    elif mat_type == "rug":
        # Rich warm tones, not white
        bsdf.inputs['Base Color'].default_value = (0.28, 0.20, 0.14, 1.0)
        bsdf.inputs['Roughness'].default_value = 0.9

    elif mat_type == "leather":
        bsdf.inputs['Base Color'].default_value = (0.12, 0.09, 0.07, 1.0)
        bsdf.inputs['Roughness'].default_value = 0.4

    elif mat_type == "fabric":
        bsdf.inputs['Base Color'].default_value = (0.82, 0.78, 0.72, 1.0)
        bsdf.inputs['Roughness'].default_value = 0.85

    elif mat_type == "walnut":
        bsdf.inputs['Base Color'].default_value = (0.18, 0.11, 0.06, 1.0)
        bsdf.inputs['Roughness'].default_value = 0.3

    elif mat_type == "brass":
        bsdf.inputs['Base Color'].default_value = (0.65, 0.50, 0.22, 1.0)
        bsdf.inputs['Roughness'].default_value = 0.25
        bsdf.inputs['Metallic'].default_value = 0.95


MATERIAL_UPGRADES = {
    "concrete": "concrete",
    "marble": "marble",
    "glass": "glass",
    "tableglass": "glass",
    "ground": "ground",
    "luxuryrug": "rug",
    "leather": "leather",
    "bedfabric": "fabric",
    "headboard": "leather",
    "darkwalnut": "walnut",
    "brass": "brass",
    "pillow": "fabric",
}

upgraded = 0
for mat in bpy.data.materials:
    mat_name = mat.name.lower().replace(" ", "")
    for key, mat_type in MATERIAL_UPGRADES.items():
        if key in mat_name:
            try:
                upgrade_material(mat, mat_type)
                upgraded += 1
            except Exception as e:
                print(f"  Material upgrade failed {mat.name}: {e}")
            break

print(f"Upgraded {upgraded} materials")

# ---------------------------------------------------------------------------
# Camera positions (converted from feet to meters)
# ---------------------------------------------------------------------------
FT = 0.3048
# Building center roughly at (0, 0). Hex radius ~7m, triangle extends ~16.5m.
CAMERAS = {
    "hero_3quarter": {
        "location": (65 * FT, -55 * FT, 35 * FT),
        "target": (0, 5 * FT, 10 * FT),
        "focal_length": 28,
        "description": "3/4 hero view showing atrium and front wings",
    },
    "atrium_interior": {
        "location": (0, 2 * FT, 4.5 * FT),
        "target": (0, 10 * FT, 15 * FT),
        "focal_length": 18,
        "description": "Standing inside atrium looking up at glass dome",
    },
    "approach": {
        "location": (40 * FT, -50 * FT, 12 * FT),
        "target": (0, 0, 10 * FT),
        "focal_length": 32,
        "description": "Approaching from driveway, seeing the building emerge",
    },
    "aerial": {
        "location": (0, 0, 120 * FT),
        "target": (0, 0, 0),
        "focal_length": 50,
        "description": "Aerial top-down showing full plan geometry",
    },
    "wingc_lookback": {
        "location": (-5 * FT, 18 * FT, 2 * FT),
        "target": (0, 0, 15 * FT),
        "focal_length": 20,
        "description": "From Wing C looking back through atrium garden",
    },
}

def render_view(name, cam_info):
    """Set up camera and render one view."""
    loc = cam_info["location"]
    target = cam_info["target"]
    fl = cam_info["focal_length"]

    cam_data = bpy.data.cameras.new(name=f"Camera_{name}")
    cam_data.lens = fl
    cam_data.clip_start = 0.1
    cam_data.clip_end = 200

    cam_obj = bpy.data.objects.new(f"Camera_{name}", cam_data)
    bpy.context.scene.collection.objects.link(cam_obj)
    cam_obj.location = loc

    # Point camera at target
    direction = (target[0] - loc[0], target[1] - loc[1], target[2] - loc[2])
    # Use track-to constraint for accurate aiming
    empty = bpy.data.objects.new(f"Target_{name}", None)
    empty.location = target
    bpy.context.scene.collection.objects.link(empty)

    track = cam_obj.constraints.new(type='TRACK_TO')
    track.target = empty
    track.track_axis = 'TRACK_NEGATIVE_Z'
    track.up_axis = 'UP_Y'

    # Set as active camera
    scene.camera = cam_obj

    # Force constraint evaluation
    bpy.context.view_layer.update()

    # Render
    out_path = os.path.join(RENDER_DIR, f"{name}.png")
    scene.render.filepath = out_path
    bpy.ops.render.render(write_still=True)
    print(f"Rendered: {out_path}")

    # Cleanup camera objects
    bpy.data.objects.remove(empty, do_unlink=True)
    bpy.data.objects.remove(cam_obj, do_unlink=True)
    bpy.data.cameras.remove(cam_data)

    return out_path


# ---------------------------------------------------------------------------
# Render all views
# ---------------------------------------------------------------------------
print("\n=== Starting production renders ===")
rendered = []
for name, info in CAMERAS.items():
    try:
        path = render_view(name, info)
        rendered.append(path)
    except Exception as e:
        print(f"Failed to render {name}: {e}")

print(f"\n=== Rendered {len(rendered)} views ===")
for p in rendered:
    print(f"  {p}")
