"""Fix fountain water: PURE SATURATED BLUE, no emission/glossy tricks."""
import bpy

def fix():
    for obj in bpy.data.objects:
        if 'Fountain' not in obj.name:
            continue
        if not hasattr(obj.data, 'materials'):
            continue
        if 'Water' not in obj.name:
            continue

        # PURE BLUE - Principled BSDF, no transmission, no alpha, just BLUE
        mat = bpy.data.materials.new(name=f"BlueWater_{obj.name}")
        mat.use_nodes = True
        nt = mat.node_tree
        bsdf = nt.nodes['Principled BSDF']
        bsdf.inputs['Base Color'].default_value = (0.0, 0.15, 0.6, 1.0)  # vivid blue
        bsdf.inputs['Roughness'].default_value = 0.1  # slightly glossy
        bsdf.inputs['Metallic'].default_value = 0.0
        bsdf.inputs['Transmission Weight'].default_value = 0.0  # NOT transparent
        bsdf.inputs['Alpha'].default_value = 1.0  # fully opaque
        bsdf.inputs['Specular IOR Level'].default_value = 0.8  # bright specular

        if len(obj.data.materials) > 0:
            obj.data.materials[0] = mat
        else:
            obj.data.materials.append(mat)
        print(f"  {obj.name} -> vivid blue diffuse")

    bpy.context.view_layer.update()
    print("Water is now PURE BLUE. No transparency, no emission, just blue.")

fix()
