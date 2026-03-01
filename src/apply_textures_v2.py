"""Apply generated textures to Blender scene objects by name.

Creates unique materials per object group so shared GLB materials
don't interfere.  Run via:
    ns={}; exec(open(r'F:\home\exploded-hexagon-home\src\apply_textures_v2.py').read(), ns)
"""

import bpy
import os

PROJECT_ROOT = r"F:\home\exploded-hexagon-home"
TEX = os.path.join(PROJECT_ROOT, "assets", "textures")

# ── helpers ──────────────────────────────────────────────────────────────────

def _load_img(fname):
    path = os.path.join(TEX, fname)
    if not os.path.exists(path):
        print(f"  MISSING: {path}")
        return None
    existing = bpy.data.images.get(fname)
    if existing:
        existing.reload()
        return existing
    return bpy.data.images.load(path)


def _make_textured_mat(name, img, projection="FLAT", scale=(1,1,1),
                       roughness=0.5, metallic=0.0,
                       emission=False, alpha=None):
    """Create or replace a Principled BSDF material with an image texture."""
    mat = bpy.data.materials.get(name)
    if mat is None:
        mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()

    # Output
    out = nodes.new("ShaderNodeOutputMaterial")
    out.location = (400, 0)

    # BSDF
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.location = (100, 0)
    bsdf.inputs["Roughness"].default_value = roughness
    bsdf.inputs["Metallic"].default_value = metallic
    links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])

    if img is not None:
        tc = nodes.new("ShaderNodeTexCoord")
        tc.location = (-700, 0)
        mp = nodes.new("ShaderNodeMapping")
        mp.location = (-500, 0)
        mp.inputs["Scale"].default_value = scale
        ti = nodes.new("ShaderNodeTexImage")
        ti.location = (-250, 0)
        ti.image = img
        ti.projection = projection

        links.new(tc.outputs["Generated"], mp.inputs["Vector"])
        links.new(mp.outputs["Vector"], ti.inputs["Vector"])
        links.new(ti.outputs["Color"], bsdf.inputs["Base Color"])

        if emission:
            if "Emission Color" in bsdf.inputs:
                links.new(ti.outputs["Color"], bsdf.inputs["Emission Color"])
                bsdf.inputs["Emission Strength"].default_value = 1.0

    if alpha is not None:
        mat.blend_method = "ALPHA_BLEND" if hasattr(mat, "blend_method") else None
        bsdf.inputs["Alpha"].default_value = alpha

    return mat


def _assign_mat(obj_name, mat):
    obj = bpy.data.objects.get(obj_name)
    if obj is None:
        return False
    obj.data.materials.clear()
    obj.data.materials.append(mat)
    return True


# ── main ─────────────────────────────────────────────────────────────────────

print("=" * 60)
print("apply_textures_v2: assigning materials by object name")
print("=" * 60)

# 1. Marble floor (atrium only)
print("\n--- Marble floor ---")
marble_img = _load_img("atrium_marble_star_basecolor.png")
marble_mat = _make_textured_mat("MarbleFloor", marble_img,
                                 projection="FLAT", scale=(1.0, 1.0, 1.0),
                                 roughness=0.15, metallic=0.0)
for n in ("atrium_floor",):
    ok = _assign_mat(n, marble_mat)
    print(f"  {n}: {'OK' if ok else 'not found'}")

# 1b. Motorcourt floor (ouroboros tile)
print("\n--- Motorcourt floor (ouroboros) ---")
ouro_img = _load_img("ouroboros_courtyard_basecolor.png")
if ouro_img:
    ouro_mat = _make_textured_mat("OuroborosFloor", ouro_img,
                                   projection="FLAT", scale=(1.0, 1.0, 1.0),
                                   roughness=0.2, metallic=0.0)
    ok = _assign_mat("motorcourt_floor", ouro_mat)
    print(f"  motorcourt_floor: {'OK' if ok else 'not found'}")
else:
    ok = _assign_mat("motorcourt_floor", marble_mat)
    print(f"  motorcourt_floor: fallback to marble")

