#!/usr/bin/env python3
"""Generate all textures for the Exploded Hexagon Home project.

Uses the Gemini image generation helper to create architectural textures.

Usage:
    python src/generate_textures.py              # Generate all textures
    python src/generate_textures.py --only marble # Generate just one
    python src/generate_textures.py --list        # List available textures
"""

import argparse
import os
import sys
import time

# Import the Gemini image generation helper
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '.github', 'skills', 'architecture-3d'))
from gemini_image_gen import generate_image

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
TEXTURE_DIR = os.path.join(PROJECT_ROOT, 'assets', 'textures')
MODEL = "gemini-2.5-flash-preview-image-generation"

# Each texture: (short_name, filename, size, prompt)
TEXTURES = [
    (
        "marble",
        "atrium_marble_star_basecolor.png",
        "2048x2048",
        (
            "A polished white Carrara marble floor tile with an inscribed six-pointed "
            "Star of David (hexagram) made of deep blue mosaic tiles. The star has thin "
            "gold metallic lines outlining its edges. Top-down overhead view, perfectly "
            "square, photorealistic architectural visualization quality. The white marble "
            "has subtle grey veining. Clean, even lighting with no shadows. "
            "No text, no watermarks, no labels."
        ),
    ),
    (
        "driveway",
        "driveway_basecolor.png",
        "2048x2048",
        (
            "Seamless tileable brushed broom-finished concrete driveway surface texture. "
            "Slightly weathered with fine parallel brush strokes. Light grey concrete with "
            "subtle color variation and minor surface wear. Top-down overhead view, "
            "photorealistic, even diffuse lighting, no shadows. Suitable for PBR "
            "architectural rendering. No text, no watermarks."
        ),
    ),
    (
        "concrete",
        "smooth_concrete_basecolor.png",
        "2048x2048",
        (
            "Seamless tileable smooth poured concrete wall surface texture. Subtle "
            "formwork lines and minor bug holes typical of board-formed concrete. "
            "Medium grey tone with natural color variation. Flat front-facing view, "
            "photorealistic, even diffuse lighting, no directional shadows. Suitable "
            "for retaining walls and exterior walls in architectural visualization. "
            "No text, no watermarks."
        ),
    ),
    (
        "plantwall",
        "plant_wall_basecolor.png",
        "2048x2048",
        (
            "A lush vertical green living wall installation, densely planted with "
            "tropical plants, ferns, pothos, philodendrons, and soft moss patches. "
            "Rich variety of green shades from deep emerald to bright lime. Front-facing "
            "view of the entire wall surface. Professional interior living wall design, "
            "photorealistic quality. Even soft lighting, no harsh shadows. "
            "No text, no watermarks, no visible mounting hardware."
        ),
    ),
    (
        "accent",
        "accent_wall_bedroom_basecolor.png",
        "2048x2048",
        (
            "An elegant futuristic high-tech accent wall panel design for a luxury "
            "penthouse bedroom headboard wall. Dark charcoal and matte black materials "
            "with subtle geometric patterns. Thin integrated ambient LED lighting strips "
            "in warm white creating soft glowing lines. Brushed dark metal and carbon "
            "fiber accents. Front-facing view, photorealistic architectural interior "
            "visualization. Sophisticated, minimal, sci-fi luxury aesthetic. "
            "No text, no watermarks."
        ),
    ),
    (
        "rug",
        "luxury_rug_basecolor.png",
        "2048x2048",
        (
            "A beautiful colorful luxury area rug viewed from directly above, top-down "
            "view. Rich jewel-toned Persian or modern geometric design with deep royal "
            "blue, antique gold, burgundy red, and emerald green. Intricate patterns "
            "with fine detail. Rectangular shape on a transparent or neutral background. "
            "Photorealistic textile texture with visible pile and weave. "
            "No text, no watermarks."
        ),
    ),
    (
        "sky",
        "sky_sphere_basecolor.png",
        "2048x2048",
        (
            "A panoramic sky texture suitable for a sky sphere or sky dome in 3D "
            "rendering. Dramatic blue sky with beautiful white and soft grey cumulus "
            "clouds. Gradient from deep azure blue at the zenith to lighter blue and "
            "warm white near the horizon. Wide panoramic aspect, bright daylight "
            "conditions. Photorealistic, no ground visible, no sun disc. Suitable for "
            "wrapping around a sphere for architectural exterior visualization. "
            "No text, no watermarks."
        ),
    ),
    (
        "lawn",
        "lawn_basecolor.png",
        "2048x2048",
        (
            "Seamless tileable lush green grass lawn texture, top-down overhead view. "
            "Natural looking well-maintained residential lawn with slight variation in "
            "blade direction and subtle color differences between individual grass "
            "blades. Medium green color, photorealistic quality. Even diffuse lighting, "
            "no shadows, no bare patches. Suitable for PBR architectural landscape "
            "rendering. No text, no watermarks."
        ),
    ),
]


def check_api_key():
    """Check that a Gemini API key is available."""
    key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not key:
        print("ERROR: No Gemini API key found.")
        print("Set GEMINI_API_KEY or GOOGLE_API_KEY environment variable.")
        print("Get a key from https://aistudio.google.com/apikey")
        sys.exit(1)
    return key


def generate_one(name, filename, size, prompt):
    """Generate a single texture."""
    output_path = os.path.join(TEXTURE_DIR, filename)
    if os.path.exists(output_path):
        print(f"  [skip] {filename} already exists. Delete it to regenerate.")
        return

    print(f"  Generating {filename} ({size}) ...")
    start = time.time()
    generate_image(prompt, size=size, model=MODEL, output_path=output_path)
    elapsed = time.time() - start
    print(f"  Done in {elapsed:.1f}s\n")


def main():
    parser = argparse.ArgumentParser(
        description="Generate textures for the Exploded Hexagon Home project."
    )
    parser.add_argument(
        "--only",
        type=str,
        default=None,
        help="Generate only this texture (by short name, e.g. 'marble', 'sky').",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List available texture names and exit.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing textures instead of skipping.",
    )
    args = parser.parse_args()

    # List mode
    if args.list:
        print("Available textures:")
        for name, filename, size, _ in TEXTURES:
            status = "exists" if os.path.exists(os.path.join(TEXTURE_DIR, filename)) else "missing"
            print(f"  {name:12s}  {filename:45s}  {size}  [{status}]")
        return

    check_api_key()
    os.makedirs(TEXTURE_DIR, exist_ok=True)

    # Filter to requested texture
    if args.only:
        matches = [t for t in TEXTURES if t[0] == args.only]
        if not matches:
            valid = ", ".join(t[0] for t in TEXTURES)
            print(f"ERROR: Unknown texture '{args.only}'. Valid names: {valid}")
            sys.exit(1)
        targets = matches
    else:
        targets = TEXTURES

    total = len(targets)
    print(f"Generating {total} texture(s) into {TEXTURE_DIR}\n")

    for i, (name, filename, size, prompt) in enumerate(targets, 1):
        print(f"[{i}/{total}] {name}")

        if args.force:
            output_path = os.path.join(TEXTURE_DIR, filename)
            if os.path.exists(output_path):
                os.remove(output_path)

        generate_one(name, filename, size, prompt)

    print("All done.")


if __name__ == "__main__":
    main()
