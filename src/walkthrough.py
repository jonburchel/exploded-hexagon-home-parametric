"""
Cinematic walkthrough animation for the Exploded Hexagon Home.

Opens the user's saved .blend (with GPU/Cycles/lighting settings intact)
and adds a cinematic camera path through the building.

Usage (headless render):
  blender -b out/massing_s23_d7.blend --python src/walkthrough.py -- renders/cinematic

Preview in viewport (scrub timeline, Numpad-0 for camera view):
  blender out/massing_s23_d7.blend --python src/walkthrough.py

Choreography:
  1.  Approach from front
  2.  Descend driveway (slow panning)
  3.  Cross courtyard
  4.  Enter atrium, 360-degree panoramic
  5.  Walk to Wing C (curving around fountain)
  6.  Return to atrium
  7.  Fly up to master-triangle bedroom level
  8.  Flythrough bedroom
  9.  Exit onto terrace, fly out 30 yards
  10. Orbit house at 40 ft elevation
  11. Spiral down to ground at rear
"""

import bpy
import sys
import os
import math
from mathutils import Vector, Euler

# ---------------------------------------------------------------------------
# CLI args:  -- [output_dir_or_mp4]
# ---------------------------------------------------------------------------
argv = sys.argv
args = argv[argv.index("--") + 1:] if "--" in argv else []
output_path = os.path.abspath(args[0]) if args else os.path.abspath("renders/cinematic")
os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

scene = bpy.context.scene
FPS = 30

# ---------------------------------------------------------------------------
# Unit helpers
# ---------------------------------------------------------------------------
FT = 0.3048

def ft(*vals):
    """Convert feet to meters. Single value -> scalar, multiple -> tuple."""
    r = tuple(v * FT for v in vals)
    return r[0] if len(r) == 1 else r

# ---------------------------------------------------------------------------
# Building reference points (feet, converted on use)
# ---------------------------------------------------------------------------
DRIVEWAY_TOP_Y     = ft(-114.28)
DRIVEWAY_BOTTOM_Y  = ft(-69.28)
UPPER_GROUND_Z     = ft(13.0)
COURTYARD_Z        = ft(-1.0)
ATRIUM_FRONT_Y     = ft(-19.92)
ATRIUM_FLOOR_Z     = ft(-2.0)
WING_C_CENTER_Y    = ft(29.88)
WING_C_FAR_Y       = ft(39.84)
WING_C_FLOOR_Z     = ft(0.0)
MASTER_TRI_TOP_Z   = ft(26.0)
ATRIUM_ROOF_APEX_Z = ft(49.0)
BEDROOM_XY         = ft(-31.77, -4.19)
SITTING_XY         = ft(-42.67, 0.13)
EYE_H              = ft(5.5)
ORBIT_R            = ft(130)
ORBIT_Z            = ft(40)
FLYOUT_DIST        = ft(90)

# ---------------------------------------------------------------------------
# Clean up any previous walkthrough objects
# ---------------------------------------------------------------------------
for name in ("CinematicCam", "CinematicTarget",
             "WalkthroughCam", "LookTarget"):
    obj = bpy.data.objects.get(name)
    if obj:
        bpy.data.objects.remove(obj, do_unlink=True)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def driveway_z(y_m):
    """Camera Z on the driveway ramp (linear upper-ground -> courtyard)."""
    t = (y_m - DRIVEWAY_TOP_Y) / (DRIVEWAY_BOTTOM_Y - DRIVEWAY_TOP_Y)
    t = max(0.0, min(1.0, t))
    return (UPPER_GROUND_Z * (1 - t) + COURTYARD_Z * t) + EYE_H

def orbit_pt(angle_deg, radius, z, cx=0, cy=0):
    """Point on a horizontal circle."""
    a = math.radians(angle_deg)
    return (cx + radius * math.cos(a), cy + radius * math.sin(a), z)

# ---------------------------------------------------------------------------
# Build choreography
# ---------------------------------------------------------------------------
choreography = []
t = 0.0  # seconds accumulator

