"""
Solar position calculator and Blender sun lamp configurator.

Computes sun altitude and azimuth for any location, date, and time,
then applies it to a Blender Sun lamp. Uses the standard solar position
algorithm (Spencer, 1971) with no external dependencies beyond math.

Usage (standalone):
    python src/sun_position.py --lat 35.5 --lon -80.0 --month 6 --day 21 --hour 14

Usage (Blender headless):
    blender --background model.glb --python src/sun_position.py -- \
        --lat 35.5 --lon -80.0 --month 6 --day 21 --hour 14 --north-offset 0

Coordinates:
    Azimuth 0 = North (plan +Y), measured clockwise.
    Altitude 0 = horizon, 90 = zenith.
    north_offset_deg rotates the entire building relative to true north.
"""

import math
import json
import sys
import os
import argparse


def day_of_year(month: int, day: int) -> int:
    """Day of year (1-365) for non-leap year."""
    days_in_month = [0, 31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    return sum(days_in_month[:month]) + day


def solar_position(lat_deg: float, lon_deg: float, month: int, day: int,
                   hour_local: float, utc_offset: float = -5.0):
    """
    Compute solar altitude and azimuth angles.

    Args:
        lat_deg: Latitude in degrees (positive north)
        lon_deg: Longitude in degrees (positive east)
        month: Month (1-12)
        day: Day of month
        hour_local: Local time in hours (e.g., 14.5 = 2:30 PM)
        utc_offset: Hours from UTC (EST = -5, EDT = -4)

    Returns:
        (altitude_deg, azimuth_deg) where azimuth 0 = north, clockwise
    """
    doy = day_of_year(month, day)
    lat = math.radians(lat_deg)

    # Solar declination (Spencer approximation)
    B = math.radians((360 / 365) * (doy - 81))
    declination = math.radians(23.45) * math.sin(B)

    # Equation of time (minutes)
    B2 = math.radians((360 / 365) * (doy - 1))
    eot = 229.18 * (0.000075 + 0.001868 * math.cos(B2) -
                     0.032077 * math.sin(B2) -
                     0.014615 * math.cos(2 * B2) -
                     0.04089 * math.sin(2 * B2))

    # Solar time
    hour_utc = hour_local - utc_offset
    solar_time = hour_utc + (lon_deg / 15.0) + (eot / 60.0)
    hour_angle = math.radians((solar_time - 12.0) * 15.0)

    # Altitude
    sin_alt = (math.sin(lat) * math.sin(declination) +
               math.cos(lat) * math.cos(declination) * math.cos(hour_angle))
    altitude = math.asin(max(-1, min(1, sin_alt)))

    # Azimuth (measured from south, convert to from-north clockwise)
    cos_az = ((math.sin(declination) - math.sin(lat) * math.sin(altitude)) /
              (math.cos(lat) * math.cos(altitude) + 1e-10))
    cos_az = max(-1, min(1, cos_az))
    azimuth = math.acos(cos_az)

    if hour_angle > 0:
        azimuth = 2 * math.pi - azimuth
    # Convert from south-referenced to north-referenced clockwise
    azimuth = (azimuth + math.pi) % (2 * math.pi)

    return math.degrees(altitude), math.degrees(azimuth)


def utc_offset_for_month(month: int) -> float:
    """EST (-5) or EDT (-4) based on rough DST dates."""
    if 3 <= month <= 10:
        return -4.0  # EDT
    return -5.0  # EST


def sun_direction_vector(altitude_deg: float, azimuth_deg: float,
                         north_offset_deg: float = 0.0):
    """
    Convert solar altitude/azimuth to a Blender direction vector.

    In Blender: +X = East, +Y = North, +Z = Up.
    Azimuth 0 = North, clockwise.
    The returned vector points FROM the sun TOWARD the ground (for lamp direction).
    """
    alt = math.radians(altitude_deg)
    az = math.radians(azimuth_deg + north_offset_deg)

    # Direction FROM sun TO origin
    dx = -math.sin(az) * math.cos(alt)
    dy = -math.cos(az) * math.cos(alt)
    dz = -math.sin(alt)
    return (dx, dy, dz)


def sun_rotation_euler(altitude_deg: float, azimuth_deg: float,
                       north_offset_deg: float = 0.0):
    """
    Compute Euler rotation (XYZ) for a Blender Sun lamp.

    Blender Sun lamps point along their local -Z axis by default.
    """
    alt = math.radians(altitude_deg)
    az = math.radians(azimuth_deg + north_offset_deg)

    # Rotation: first rotate around X to set altitude, then around Z for azimuth
    rot_x = math.pi / 2 - alt  # tilt from zenith
    rot_y = 0.0
    rot_z = -az  # azimuth rotation (negative for CW in Blender's CCW Z-rotation)

    return (rot_x, rot_y, rot_z)


def apply_sun_in_blender(altitude_deg: float, azimuth_deg: float,
                         north_offset_deg: float = 0.0,
                         energy: float = 5.0, color_temp_k: float = 5500.0):
    """Apply sun position to a Blender Sun lamp (creates one if missing)."""
    import bpy

    # Find or create sun lamp
    sun = None
    for obj in bpy.data.objects:
        if obj.type == 'LIGHT' and obj.data.type == 'SUN':
            sun = obj
            break

    if sun is None:
        light_data = bpy.data.lights.new(name="Sun", type='SUN')
        sun = bpy.data.objects.new("Sun", light_data)
        bpy.context.collection.objects.link(sun)

    # Set rotation
    rot = sun_rotation_euler(altitude_deg, azimuth_deg, north_offset_deg)
    sun.rotation_euler = rot

    # Set energy and color temperature
    sun.data.energy = energy

    # Approximate color from temperature (simplified blackbody)
    if color_temp_k <= 3500:
        sun.data.color = (1.0, 0.75, 0.45)  # warm golden
    elif color_temp_k <= 5000:
        sun.data.color = (1.0, 0.93, 0.84)  # warm white
    elif color_temp_k <= 6500:
        sun.data.color = (1.0, 0.98, 0.95)  # neutral daylight
    else:
        sun.data.color = (0.85, 0.92, 1.0)  # cool overcast

    # Adjust energy based on altitude (lower sun = less intense)
    if altitude_deg < 10:
        sun.data.energy = energy * 0.3
    elif altitude_deg < 25:
        sun.data.energy = energy * 0.6

    sun.data.angle = math.radians(0.545)  # realistic sun disc angle

    return sun


def main():
    # Check if running inside Blender
    in_blender = False
    try:
        import bpy
        in_blender = True
    except ImportError:
        pass

    # Parse args (handle Blender's -- separator)
    argv = sys.argv
    if "--" in argv:
        argv = argv[argv.index("--") + 1:]
    else:
        argv = argv[1:]

    parser = argparse.ArgumentParser(description="Solar position calculator")
    parser.add_argument("--lat", type=float, default=35.5,
                        help="Latitude (default: 35.5 = central NC Triad)")
    parser.add_argument("--lon", type=float, default=-80.0,
                        help="Longitude (default: -80.0 = central NC Triad)")
    parser.add_argument("--month", type=int, default=6)
    parser.add_argument("--day", type=int, default=21)
    parser.add_argument("--hour", type=float, default=14.0,
                        help="Local time in hours (e.g. 14.5 = 2:30 PM)")
    parser.add_argument("--north-offset", type=float, default=0.0,
                        help="Building rotation from true north (degrees CW)")
    parser.add_argument("--energy", type=float, default=5.0)
    parser.add_argument("--glb", type=str, default=None,
                        help="GLB file to import before setting sun (Blender only)")

    args = parser.parse_args(argv)

    utc_off = utc_offset_for_month(args.month)
    alt, az = solar_position(args.lat, args.lon, args.month, args.day,
                             args.hour, utc_off)

    print(f"Location: {args.lat}°N, {args.lon}°E")
    print(f"Date: {args.month}/{args.day}, Time: {args.hour:.1f}h local (UTC{utc_off:+.0f})")
    print(f"Solar altitude: {alt:.1f}°")
    print(f"Solar azimuth:  {az:.1f}° (from north, clockwise)")

    if alt < 0:
        print("  (Sun is below the horizon)")

    if in_blender:
        if args.glb:
            bpy.ops.import_scene.gltf(filepath=args.glb)
        sun = apply_sun_in_blender(alt, az, args.north_offset,
                                   energy=args.energy)
        print(f"Blender Sun lamp set: rotation={[round(math.degrees(r),1) for r in sun.rotation_euler]}")


if __name__ == "__main__":
    main()
