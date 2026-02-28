"""
Download free CC0 3D plant assets from Poly Haven for the atrium garden.

Usage:
  python src/download_assets.py              # download all curated plants
  python src/download_assets.py --list       # list available plant slugs
  python src/download_assets.py --slug potted_plant_04  # download one specific

Assets are saved to assets/models/plants/ in GLTF format (main .gltf + textures + bin).
All Poly Haven assets are CC0 (public domain).
"""

import argparse
import json
import os
import sys
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import URLError

ASSETS_DIR = Path(__file__).parent.parent / "assets" / "models" / "plants"

# Curated list: tropical/indoor plants suitable for a luxury atrium garden
CURATED_PLANTS = [
    "potted_plant_01",         # terracotta pot plant
    "potted_plant_02",         # medium potted plant
    "potted_plant_04",         # cactus/aloe/succulent
    "pachira_aquatica_01",     # money tree (tropical)
    "calathea_orbifolia_01",   # tropical indoor plant
    "fern_02",                 # jungle fern
    "shrub_01",                # leafy foliage shrub
    "shrub_04",                # bush
    "island_tree_01",          # tropical tree
    "island_tree_02",          # tropical tree variant
    "moss_01",                 # ground cover
]

POLYHAVEN_ASSETS_API = "https://api.polyhaven.com/assets?t=models"
POLYHAVEN_FILES_API = "https://api.polyhaven.com/files/{slug}"
PREFERRED_RES = "1k"  # 1k textures are small enough for fast viewport


def _api_get(url: str) -> dict | None:
    try:
        req = Request(url, headers={"User-Agent": "ExplodedHexagonHome/1.0"})
        return json.loads(urlopen(req, timeout=20).read())
    except URLError as e:
        print(f"  API error: {e}")
        return None


def list_available_plants():
    """Fetch and print all plant model slugs from Poly Haven API."""
    print("Fetching plant models from Poly Haven...")
    data = _api_get(POLYHAVEN_ASSETS_API)
    if not data:
        return []
    plant_slugs = [k for k, v in data.items()
                   if any(t in v.get("tags", []) for t in
                          ["plant", "potted", "tree", "fern", "tropical", "shrub", "bush"])]
    print(f"\nFound {len(plant_slugs)} plant-related models:")
    for slug in sorted(plant_slugs):
        info = data[slug]
        tags = ", ".join(info.get("tags", [])[:5])
        print(f"  {slug:35s}  tags: {tags}")
    return plant_slugs


def download_plant(slug: str, resolution: str = PREFERRED_RES, force: bool = False) -> Path | None:
    """Download a plant model (GLTF + textures + bin) from Poly Haven."""
    plant_dir = ASSETS_DIR / slug
    marker = plant_dir / ".downloaded"

    if marker.exists() and not force:
        print(f"  Already downloaded: {slug}")
        return plant_dir

    # Get file manifest from API
    files_data = _api_get(POLYHAVEN_FILES_API.format(slug=slug))
    if not files_data or "gltf" not in files_data:
        print(f"  No GLTF format available for: {slug}")
        return None

    gltf_data = files_data["gltf"]
    # Pick best available resolution
    res = resolution
    if res not in gltf_data:
        for fallback in ["2k", "4k", "1k"]:
            if fallback in gltf_data:
                res = fallback
                break
        else:
            print(f"  No suitable resolution for: {slug}")
            return None

    gltf_info = gltf_data[res]["gltf"]
    main_url = gltf_info["url"]
    includes = gltf_info.get("include", {})

    plant_dir.mkdir(parents=True, exist_ok=True)
    total_size = 0

    # Download main .gltf file
    main_file = plant_dir / f"{slug}_{res}.gltf"
    try:
        req = Request(main_url, headers={"User-Agent": "ExplodedHexagonHome/1.0"})
        data = urlopen(req, timeout=60).read()
        main_file.write_bytes(data)
        total_size += len(data)
    except URLError as e:
        print(f"  Failed to download main GLTF: {e}")
        return None

    # Download included files (textures, bin)
    for rel_path, file_info in includes.items():
        out_file = plant_dir / rel_path
        out_file.parent.mkdir(parents=True, exist_ok=True)
        try:
            req = Request(file_info["url"], headers={"User-Agent": "ExplodedHexagonHome/1.0"})
            data = urlopen(req, timeout=60).read()
            out_file.write_bytes(data)
            total_size += len(data)
        except URLError as e:
            print(f"  Warning: failed to download {rel_path}: {e}")

    total_mb = total_size / (1024 * 1024)
    marker.write_text(f"resolution={res}\nfiles={len(includes) + 1}\nsize_mb={total_mb:.1f}\n")
    print(f"  Downloaded: {slug} ({res}, {total_mb:.1f} MB, {len(includes) + 1} files)")
    return plant_dir


def download_all_curated(force: bool = False):
    """Download all curated plants."""
    print(f"Downloading {len(CURATED_PLANTS)} curated plant models to {ASSETS_DIR}/")
    print("(All assets are CC0 public domain from polyhaven.com)\n")

    results = []
    for slug in CURATED_PLANTS:
        path = download_plant(slug, force=force)
        if path:
            results.append(path)

    print(f"\n{len(results)}/{len(CURATED_PLANTS)} plants downloaded successfully.")
    print(f"Assets directory: {ASSETS_DIR}")

    # Print import instructions
    if results:
        print("\nTo use in Blender:")
        print("  bpy.ops.import_scene.gltf(filepath=str(plant_dir / '{slug}_1k.gltf'))")
    return results


def main():
    parser = argparse.ArgumentParser(description="Download plant 3D assets from Poly Haven")
    parser.add_argument("--list", action="store_true", help="List available plant models")
    parser.add_argument("--slug", type=str, help="Download a specific model by slug")
    parser.add_argument("--force", action="store_true", help="Re-download even if file exists")
    parser.add_argument("--res", default=PREFERRED_RES, help="Texture resolution (1k, 2k, 4k)")
    args = parser.parse_args()

    if args.list:
        list_available_plants()
    elif args.slug:
        download_plant(args.slug, resolution=args.res, force=args.force)
    else:
        download_all_curated(args.force)


if __name__ == "__main__":
    main()
