import bpy, os

GLB = r"F:\home\exploded-hexagon-home\out\massing_s23_d7.glb"

# Remove old building meshes (keep garden/furniture/camera/lights)
keep_prefixes = ('garden_', 'furniture_', 'Camera', 'Sun', 'Light', 'VerifyCam',
                 'Tree', 'Bush', 'Palm', 'Banyan', 'Ficus', 'plant_', 'Fountain',
                 'tree_', 'palm_')
to_remove = []
for obj in bpy.data.objects:
    keep_obj = False
    for prefix in keep_prefixes:
        if obj.name.startswith(prefix):
            keep_obj = True
            break
    if obj.type == 'MESH' and not keep_obj:
        to_remove.append(obj)

for obj in to_remove:
    bpy.data.objects.remove(obj, do_unlink=True)

print(f"Removed {len(to_remove)} old meshes")

# Import fresh GLB - NO scaling needed, GLB is already in meters
bpy.ops.import_scene.gltf(filepath=GLB)

print("GLB reloaded (no scale applied - already in meters)")
print(f"Total mesh objects: {sum(1 for o in bpy.data.objects if o.type=='MESH')}")