# === Phase 1: Approach from distance ======================================
start_y = DRIVEWAY_TOP_Y - ft(50)
choreography += [
    (t,   (0, start_y,                    UPPER_GROUND_Z + EYE_H),
           (0, DRIVEWAY_TOP_Y + ft(30),   UPPER_GROUND_Z),
           "Approach from distance"),
]
t += 4
choreography += [
    (t,   (0, DRIVEWAY_TOP_Y - ft(15),    UPPER_GROUND_Z + EYE_H),
           (0, DRIVEWAY_BOTTOM_Y,          ft(5)),
           "Nearing driveway entrance"),
]
t += 4
choreography += [
    (t,   (0, DRIVEWAY_TOP_Y,             UPPER_GROUND_Z + EYE_H),
           (0, DRIVEWAY_BOTTOM_Y,          COURTYARD_Z + ft(10)),
           "At driveway entrance"),
]
t += 4

# === Phase 2: Descend driveway with slow panning ==========================
dy4 = (DRIVEWAY_BOTTOM_Y - DRIVEWAY_TOP_Y) / 4
for i, (look_x, look_z_off, desc) in enumerate([
    (ft(-20), UPPER_GROUND_Z,            "Pan left, retaining wall"),
    (ft(20),  COURTYARD_Z + ft(25),      "Pan right and up"),
    (ft(-15), COURTYARD_Z,               "Pan left, approaching courtyard"),
]):
    cam_y = DRIVEWAY_TOP_Y + (i + 1) * dy4
    choreography.append(
        (t, (0, cam_y, driveway_z(cam_y)),
             (look_x, DRIVEWAY_BOTTOM_Y + ft(10), look_z_off), desc))
    t += 3.5

choreography.append(
    (t, (0, DRIVEWAY_BOTTOM_Y, COURTYARD_Z + EYE_H),
         (0, ATRIUM_FRONT_Y, ATRIUM_FLOOR_Z + ft(15)),
         "Reached courtyard floor"))
t += 3.5

# === Phase 3: Cross courtyard =============================================
mid_y = (DRIVEWAY_BOTTOM_Y + ATRIUM_FRONT_Y) / 2
choreography += [
    (t,   (0, mid_y,                      COURTYARD_Z + EYE_H),
           (ft(25), ATRIUM_FRONT_Y + ft(5), ft(30)),
           "Crossing courtyard, look right & up"),
]
t += 5
choreography += [
    (t,   (0, ATRIUM_FRONT_Y - ft(5),     COURTYARD_Z + EYE_H),
           (ft(-20), ATRIUM_FRONT_Y + ft(10), ft(20)),
           "Near atrium entrance, pan left"),
]
t += 5

# === Phase 4: Enter atrium, 360-degree panoramic ==========================
atrium_looks = [
    ((0,  0,       ATRIUM_ROOF_APEX_Z),            "Look up at glass roof"),
    ((ft(30), ft(-5), ATRIUM_FLOOR_Z + ft(8)),      "Pan right toward Wing A"),
    ((0,  ATRIUM_FRONT_Y - ft(10), COURTYARD_Z + ft(12)), "Look back at entrance"),
    ((ft(-30), ft(-8), ft(15)),                      "Pan left toward Wing B"),
    ((0,  ft(5),  ATRIUM_ROOF_APEX_Z),               "Look up at roof apex again"),
    ((ft(15), ft(15), ft(10)),                        "Pan right toward Wing C"),
]
cam_y_start = ATRIUM_FRONT_Y + ft(3)
for i, (look, desc) in enumerate(atrium_looks):
    frac = i / max(len(atrium_looks) - 1, 1)
    cy = cam_y_start + frac * ft(6)  # drift slowly forward
    choreography.append(
        (t, (0, cy, ATRIUM_FLOOR_Z + EYE_H), look, desc))
    t += 3.5

