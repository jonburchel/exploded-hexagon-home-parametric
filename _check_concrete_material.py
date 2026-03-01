import bpy

def _mat_info(name):
    mat = bpy.data.materials.get(name)
    if not mat or not mat.use_nodes:
        print(name, "missing")
        return
    bsdf = None
    mapping = None
    for n in mat.node_tree.nodes:
        if n.type == "BSDF_PRINCIPLED" and bsdf is None:
            bsdf = n
        if n.type == "MAPPING" and mapping is None:
            mapping = n
    rough = bsdf.inputs["Roughness"].default_value if bsdf else None
    scale = tuple(mapping.inputs["Scale"].default_value) if mapping else None
    print(name, "roughness", rough, "scale", scale)

_mat_info("SmoothConc")
_mat_info("AccentWall")

for obj_name in ("atrium_top_wall", "bedroom_accent_wall", "wing_b_atrium_wall"):
    obj = bpy.data.objects.get(obj_name)
    if not obj or not obj.data or not hasattr(obj.data, "materials"):
        print(obj_name, "missing")
        continue
    mats = [m.name for m in obj.data.materials if m]
    print(obj_name, "materials", mats)
