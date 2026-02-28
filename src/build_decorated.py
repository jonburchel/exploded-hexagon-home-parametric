"""
Build the fully decorated scene: base GLB + garden + furniture + plants + render settings.

Runs each decoration script in sequence via Blender headless, then saves a .blend
file with everything baked in (collections, lights, materials, furniture, garden).

Usage:
  python src/build_decorated.py
  python src/build_decorated.py --render   (also produce production renders)
"""

import subprocess
import sys
import os
import json
import shutil

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
CONFIG_PATH = os.path.join(SCRIPT_DIR, "config.json")

# Load config for blender path
with open(CONFIG_PATH) as f:
    cfg = json.load(f)

BLENDER = cfg.get("blender_executable", "blender")
BASE_GLB = os.path.join(PROJECT_DIR, "out", "massing_s23_d7.glb")
DECORATED_GLB = os.path.join(PROJECT_DIR, "out", "massing_s23_d7_decorated.glb")
BLEND_OUT = os.path.join(PROJECT_DIR, "out", "massing_s23_d7.blend")

# Verify blender exists
if not os.path.exists(BLENDER):
    print(f"ERROR: Blender not found at {BLENDER}")
    sys.exit(1)

if not os.path.exists(BASE_GLB):
    print(f"ERROR: Base GLB not found at {BASE_GLB}")
    print("Run 'python -m src.main' first to generate it.")
    sys.exit(1)

# Working copy so we don't clobber the base
work_glb = os.path.join(PROJECT_DIR, "out", "_work_decorated.glb")
shutil.copy2(BASE_GLB, work_glb)

# Decoration scripts to run in order, each imports work_glb and exports back to it
DECORATION_STEPS = [
    ("Atrium garden", os.path.join(SCRIPT_DIR, "atrium_garden.py")),
    ("Wing B furniture", os.path.join(SCRIPT_DIR, "furnish_wingb.py")),
]

# Check if realistic plant assets exist
plants_dir = os.path.join(PROJECT_DIR, "assets", "models", "plants")
has_realistic_plants = os.path.exists(plants_dir) and any(
    os.path.isdir(os.path.join(plants_dir, d)) for d in os.listdir(plants_dir)
) if os.path.exists(plants_dir) else False

if has_realistic_plants:
    DECORATION_STEPS.append(
        ("Realistic plants", os.path.join(SCRIPT_DIR, "place_realistic_plants.py"))
    )

print("=" * 60)
print("Building decorated scene")
print("=" * 60)

for step_name, script_path in DECORATION_STEPS:
    if not os.path.exists(script_path):
        print(f"  SKIP {step_name}: {script_path} not found")
        continue

    print(f"\n  [{step_name}]")
    cmd = [
        BLENDER, "--background", "--python", script_path,
        "--", work_glb, work_glb
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if result.returncode != 0:
        print(f"    WARNING: {step_name} returned code {result.returncode}")
        # Print last 10 lines of stderr for debugging
        err_lines = result.stderr.strip().split('\n')[-10:]
        for line in err_lines:
            print(f"    {line}")
    else:
        # Print script output summary
        out_lines = result.stdout.strip().split('\n')
        for line in out_lines[-5:]:
            if line.strip():
                print(f"    {line.strip()}")

# Now run blender_startup.py to apply materials, lighting, collections, and save .blend
print(f"\n  [Final scene setup + save .blend]")
save_script = f'''
import bpy, sys, os
sys.path.insert(0, r"{SCRIPT_DIR}")

# Run blender_startup.py contents for materials/lighting/collections
exec(open(r"{os.path.join(SCRIPT_DIR, 'blender_startup.py')}").read())

# Save as .blend (preserves collections, lights, materials, render settings)
blend_path = r"{BLEND_OUT}"
bpy.ops.wm.save_as_mainfile(filepath=blend_path)
print(f"Saved .blend: {{blend_path}}")
'''

# Write temp script
temp_script = os.path.join(PROJECT_DIR, "out", "_save_blend.py")
with open(temp_script, 'w') as f:
    f.write(save_script)

cmd = [
    BLENDER, "--background", "--python", temp_script,
    "--", work_glb
]
result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
if result.returncode != 0:
    print(f"    WARNING: save step returned code {result.returncode}")
    err_lines = result.stderr.strip().split('\n')[-10:]
    for line in err_lines:
        print(f"    {line}")
else:
    out_lines = result.stdout.strip().split('\n')
    for line in out_lines[-5:]:
        if line.strip():
            print(f"    {line.strip()}")

# Copy decorated GLB to main output
shutil.copy2(work_glb, DECORATED_GLB)
# Also update the main GLB so file-watch picks it up
shutil.copy2(work_glb, BASE_GLB)

# Clean up temp files
for tmp in [work_glb, temp_script]:
    try:
        os.remove(tmp)
    except OSError:
        pass

print(f"\n{'=' * 60}")
print(f"Decorated GLB: {DECORATED_GLB}")
print(f"Main GLB updated: {BASE_GLB}")
print(f"Blend file: {BLEND_OUT}")
print(f"{'=' * 60}")

# Optional: run production renders
if "--render" in sys.argv:
    print("\n  [Production renders]")
    render_script = os.path.join(SCRIPT_DIR, "render_production.py")
    if os.path.exists(render_script):
        cmd = [
            BLENDER, "--background", "--python", render_script,
            "--", DECORATED_GLB
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        out_lines = result.stdout.strip().split('\n')
        for line in out_lines[-8:]:
            if line.strip():
                print(f"    {line.strip()}")
