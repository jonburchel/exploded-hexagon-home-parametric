"""Apply generated texture images to materials in the Blender scene.

Run inside Blender via:
    .\Send-Blender.ps1 -File "src\apply_textures.py"

Loads textures from assets/textures/ and connects them to the appropriate
Principled BSDF materials.  Idempotent: safe to run multiple times.
"""

import bpy
import os
import math

PROJECT_ROOT = r"F:\home\exploded-hexagon-home"
TEXTURE_DIR = os.path.join(PROJECT_ROOT, "assets", "textures")

# ---------------------------------------------------------------------------
# Texture mapping: (material name substring, texture file, projection, scale)
# Order matters: more specific patterns must come before generic ones.
# ---------------------------------------------------------------------------
TEXTURE_MAP = [
    # Marble floors (atrium + Wing C)
    ("marble",   "atrium_marble_star_basecolor.png", "FLAT", (0.05, 0.05, 0.05)),
    # Driveway
    ("driveway", "driveway_basecolor.png",           "FLAT", (0.1, 0.1, 0.1)),
    # Side courtyards use lawn texture
    ("side_court", "lawn_basecolor.png",             "FLAT", (0.2, 0.2, 0.2)),
    # Concrete (walls, slabs, retaining walls)
    ("concrete", "smooth_concrete_basecolor.png",    "BOX",  (0.1, 0.1, 0.1)),
    # Ground / terrain / lawn
    ("ground",   "lawn_basecolor.png",               "FLAT", (0.2, 0.2, 0.2)),
]

# Special wall textures keyed by material or object name substring
WALL_TEXTURES = {
    "plant_wall":    "plant_wall_basecolor.png",
    "accent_wall":   "accent_wall_bedroom_basecolor.png",
    "bedroom_accent": "accent_wall_bedroom_basecolor.png",
}


# ---------------------------------------------------------------------------
# Core helper
# ---------------------------------------------------------------------------
def apply_texture_to_material(mat, tex_path, projection="FLAT", scale=(1, 1, 1)):
    """Wire an image texture into *mat*'s Principled BSDF Base Color input."""
    if not os.path.exists(tex_path):
        print(f"  Warning: texture not found: {tex_path}")
        return False

    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links

    bsdf = nodes.get("Principled BSDF")
    if not bsdf:
        print(f"  Warning: no Principled BSDF in {mat.name}, skipping")
        return False

    # Remove existing texture pipeline nodes (idempotent cleanup)
    for node in list(nodes):
        if node.type in ("TEX_IMAGE", "TEX_COORD", "MAPPING"):
            nodes.remove(node)

    # Build new texture pipeline
    tex_coord = nodes.new("ShaderNodeTexCoord")
    tex_coord.location = (-800, 300)

    mapping = nodes.new("ShaderNodeMapping")
    mapping.location = (-600, 300)
    mapping.inputs["Scale"].default_value = scale

    tex_image = nodes.new("ShaderNodeTexImage")
    tex_image.location = (-300, 300)

    # Reuse already-loaded image data if available
    img_name = os.path.basename(tex_path)
    existing = bpy.data.images.get(img_name)
    if existing and existing.filepath == tex_path:
        tex_image.image = existing
    else:
        tex_image.image = bpy.data.images.load(tex_path)

    tex_image.projection = projection

    links.new(tex_coord.outputs["Generated"], mapping.inputs["Vector"])
    links.new(mapping.outputs["Vector"], tex_image.inputs["Vector"])
    links.new(tex_image.outputs["Color"], bsdf.inputs["Base Color"])

    print(f"  Applied {img_name} to {mat.name} (proj={projection})")
    return True


# ---------------------------------------------------------------------------
# Sky sphere / world background
# ---------------------------------------------------------------------------
def setup_sky(tex_path):
    """Set the sky texture as world background or on a sky sphere."""
    if not os.path.exists(tex_path):
        print(f"  Warning: sky texture not found: {tex_path}")
        return

    # Prefer setting as world environment texture
    world = bpy.context.scene.world
    if world is None:
        world = bpy.data.worlds.new("World")
        bpy.context.scene.world = world

    world.use_nodes = True
    nodes = world.node_tree.nodes
    links = world.node_tree.links

    # Remove old environment texture nodes
    for node in list(nodes):
        if node.type in ("TEX_ENVIRONMENT", "TEX_IMAGE", "TEX_COORD", "MAPPING"):
            nodes.remove(node)

    bg = nodes.get("Background")
    if not bg:
        bg = nodes.new("ShaderNodeBackground")

    env_tex = nodes.new("ShaderNodeTexEnvironment")
    env_tex.location = (-300, 300)

    img_name = os.path.basename(tex_path)
    existing = bpy.data.images.get(img_name)
    if existing and existing.filepath == tex_path:
        env_tex.image = existing
    else:
        env_tex.image = bpy.data.images.load(tex_path)

    tex_coord = nodes.new("ShaderNodeTexCoord")
    tex_coord.location = (-700, 300)
    mapping = nodes.new("ShaderNodeMapping")
    mapping.location = (-500, 300)

    links.new(tex_coord.outputs["Generated"], mapping.inputs["Vector"])
    links.new(mapping.outputs["Vector"], env_tex.inputs["Vector"])
    links.new(env_tex.outputs["Color"], bg.inputs["Color"])
    print(f"  Applied {img_name} as world environment texture")

    # Also create sky sphere if one doesn't exist
    sky_obj = bpy.data.objects.get("SkySphere")
    if sky_obj is None:
        bpy.ops.mesh.primitive_uv_sphere_add(
            radius=500, segments=64, ring_count=32, location=(0, 0, 0)
        )
        sky_obj = bpy.context.active_object
        sky_obj.name = "SkySphere"
        # Flip normals inward
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.mesh.flip_normals()
        bpy.ops.object.mode_set(mode="OBJECT")
        print("  Created SkySphere (r=500)")

    # Apply sky texture as material on the sphere
    mat_name = "SkySphereMat"
    mat = bpy.data.materials.get(mat_name)
    if mat is None:
        mat = bpy.data.materials.new(mat_name)
    mat.use_nodes = True
    mat_nodes = mat.node_tree.nodes
    mat_links = mat.node_tree.links

    bsdf = mat_nodes.get("Principled BSDF")
    if bsdf:
        # Remove old tex nodes
        for node in list(mat_nodes):
            if node.type in ("TEX_IMAGE", "TEX_COORD", "MAPPING"):
                mat_nodes.remove(node)

        tc = mat_nodes.new("ShaderNodeTexCoord")
        tc.location = (-800, 300)
        mp = mat_nodes.new("ShaderNodeMapping")
        mp.location = (-600, 300)
        ti = mat_nodes.new("ShaderNodeTexImage")
        ti.location = (-300, 300)

        sky_img_name = os.path.basename(tex_path)
        existing_sky = bpy.data.images.get(sky_img_name)
        ti.image = existing_sky if existing_sky else bpy.data.images.load(tex_path)

        mat_links.new(tc.outputs["Generated"], mp.inputs["Vector"])
        mat_links.new(mp.outputs["Vector"], ti.inputs["Vector"])
        mat_links.new(ti.outputs["Color"], bsdf.inputs["Base Color"])
        bsdf.inputs["Roughness"].default_value = 1.0
        # Make it emissive so it looks like sky, not a dark sphere
        if "Emission Color" in bsdf.inputs:
            mat_links.new(ti.outputs["Color"], bsdf.inputs["Emission Color"])
            bsdf.inputs["Emission Strength"].default_value = 1.0

    sky_obj.data.materials.clear()
    sky_obj.data.materials.append(mat)
    print(f"  Applied {img_name} to SkySphere material")


