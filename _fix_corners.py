import bpy

mat = bpy.data.materials.get('SmoothConc')
if mat:
    for obj in bpy.data.objects:
        if 'corner' in obj.name.lower() and obj.type == 'MESH':
            obj.data.materials.clear()
            obj.data.materials.append(mat)
            print(f'  {obj.name}: concrete assigned')
else:
    print('smooth_concrete material not found')
