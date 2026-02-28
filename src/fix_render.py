import bpy, math, os
s=bpy.context.scene
s.render.engine='CYCLES'
s.view_settings.view_transform='Filmic'
s.view_settings.exposure=0.0
s.view_settings.look='Medium High Contrast'
s.view_settings.gamma=1.0
# Sky: deep blue zenith -> Carolina blue horizon -> dark green earth
w=s.world or bpy.data.worlds.new("World")
s.world=w; w.use_nodes=True; n=w.node_tree.nodes; l=w.node_tree.links; n.clear()
geom=n.new('ShaderNodeNewGeometry')
sep=n.new('ShaderNodeSeparateXYZ')
l.new(geom.outputs['Normal'], sep.inputs['Vector'])
# In world shader, upward rays have NEGATIVE Normal Z, so negate first
negate=n.new('ShaderNodeMath'); negate.operation='MULTIPLY'
negate.inputs[1].default_value=-1.0
l.new(sep.outputs['Z'], negate.inputs[0])
# Clamp negated Z to 0..1 for sky gradient (0=horizon, 1=zenith)
sky_clamp=n.new('ShaderNodeClamp')
sky_clamp.inputs['Min'].default_value=0.0
sky_clamp.inputs['Max'].default_value=1.0
l.new(negate.outputs['Value'], sky_clamp.inputs['Value'])
# Sky color ramp: Carolina blue at horizon -> deep blue at zenith
sky_ramp=n.new('ShaderNodeValToRGB')
sky_ramp.color_ramp.elements[0].position=0.0
sky_ramp.color_ramp.elements[0].color=(0.35, 0.65, 0.90, 1.0)  # Carolina blue horizon
sky_ramp.color_ramp.elements[1].position=1.0
sky_ramp.color_ramp.elements[1].color=(0.08, 0.15, 0.55, 1.0)  # deep blue zenith
l.new(sky_clamp.outputs['Result'], sky_ramp.inputs['Fac'])
# Dark green earth below horizon
ground=n.new('ShaderNodeRGB')
ground.outputs[0].default_value=(0.08, 0.22, 0.06, 1.0)  # dark forest green
# Sharp horizon cut: Z < -0.005 (sky) -> 0, Z > 0.005 (ground) -> 1
horizon=n.new('ShaderNodeMapRange')
horizon.inputs['From Min'].default_value=-0.005
horizon.inputs['From Max'].default_value=0.005
l.new(sep.outputs['Z'], horizon.inputs['Value'])
mix=n.new('ShaderNodeMixRGB')
l.new(horizon.outputs['Result'], mix.inputs['Fac'])
l.new(sky_ramp.outputs['Color'], mix.inputs['Color1'])  # Fac=0 -> sky
l.new(ground.outputs[0], mix.inputs['Color2'])            # Fac=1 -> ground
bg=n.new('ShaderNodeBackground')
bg.inputs['Strength'].default_value=1.0
l.new(mix.outputs[0], bg.inputs['Color'])
o=n.new('ShaderNodeOutputWorld')
l.new(bg.outputs[0], o.inputs['Surface'])
# Remove ALL existing lights first so we don't stack duplicates
for obj in list(bpy.data.objects):
    if obj.type=='LIGHT':
        bpy.data.objects.remove(obj, do_unlink=True)
# Sun lamp: nearly overhead (X=10deg = sun at 80deg elevation)
sd=bpy.data.lights.new("Sun","SUN")
sun=bpy.data.objects.new("Sun",sd)
s.collection.objects.link(sun)
sun.rotation_euler=(math.radians(10), 0, math.radians(-30))
sun.data.energy=8.0
sun.data.color=(1.0, 0.97, 0.92)
sun.data.angle=math.radians(0.545)
# Fill from below/side
fd=bpy.data.lights.new("FillLight","SUN")
fill=bpy.data.objects.new("FillLight",fd)
s.collection.objects.link(fill)
fill.rotation_euler=(math.radians(50), 0, math.radians(150))
fill.data.energy=1.5
fill.data.color=(0.9, 0.93, 1.0)
print("Done: Nishita sky + Sun (80deg elev, energy=8)")
