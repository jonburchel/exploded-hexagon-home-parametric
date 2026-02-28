"""Headless overnight render: resume walkthrough from frame 275, step=2."""
import bpy
import sys
import os

# Settings
BLEND_FILE = r"F:\home\exploded-hexagon-home\F__home_exploded-hexagon-home_out_massing_s23_d7.blend"
OUTPUT_DIR = r"F:\home\exploded-hexagon-home\out\massing_s23_d7.glb_frames"

s = bpy.context.scene

# Resume from frame 275, every other frame
s.frame_start = 275
s.frame_end = 5213
s.frame_step = 2

# Output settings
s.render.filepath = os.path.join(OUTPUT_DIR, "")
s.render.image_settings.file_format = 'PNG'
s.render.image_settings.color_mode = 'RGB'
s.render.image_settings.compression = 15

# Ensure GPU + Cycles
s.render.engine = 'CYCLES'
s.cycles.device = 'GPU'
s.cycles.samples = 16
s.cycles.use_denoising = True

# Set compute device
prefs = bpy.context.preferences.addons.get('cycles')
if prefs:
    prefs.preferences.compute_device_type = 'CUDA'
    prefs.preferences.get_devices()
    for d in prefs.preferences.devices:
        d.use = True

# Skip existing frames (in case we restart)
s.render.use_file_extension = True
s.render.use_overwrite = False

print(f"Rendering frames {s.frame_start}-{s.frame_end} step {s.frame_step}")
print(f"Output: {OUTPUT_DIR}")
print(f"Estimated frames: {(s.frame_end - s.frame_start) // s.frame_step + 1}")
print(f"At ~17s/frame, ETA: ~{((s.frame_end - s.frame_start) // s.frame_step + 1) * 17 / 3600:.1f} hours")

# Render animation
bpy.ops.render.render(animation=True)
print("RENDER COMPLETE!")