# 2. Driveway concrete
print("\n--- Driveway ---")
drive_img = _load_img("driveway_basecolor.png")
drive_mat = _make_textured_mat("DrivewayConc", drive_img,
                                projection="FLAT", scale=(20.0, 20.0, 20.0),
                                roughness=0.6)
for n in ("driveway_floor", "driveway_ext_floor"):
    ok = _assign_mat(n, drive_mat)
    print(f"  {n}: {'OK' if ok else 'not found'}")

# 3. Smooth concrete (walls, slabs, retaining walls)
print("\n--- Smooth concrete ---")
conc_img = _load_img("smooth_concrete_basecolor.png")
conc_mat = _make_textured_mat("SmoothConc", conc_img,
                               projection="BOX", scale=(15.0, 15.0, 15.0),
                               roughness=0.4)
concrete_objs = [
    "driveway_walls", "driveway_ext_walls",
    "motorcourt_walls",
    "side_court_left_walls", "side_court_right_walls",
    "wing_a_floor", "wing_a_roof_slab",
    "wing_a_garage_floor", "wing_a_garage_roof_slab",
    "wing_a_garage_facade",  # lower level = garage/utility, concrete walls
    "wing_b_floor", "wing_b_roof_slab",
    "wing_b_garage_floor", "wing_b_garage_roof_slab",
    "wing_b_garage_facade",  # lower level = garage/utility, concrete walls
    "wing_a_atrium_wall", "wing_b_atrium_wall", "wing_c_atrium_wall",  # concrete walls between atrium and wing floors
    "wing_c_floor", "wing_c_roof_slab",
    "master_triangle_floor", "master_triangle_roof_slab",
]
for n in concrete_objs:
    ok = _assign_mat(n, conc_mat)
    print(f"  {n}: {'OK' if ok else 'not found'}")

# 4. Ground / lawn
print("\n--- Lawn / ground ---")
lawn_img = _load_img("lawn_basecolor.png")
lawn_mat = _make_textured_mat("LawnGround", lawn_img,
                               projection="FLAT", scale=(60.0, 60.0, 60.0),
                               roughness=0.85)
for n in ("ground", "side_court_left_floor", "side_court_right_floor"):
    ok = _assign_mat(n, lawn_mat)
    print(f"  {n}: {'OK' if ok else 'not found'}")

# 5. Glass facades
print("\n--- Glass facades ---")
glass_mat = bpy.data.materials.get("GlassFacade")
if glass_mat is None:
    glass_mat = bpy.data.materials.new("GlassFacade")
glass_mat.use_nodes = True
gn = glass_mat.node_tree.nodes
gl = glass_mat.node_tree.links
gn.clear()
out = gn.new("ShaderNodeOutputMaterial"); out.location = (400, 0)
bsdf = gn.new("ShaderNodeBsdfPrincipled"); bsdf.location = (100, 0)
bsdf.inputs["Base Color"].default_value = (0.85, 0.92, 0.95, 1.0)
bsdf.inputs["Roughness"].default_value = 0.05
bsdf.inputs["Metallic"].default_value = 0.0
bsdf.inputs["Transmission Weight"].default_value = 0.9
bsdf.inputs["IOR"].default_value = 1.45
bsdf.inputs["Alpha"].default_value = 0.3
gl.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
glass_mat.use_backface_culling = False

glass_objs = [
    "atrium_facade", "atrium_roof",
    "master_triangle_facade",
    "wing_a_facade",
    "wing_b_facade",
    "wing_c_facade",
]
for n in glass_objs:
    ok = _assign_mat(n, glass_mat)
    print(f"  {n}: {'OK' if ok else 'not found'}")

# 6. Bedroom accent wall
print("\n--- Accent wall ---")
accent_img = _load_img("accent_wall_bedroom_basecolor.png")
accent_mat = _make_textured_mat("AccentWall", accent_img,
                                 projection="BOX", scale=(3.0, 3.0, 3.0),
                                 roughness=0.3)
