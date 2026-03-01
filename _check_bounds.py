import bpy
from mathutils import Vector

FT = 0.3048
objects_of_interest = [
    'atrium_floor', 'atrium_facade',
    'wing_a_garage_floor', 'wing_a_garage_facade',
    'wing_b_garage_floor', 'wing_b_garage_facade',
    'wing_c_atrium_wall',
]

for name in objects_of_interest:
    obj = bpy.data.objects.get(name)
    if obj is None:
        print(f"{name}: NOT FOUND")
        continue
    me = obj.data
    mat = obj.matrix_world
    zs = [round((mat @ Vector((*v.co,))).z / FT, 3) for v in me.vertices]
    mats = [m.name for m in obj.data.materials] if obj.data.materials else ['NO_MAT']
    print(f"{name}: z=[{min(zs):.3f}, {max(zs):.3f}]ft  mats={mats}")