# === Phase 5: Walk to Wing C, curving around fountain =====================
# Fountain centre is near (0, 0); curve right (positive X) to avoid it
choreography += [
    (t,   (ft(10), ft(3),  ATRIUM_FLOOR_Z + EYE_H),
           (ft(5),  ft(15), ATRIUM_FLOOR_Z + ft(8)),
           "Curving right around fountain"),
]
t += 4
choreography += [
    (t,   (ft(12), ft(12), ATRIUM_FLOOR_Z + EYE_H + ft(1)),
           (0, WING_C_CENTER_Y, WING_C_FLOOR_Z + ft(6)),
           "Rounding fountain toward Wing C"),
]
t += 4
choreography += [
    (t,   (ft(5), ft(18), WING_C_FLOOR_Z + EYE_H),
           (0, WING_C_FAR_Y, WING_C_FLOOR_Z + ft(5)),
           "Entering Wing C"),
]
t += 4
choreography += [
    (t,   (0, WING_C_CENTER_Y, WING_C_FLOOR_Z + EYE_H),
           (0, WING_C_FAR_Y, WING_C_FLOOR_Z + ft(5)),
           "In Wing C, looking at far wall"),
]
t += 4

# === Phase 6: Return to atrium ============================================
choreography += [
    (t,   (0, WING_C_CENTER_Y - ft(5), WING_C_FLOOR_Z + EYE_H),
           (ft(-15), ft(5), WING_C_FLOOR_Z + ft(10)),
           "Turning back, pan left"),
]
t += 3
choreography += [
    (t,   (ft(-8), ft(10), ATRIUM_FLOOR_Z + EYE_H + ft(1)),
           (0, ft(-5), ATRIUM_FLOOR_Z + ft(5)),
           "Walking back to atrium centre"),
]
t += 3.5
choreography += [
    (t,   (ft(-5), 0, ATRIUM_FLOOR_Z + EYE_H),
           (0, 0, ATRIUM_ROOF_APEX_Z),
           "In atrium centre, looking up"),
]
t += 3.5

# === Phase 7: Fly up to bedroom level =====================================
choreography += [
    (t,   (ft(-3), ft(-2), ft(15)),
           (0, 0, ATRIUM_FLOOR_Z + ft(5)),
           "Rising, looking down into atrium"),
]
t += 3
choreography += [
    (t,   (ft(-5), ft(-3), MASTER_TRI_TOP_Z + ft(2)),
           (0, 0, ATRIUM_FLOOR_Z),
           "At triangle level, looking through atrium void"),
]
t += 3.5
choreography += [
    (t,   (ft(-10), ft(-3), MASTER_TRI_TOP_Z + EYE_H),
           (BEDROOM_XY[0], BEDROOM_XY[1], MASTER_TRI_TOP_Z + ft(3)),
           "On triangle slab, looking toward bedroom"),
]
t += 3.5

# === Phase 8: Bedroom flythrough ==========================================
choreography += [
    (t,   (ft(-20), ft(-3), MASTER_TRI_TOP_Z + EYE_H),
           (BEDROOM_XY[0], BEDROOM_XY[1], MASTER_TRI_TOP_Z + ft(3)),
           "Approaching bedroom"),
]
t += 4
choreography += [
    (t,   (BEDROOM_XY[0] + ft(3), BEDROOM_XY[1], MASTER_TRI_TOP_Z + EYE_H),
           (BEDROOM_XY[0] - ft(5), BEDROOM_XY[1] + ft(3), MASTER_TRI_TOP_Z + ft(2)),
           "At bed, looking across room"),
]
t += 4
choreography += [
    (t,   (SITTING_XY[0] + ft(5), SITTING_XY[1], MASTER_TRI_TOP_Z + EYE_H),
           (SITTING_XY[0] - ft(10), SITTING_XY[1], MASTER_TRI_TOP_Z + ft(3)),
           "At sitting area, looking outward"),
]
t += 3.5
choreography += [
    (t,   (SITTING_XY[0] + ft(3), SITTING_XY[1] + ft(2), MASTER_TRI_TOP_Z + EYE_H),
           (BEDROOM_XY[0], BEDROOM_XY[1], MASTER_TRI_TOP_Z + ft(4)),
           "Looking back at bed"),
]
t += 3.5