ok = _assign_mat("bedroom_accent_wall", accent_mat)
print(f"  bedroom_accent_wall: {'OK' if ok else 'not found'}")
# Add backfacing shader: atrium side shows concrete, bedroom side shows accent
if ok and accent_mat.node_tree:
    _an = accent_mat.node_tree.nodes
    _al = accent_mat.node_tree.links
    _bsdf = next((n for n in _an if n.type == 'BSDF_PRINCIPLED'), None)
    _out = next((n for n in _an if n.type == 'OUTPUT_MATERIAL'), None)
    if _bsdf and _out:
        _cb = _an.new('ShaderNodeBsdfPrincipled')
        _cb.location = (_bsdf.location.x, _bsdf.location.y - 300)
        _ct = _an.new('ShaderNodeTexImage')
        _ct.location = (_cb.location.x - 300, _cb.location.y)
        _ci = _load_img("smooth_concrete_basecolor.png")
        _ct.image = _ci
        _ctc = _an.new('ShaderNodeTexCoord')
        _ctc.location = (_ct.location.x - 400, _ct.location.y)
        _cm = _an.new('ShaderNodeMapping')
        _cm.location = (_ct.location.x - 200, _ct.location.y)
        _cm.inputs['Scale'].default_value = (0.15, 0.15, 0.15)
        _al.new(_ctc.outputs['Object'], _cm.inputs['Vector'])
        _al.new(_cm.outputs['Vector'], _ct.inputs['Vector'])
        _al.new(_ct.outputs['Color'], _cb.inputs['Base Color'])
        _cb.inputs['Roughness'].default_value = 0.4
        _gn = _an.new('ShaderNodeNewGeometry')
        _gn.location = (_bsdf.location.x + 200, _bsdf.location.y + 200)
        _mx = _an.new('ShaderNodeMixShader')
        _mx.location = (_bsdf.location.x + 400, _bsdf.location.y)
        for _lk in list(_al):
            if _lk.to_node == _out and _lk.to_socket.name == 'Surface':
                _al.remove(_lk)
        _al.new(_gn.outputs['Backfacing'], _mx.inputs['Fac'])
        _al.new(_bsdf.outputs['BSDF'], _mx.inputs[1])
        _al.new(_cb.outputs['BSDF'], _mx.inputs[2])
        _al.new(_mx.outputs['Shader'], _out.inputs['Surface'])

# 7. Plant wall (atrium-facing side of accent wall, if separate object exists)
print("\n--- Plant wall ---")
plant_img = _load_img("plant_wall_basecolor.png")
if plant_img:
    plant_mat = _make_textured_mat("PlantWall", plant_img,
                                    projection="BOX", scale=(0.05, 0.05, 0.05),
                                    roughness=0.7)
    # Check for plant_wall object
    ok = _assign_mat("plant_wall", plant_mat)
    print(f"  plant_wall: {'OK' if ok else 'object not found (expected)'}")

# 8. Sky (procedural HOSEK_WILKIE, no banding)
print("\n--- Sky (procedural) ---")
world = bpy.context.scene.world
if world is None:
    world = bpy.data.worlds.new("World")
    bpy.context.scene.world = world
world.use_nodes = True
wn = world.node_tree.nodes
wl = world.node_tree.links
for node in list(wn):
    if node.type in ("TEX_ENVIRONMENT", "TEX_IMAGE", "TEX_COORD", "MAPPING", "TEX_SKY"):
        wn.remove(node)
bg = None
wo = None
for node in wn:
    if node.type == "BACKGROUND":
        bg = node
    elif node.type == "OUTPUT_WORLD":
        wo = node
if bg is None:
    bg = wn.new("ShaderNodeBackground")
    bg.location = (0, 0)
if wo is None:
    wo = wn.new("ShaderNodeOutputWorld")
    wo.location = (300, 0)
    wl.new(bg.outputs["Background"], wo.inputs["Surface"])
sky = wn.new("ShaderNodeTexSky")
sky.location = (-300, 0)
sky.sky_type = "HOSEK_WILKIE"
sky.sun_elevation = 0.785  # ~45 degrees
sky.sun_rotation = 0.0
sky.turbidity = 2.5
sky.ground_albedo = 0.3
wl.new(sky.outputs["Color"], bg.inputs["Color"])
bg.inputs["Strength"].default_value = 1.0
print("  Procedural sky: HOSEK_WILKIE, 45° elevation")

print("\n" + "=" * 60)
print("apply_textures_v2: DONE")
print("=" * 60)
