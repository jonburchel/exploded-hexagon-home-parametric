import bpy

# Remove all existing mesh objects
for obj in [o for o in bpy.data.objects if o.type == 'MESH']:
    bpy.data.objects.remove(obj, do_unlink=True)

# Clean orphan meshes
for mesh in bpy.data.meshes:
    if mesh.users == 0:
        bpy.data.meshes.remove(mesh)

# Import fresh GLB
bpy.ops.import_scene.gltf(filepath=r'F:\home\exploded-hexagon-home\out\massing_s23_d7.glb')
mesh_count = len([o for o in bpy.data.objects if o.type == 'MESH'])
names = sorted([o.name for o in bpy.data.objects if o.type == 'MESH'])
print(f'Imported {mesh_count} mesh objects')
print(', '.join(names))
