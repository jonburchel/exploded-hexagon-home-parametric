import bpy, os

FT = 0.3048
GLB = r"F:\home\exploded-hexagon-home\out\massing_s23_d7.glb"

# Remove old building meshes (keep cameras, lights, garden objects)
keep_prefixes = ['Sun', 'Camera', 'VerifyCam', 'Light', 'Garden_', 'Fountain', 
                 'potted_', 'indoor_', 'monstera', 'bird_of_paradise', 'palm_tree', 'fern',
                 'BanyanTree', 'banyan', 'Planter']
for obj in list(bpy.data.objects):
    keep_obj = False
    for prefix in keep_prefixes:
        if obj.name.startswith(prefix):
            keep_obj = True
            break
    if obj.type == 'MESH' and not keep_obj:
        bpy.data.objects.remove(obj, do_unlink=True)

# Import fresh GLB
bpy.ops.import_scene.gltf(filepath=GLB)
print(f"Imported GLB: {sum(1 for o in bpy.data.objects if o.type == 'MESH')} mesh objects")