# ---------------------------------------------------------------------------
# Luxury rug
# ---------------------------------------------------------------------------
def apply_rug_texture():
    """Apply luxury rug texture to AreaRug object if it exists."""
    tex_path = os.path.join(TEXTURE_DIR, "luxury_rug_basecolor.png")
    rug_obj = None
    for obj in bpy.data.objects:
        if "AreaRug" in obj.name:
            rug_obj = obj
            break

    if rug_obj is None:
        print("  No AreaRug object found, skipping rug texture")
        return

    if not os.path.exists(tex_path):
        print(f"  Warning: rug texture not found: {tex_path}")
        return

    if rug_obj.data.materials:
        mat = rug_obj.data.materials[0]
    else:
        mat = bpy.data.materials.new("LuxuryRug")
        rug_obj.data.materials.append(mat)

    apply_texture_to_material(mat, tex_path, projection="FLAT", scale=(1.0, 1.0, 1.0))
    print("  Rug texture applied to AreaRug")


# ---------------------------------------------------------------------------
# Bedroom accent wall handling
# ---------------------------------------------------------------------------
def apply_special_wall_textures():
    """Apply plant wall and accent wall textures to specially named materials."""
    applied = 0
    for mat in bpy.data.materials:
        mat_lower = mat.name.lower()
        for key, tex_file in WALL_TEXTURES.items():
            if key in mat_lower:
                tex_path = os.path.join(TEXTURE_DIR, tex_file)
                if apply_texture_to_material(
                    mat, tex_path, projection="BOX", scale=(0.1, 0.1, 0.1)
                ):
                    applied += 1
                break
    return applied


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    print("=" * 60)
    print("apply_textures.py: applying image textures to materials")
    print("=" * 60)

    if not os.path.isdir(TEXTURE_DIR):
        print(f"Texture directory not found: {TEXTURE_DIR}")
        print("Run 'python src/generate_textures.py' first to create textures.")
        return

    # 1. Special wall textures (plant wall, bedroom accent)
    print("\n--- Special wall textures ---")
    wall_count = apply_special_wall_textures()
    print(f"  Applied {wall_count} special wall texture(s)")

    # 2. General material textures
    print("\n--- General material textures ---")
    applied = 0
    skipped_glass = 0
    for mat in bpy.data.materials:
        mat_lower = mat.name.lower()

        # Skip glass, garden, furniture, and already-handled special materials
        if "glass" in mat_lower:
            skipped_glass += 1
            continue
        if any(k in mat_lower for k in WALL_TEXTURES):
            continue

        matched = False
        for pattern, tex_file, projection, scale in TEXTURE_MAP:
            if pattern in mat_lower:
                tex_path = os.path.join(TEXTURE_DIR, tex_file)
                if apply_texture_to_material(mat, tex_path, projection, scale):
                    applied += 1
                matched = True
                break

        if not matched and mat_lower not in (
            "dots stroke", "skysphermat",
        ):
            # Only log truly unmatched structural materials
            has_bsdf = (
                mat.use_nodes
                and mat.node_tree
                and mat.node_tree.nodes.get("Principled BSDF")
            )
            if has_bsdf:
                pass  # many garden/furniture materials, no need to warn

    print(f"  Applied textures to {applied} material(s), skipped {skipped_glass} glass")

    # 3. Sky sphere / world background
    print("\n--- Sky setup ---")
    sky_path = os.path.join(TEXTURE_DIR, "sky_sphere_basecolor.png")
    setup_sky(sky_path)

    # 4. Luxury rug
    print("\n--- Rug texture ---")
    apply_rug_texture()

    print("\n" + "=" * 60)
    total = applied + wall_count
    print(f"apply_textures.py: done ({total} textures applied)")
    print("=" * 60)


main()