# === Phase 9: Exit to terrace, fly out 30 yards ===========================
terrace_x, terrace_y = ft(-48), ft(0)
choreography += [
    (t,   (terrace_x, terrace_y, MASTER_TRI_TOP_Z + EYE_H),
           (terrace_x - ft(20), terrace_y, MASTER_TRI_TOP_Z),
           "On terrace edge, looking out"),
]
t += 3.5
flyout_x = terrace_x - FLYOUT_DIST
choreography += [
    (t,   (flyout_x, terrace_y, MASTER_TRI_TOP_Z + EYE_H),
           (0, 0, ft(20)),
           "30 yards out, looking back at house"),
]
t += 4.5
# Transition to orbit start (180 deg = negative-X = left side)
choreography += [
    (t,   orbit_pt(180, ORBIT_R, ORBIT_Z),
           (0, 0, ft(15)),
           "Transitioning to orbit"),
]
t += 3

# === Phase 10: Orbit at 40 ft elevation ===================================
ORBIT_STEPS = 8
ORBIT_DUR   = 22.0
for i in range(ORBIT_STEPS + 1):
    angle = 180 + 360 * i / ORBIT_STEPS
    choreography.append(
        (t, orbit_pt(angle, ORBIT_R, ORBIT_Z),
             (0, 0, ft(15)),
             f"Orbit {int(360 * i / ORBIT_STEPS)} deg"))
    t += ORBIT_DUR / ORBIT_STEPS

# === Phase 11: Spiral down to ground at rear ===============================
# 1.75 revolutions: 180 -> 180 + 630 = 810 -> 810 mod 360 = 90 deg = back
SPIRAL_STEPS = 14
SPIRAL_DUR   = 28.0
SPIRAL_REVS  = 1.75
ground_z     = EYE_H
for i in range(SPIRAL_STEPS + 1):
    frac  = i / SPIRAL_STEPS
    angle = 180 + 360 * SPIRAL_REVS * frac
    z     = ORBIT_Z * (1 - frac) + ground_z * frac
    r     = ORBIT_R * (1 - 0.3 * frac)  # tighten slightly
    look_z = ft(15) * (1 - frac) + ft(5) * frac
    choreography.append(
        (t, orbit_pt(angle, r, z),
             (0, 0, look_z),
             f"Spiral {int(frac * 100)}%"))
    t += SPIRAL_DUR / SPIRAL_STEPS

# Final hold
choreography.append(
    (t, orbit_pt(90, ORBIT_R * 0.7, ground_z),
         (0, 0, ft(10)),
         "Final: ground level behind house"))
t += 3

TOTAL_FRAMES = int(choreography[-1][0] * FPS) + 1

# ---------------------------------------------------------------------------
# Create camera + look-target
# ---------------------------------------------------------------------------
cam_data = bpy.data.cameras.new("CinematicCam")
cam_data.type  = "PERSP"
cam_data.lens  = 24
cam_data.clip_start = 0.1
cam_data.clip_end   = 300.0
cam_obj = bpy.data.objects.new("CinematicCam", cam_data)
scene.collection.objects.link(cam_obj)
scene.camera = cam_obj

look_target = bpy.data.objects.new("CinematicTarget", None)
look_target.empty_display_type = "PLAIN_AXES"
look_target.empty_display_size = 0.5
scene.collection.objects.link(look_target)

track = cam_obj.constraints.new("TRACK_TO")
track.target     = look_target
track.track_axis = "TRACK_NEGATIVE_Z"
track.up_axis    = "UP_Y"

# ---------------------------------------------------------------------------
# Keyframe camera and target
# ---------------------------------------------------------------------------
for time_sec, cam_pos, target_pos, _desc in choreography:
    frame = int(time_sec * FPS) + 1
    cam_obj.location = Vector(cam_pos)
    cam_obj.keyframe_insert(data_path="location", frame=frame)
    look_target.location = Vector(target_pos)
    look_target.keyframe_insert(data_path="location", frame=frame)

