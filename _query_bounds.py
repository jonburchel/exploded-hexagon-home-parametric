def run():
    import bpy, mathutils
    result = []
    for o in sorted(bpy.data.objects, key=lambda x: x.name):
        if o.type != 'MESH':
            continue
        bb = [o.matrix_world @ mathutils.Vector(c) for c in o.bound_box]
        mn = [min(b[i] for b in bb) for i in range(3)]
        mx = [max(b[i] for b in bb) for i in range(3)]
        result.append('{}: x=[{:.3f},{:.3f}] y=[{:.3f},{:.3f}] z=[{:.3f},{:.3f}]'.format(
            o.name, mn[0], mx[0], mn[1], mx[1], mn[2], mx[2]))
    print('\n'.join(result))

run()