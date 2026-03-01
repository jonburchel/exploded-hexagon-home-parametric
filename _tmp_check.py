import bpy
FT = 0.3048
names = ['wing_a_atrium_wall', 'wing_b_atrium_wall', 'wing_c_atrium_wall']
results = []
for n in names:
    ob = bpy.data.objects.get(n)
    if ob is not None and ob.type == 'MESH':
        world = ob.matrix_world
        lo = 9999.0
        hi = -9999.0
        for v in ob.data.vertices:
            z = (world @ v.co).z
            if z < lo:
                lo = z
            if z > hi:
                hi = z
        results.append(n + ': ' + str(round(lo/FT, 1)) + 'ft to ' + str(round(hi/FT, 1)) + 'ft')
print('\n'.join(results))