# Smooth all keyframes to Bezier
for obj in (cam_obj, look_target):
    if not (obj.animation_data and obj.animation_data.action):
        continue
    action = obj.animation_data.action
    fcurves = None
    if hasattr(action, "fcurves"):
        fcurves = action.fcurves
    elif hasattr(action, "layers"):
        for layer in action.layers:
            for strip in layer.strips:
                if hasattr(strip, "channelbags"):
                    for bag in strip.channelbags:
                        fcurves = bag.fcurves
                        break
    if fcurves:
        for fc in fcurves:
            for kp in fc.keyframe_points:
                kp.interpolation = "BEZIER"
                kp.easing = "EASE_IN_OUT"

# ---------------------------------------------------------------------------
# Timeline
# ---------------------------------------------------------------------------
scene.frame_start = 1
scene.frame_end   = TOTAL_FRAMES
scene.render.fps  = FPS

# ---------------------------------------------------------------------------
# Output settings (keep user's engine/samples/GPU, only set output path)
# ---------------------------------------------------------------------------
frames_dir = output_path + "_frames"
os.makedirs(frames_dir, exist_ok=True)
scene.render.filepath = os.path.join(frames_dir, "")
scene.render.image_settings.file_format    = "PNG"
scene.render.image_settings.color_mode     = "RGBA"
scene.render.image_settings.compression    = 15

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
duration_sec = TOTAL_FRAMES / FPS
engine = scene.render.engine
samples = getattr(scene.cycles, "samples", "?") if engine == "CYCLES" else "N/A"
res = f"{scene.render.resolution_x}x{scene.render.resolution_y}"

print(f"\n{'=' * 60}")
print(f"  Cinematic Walkthrough Ready")
print(f"{'=' * 60}")
print(f"  Duration : {duration_sec:.0f}s  ({TOTAL_FRAMES} frames @ {FPS} fps)")
print(f"  Output   : {frames_dir}/0001.png ...")
print(f"  Engine   : {engine}   Samples: {samples}   Res: {res}")
print()
print("  Phases:")
for label in [
    "1.  Approach from front",
    "2.  Descend driveway (panning)",
    "3.  Cross courtyard",
    "4.  Enter atrium (360-degree panoramic)",
    "5.  Walk to Wing C (around fountain)",
    "6.  Return to atrium",
    "7.  Fly up to bedroom level",
    "8.  Bedroom flythrough",
    "9.  Exit to terrace, fly out 30 yards",
    "10. Orbit at 40 ft",
    "11. Spiral down to ground (rear)",
]:
    print(f"        {label}")

# Rough render-time estimate
est_per_frame = 8 if engine == "CYCLES" else 1
est_hours = TOTAL_FRAMES * est_per_frame / 3600
print(f"\n  Est. render time: ~{est_hours:.1f} h  ({est_per_frame}s/frame)")
print(f"  Stitch to MP4:   ffmpeg -framerate {FPS} -i \"{frames_dir}/%04d.png\""
      f" -c:v libx264 -pix_fmt yuv420p \"{output_path}.mp4\"")
print(f"{'=' * 60}\n")

# ---------------------------------------------------------------------------
# Render if headless
# ---------------------------------------------------------------------------
if "--background" in sys.argv or "-b" in sys.argv:
    print("Rendering cinematic walkthrough ...")
    bpy.ops.render.render(animation=True)
    print(f"Done!  Frames in: {frames_dir}")
    print(f"Stitch: ffmpeg -framerate {FPS} -i \"{frames_dir}/%04d.png\""
          f" -c:v libx264 -pix_fmt yuv420p \"{output_path}.mp4\"")
else:
    print("Walkthrough camera added. Scrub timeline or press Numpad-0 for camera view.")
    print("Render animation: Ctrl+F12")
