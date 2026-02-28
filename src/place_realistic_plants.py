"""
Replace procedural plant primitives in the atrium garden with realistic
Poly Haven GLTF models downloaded by download_assets.py.

Usage:
  blender --background --python src/place_realistic_plants.py -- in.glb out.glb
  blender --python src/place_realistic_plants.py -- model.glb  (interactive)

Expects assets in assets/models/plants/{slug}/{slug}_1k.gltf
"""

import bpy
import math
import os
import sys
import random
from pathlib import Path

# Parse args: input GLB, output GLB
argv = sys.argv
custom_args = argv[argv.index("--") + 1:] if "--" in argv else []
in_glb = custom_args[0] if len(custom_args) >= 1 else None
out_glb = custom_args[1] if len(custom_args) >= 2 else in_glb

SCRIPT_DIR = Path(__file__).parent
ASSETS_DIR = SCRIPT_DIR.parent / "assets" / "models" / "plants"

# Feet to meters conversion
FT = 0.3048

# Atrium garden layout parameters (in meters)
ATRIUM_CENTER = (0.0, 0.0)
FLOOR_Z = -1.0 * FT  # atrium slab top
GARDEN_RADIUS = 17.0 * FT
CLEAR_CENTER_RADIUS = 5.0 * FT
PATH_WIDTH = 2.5 * FT

# Plant placement slots: (x, y, scale_range, preferred_types)
# Arranged in concentric rings around the fountain
PLANT_SLOTS = []

# Ring 1: close to fountain (r ~6-8 ft), small plants
for i in range(8):
    angle = i * (2 * math.pi / 8) + math.radians(22.5)
    r = 6.5 * FT
    x = r * math.cos(angle)
    y = r * math.sin(angle)
    PLANT_SLOTS.append((x, y, (0.8, 1.2), ["potted_plant_01", "potted_plant_02", "calathea_orbifolia_01", "potted_plant_04"]))

# Ring 2: medium distance (r ~10-12 ft), medium plants and ferns
for i in range(10):
    angle = i * (2 * math.pi / 10) + math.radians(10)
    r = 11.0 * FT
    x = r * math.cos(angle)
    y = r * math.sin(angle)
    PLANT_SLOTS.append((x, y, (1.0, 1.8), ["pachira_aquatica_01", "fern_02", "shrub_01", "shrub_04"]))

# Ring 3: outer edge (r ~14-16 ft), tall trees and large shrubs
for i in range(6):
    angle = i * (2 * math.pi / 6) + math.radians(30)
    r = 15.0 * FT
    x = r * math.cos(angle)
    y = r * math.sin(angle)
    PLANT_SLOTS.append((x, y, (1.5, 2.5), ["island_tree_01", "island_tree_02", "pachira_aquatica_01"]))

# Ground cover patches
for i in range(12):
    angle = i * (2 * math.pi / 12) + math.radians(15)
    r = random.uniform(7 * FT, 14 * FT)
    x = r * math.cos(angle)
    y = r * math.sin(angle)
    PLANT_SLOTS.append((x, y, (2.0, 4.0), ["moss_01"]))


def find_asset_gltf(slug: str) -> str | None:
    """Find the GLTF file for a given asset slug."""
    plant_dir = ASSETS_DIR / slug
    if not plant_dir.exists():
        return None
    for f in plant_dir.iterdir():
        if f.suffix == ".gltf":
            return str(f)
    return None


def import_plant(filepath: str, location: tuple, scale: float, name: str) -> list:
    """Import a GLTF plant and position it."""
    before = set(bpy.data.objects.keys())
    bpy.ops.import_scene.gltf(filepath=filepath)
    after = set(bpy.data.objects.keys())
    new_names = after - before

    imported = [bpy.data.objects[n] for n in new_names if n in bpy.data.objects]

    # Find the root objects (no parent among imported)
    roots = [o for o in imported if o.parent is None or o.parent.name not in new_names]

    for obj in roots:
        # Position at slot location, on atrium floor
        obj.location = (location[0], location[1], FLOOR_Z)
        obj.scale = (scale, scale, scale)
        # Random rotation for variety
        obj.rotation_euler = (0, 0, random.uniform(0, 2 * math.pi))

    # Rename root for scene organization
    for i, obj in enumerate(roots):
        suffix = f".{i}" if i > 0 else ""
        obj.name = f"RealisticPlant_{name}{suffix}"

    return imported


def remove_procedural_plants():
    """Remove the old procedural plant primitives."""
    removed = 0
    patterns = ["Palm_", "Bush_", "Fern_", "SoilBed", "PathStone_"]
    for obj in list(bpy.data.objects):
        for pat in patterns:
            if obj.name.startswith(pat) or pat in obj.name:
                bpy.data.objects.remove(obj, do_unlink=True)
                removed += 1
                break
    print(f"Removed {removed} procedural plant objects")


def main():
    # Import base GLB
    if in_glb and os.path.exists(in_glb):
        # Clear scene
        for obj in list(bpy.data.objects):
            bpy.data.objects.remove(obj, do_unlink=True)
        bpy.ops.import_scene.gltf(filepath=in_glb)
        print(f"Imported base: {in_glb}")

    # Remove old procedural plants
    remove_procedural_plants()

    # Check available assets
    available = {}
    if ASSETS_DIR.exists():
        for d in ASSETS_DIR.iterdir():
            if d.is_dir():
                gltf = find_asset_gltf(d.name)
                if gltf:
                    available[d.name] = gltf
    print(f"Available realistic plants: {list(available.keys())}")

    if not available:
        print("No plant assets found. Run: python src/download_assets.py")
        return

    # Place plants at each slot
    placed = 0
    random.seed(42)  # reproducible layout

    for i, (x, y, scale_range, preferred) in enumerate(PLANT_SLOTS):
        # Pick from preferred types that are available
        choices = [s for s in preferred if s in available]
        if not choices:
            choices = list(available.keys())

        slug = random.choice(choices)
        scale = random.uniform(*scale_range)
        gltf_path = available[slug]

        try:
            objs = import_plant(gltf_path, (x, y), scale, f"{slug}_{i}")
            placed += 1
        except Exception as e:
            print(f"  Failed to place {slug} at ({x:.1f}, {y:.1f}): {e}")

    print(f"Placed {placed} realistic plants in atrium garden")

    # Export
    if out_glb:
        bpy.ops.export_scene.gltf(
            filepath=out_glb,
            export_format='GLB',
            use_selection=False,
        )
        print(f"Saved: {out_glb}")


main()
