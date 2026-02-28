"""
Gemini Image Generation Helper for Architecture 3D Skill.

Generates textures, concept art, and reference images using Google's Gemini API.
Requires GEMINI_API_KEY or GOOGLE_API_KEY environment variable.

Usage:
    python gemini_image_gen.py --prompt "seamless polished concrete texture" --output assets/textures/concrete_basecolor.png
    python gemini_image_gen.py --prompt "modern tropical atrium interior" --size 2048x2048 --output concept.png
    python gemini_image_gen.py --texture "walnut hardwood flooring" --output assets/textures/walnut_basecolor.png
    python gemini_image_gen.py --texture "polished concrete" --normal --output assets/textures/concrete_normal.png
"""

import argparse
import base64
import os
import sys


def get_api_key():
    """Get Gemini API key from environment."""
    key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not key:
        print("ERROR: Set GEMINI_API_KEY or GOOGLE_API_KEY environment variable.")
        print("Get a key from https://aistudio.google.com/apikey")
        sys.exit(1)
    return key


def generate_image(prompt, size="1024x1024", model="gemini-2.0-flash-exp", output_path=None):
    """Generate an image using the Gemini API.

    Args:
        prompt: Text description of the image to generate.
        size: Output resolution (e.g., "1024x1024", "2048x2048", "4096x4096").
              4K requires gemini-3-pro-image-preview model.
        model: Gemini model ID. Options:
            - "gemini-2.0-flash-exp": Fast, good quality (default)
            - "gemini-2.5-flash-preview-image-generation": Better quality
            - "gemini-3-pro-image-preview": Best quality, supports 4K
        output_path: File path to save the image. If None, returns bytes.

    Returns:
        Image bytes if output_path is None, else the output path.
    """
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=get_api_key())

    config = types.GenerateContentConfig(
        response_modalities=["IMAGE"],
    )

    response = client.models.generate_content(
        model=model,
        contents=prompt,
        config=config,
    )

    # Extract image data from response
    image_data = None
    for part in response.candidates[0].content.parts:
        if hasattr(part, 'inline_data') and part.inline_data:
            image_data = part.inline_data.data
            break

    if not image_data:
        print("ERROR: No image returned from Gemini API.")
        print("Response:", response.text if hasattr(response, 'text') else str(response))
        sys.exit(1)

    if output_path:
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        with open(output_path, "wb") as f:
            f.write(image_data)
        print(f"Saved: {output_path} ({len(image_data)} bytes)")
        return output_path
    return image_data


def generate_texture(material_name, normal=False, size="2048x2048", model="gemini-2.5-flash-preview-image-generation", output_path=None):
    """Generate a seamless tileable texture for architectural materials.

    Args:
        material_name: e.g., "polished concrete", "walnut hardwood", "limestone"
        normal: If True, generates a normal map instead of a base color map.
        size: Output resolution.
        model: Gemini model to use.
        output_path: Where to save.

    Returns:
        Path to saved file.
    """
    map_type = "normal map" if normal else "base color texture map"

    prompt = f"""Generate a seamless tileable {map_type} for {material_name}.
Requirements:
- Seamlessly tileable in both X and Y directions
- Photorealistic quality suitable for architectural visualization
- Even, diffuse lighting with no shadows or directional light
- No text, watermarks, or labels
- Square aspect ratio
- {"Surface relief detail encoded as RGB normals (128,128,255 = flat, variations show bumps/grooves)" if normal else "True-to-life colors and surface detail"}
- Suitable for PBR rendering in Blender Cycles"""

    if not output_path:
        safe_name = material_name.lower().replace(" ", "_").replace("/", "_")
        suffix = "normal" if normal else "basecolor"
        output_path = f"assets/textures/{safe_name}_{suffix}.png"

    return generate_image(prompt, size=size, model=model, output_path=output_path)


def generate_concept(description, style="architectural visualization", size="1024x1024", output_path=None):
    """Generate concept art or reference imagery.

    Args:
        description: What to visualize.
        style: Art style (e.g., "architectural visualization", "watercolor sketch").
        output_path: Where to save.
    """
    prompt = f"""{description}
Style: {style}
High quality, professional rendering. No text or watermarks."""

    if not output_path:
        output_path = "concept_art.png"

    return generate_image(prompt, size=size, output_path=output_path)


def edit_image(image_path, instruction, model="gemini-2.5-flash-preview-image-generation", output_path=None):
    """Edit an existing image with text instructions.

    Args:
        image_path: Path to the input image.
        instruction: What to change (e.g., "make the sky more blue", "add trees").
        output_path: Where to save the result.
    """
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=get_api_key())

    with open(image_path, "rb") as f:
        image_bytes = f.read()

    # Determine mime type
    ext = image_path.lower().rsplit(".", 1)[-1]
    mime = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg"}.get(ext, "image/png")

    response = client.models.generate_content(
        model=model,
        contents=[
            types.Part.from_bytes(data=image_bytes, mime_type=mime),
            instruction,
        ],
        config=types.GenerateContentConfig(
            response_modalities=["IMAGE"],
        ),
    )

    image_data = None
    for part in response.candidates[0].content.parts:
        if hasattr(part, 'inline_data') and part.inline_data:
            image_data = part.inline_data.data
            break

    if not image_data:
        print("ERROR: No edited image returned.")
        sys.exit(1)

    if not output_path:
        base, ext = os.path.splitext(image_path)
        output_path = f"{base}_edited{ext}"

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "wb") as f:
        f.write(image_data)
    print(f"Saved edited image: {output_path}")
    return output_path


def main():
    parser = argparse.ArgumentParser(description="Gemini Image Generation for Architecture")
    sub = parser.add_subparsers(dest="command")

    # Generate free-form image
    gen = sub.add_parser("generate", help="Generate an image from a text prompt")
    gen.add_argument("--prompt", required=True, help="Text description")
    gen.add_argument("--size", default="1024x1024", help="Resolution (e.g., 1024x1024, 2048x2048)")
    gen.add_argument("--model", default="gemini-2.0-flash-exp", help="Gemini model ID")
    gen.add_argument("--output", "-o", required=True, help="Output file path")

    # Generate tileable texture
    tex = sub.add_parser("texture", help="Generate a seamless tileable texture")
    tex.add_argument("--material", required=True, help="Material name (e.g., 'polished concrete')")
    tex.add_argument("--normal", action="store_true", help="Generate normal map instead of base color")
    tex.add_argument("--size", default="2048x2048", help="Resolution")
    tex.add_argument("--model", default="gemini-2.5-flash-preview-image-generation")
    tex.add_argument("--output", "-o", help="Output file path (auto-named if omitted)")

    # Generate concept art
    con = sub.add_parser("concept", help="Generate architectural concept art")
    con.add_argument("--description", required=True, help="What to visualize")
    con.add_argument("--style", default="architectural visualization")
    con.add_argument("--size", default="1024x1024")
    con.add_argument("--output", "-o", default="concept_art.png")

    # Edit existing image
    ed = sub.add_parser("edit", help="Edit an image with text instructions")
    ed.add_argument("--input", required=True, help="Input image path")
    ed.add_argument("--instruction", required=True, help="What to change")
    ed.add_argument("--model", default="gemini-2.5-flash-preview-image-generation")
    ed.add_argument("--output", "-o", help="Output path (defaults to input_edited.ext)")

    args = parser.parse_args()

    if args.command == "generate":
        generate_image(args.prompt, size=args.size, model=args.model, output_path=args.output)
    elif args.command == "texture":
        generate_texture(args.material, normal=args.normal, size=args.size,
                        model=args.model, output_path=args.output)
    elif args.command == "concept":
        generate_concept(args.description, style=args.style, size=args.size,
                        output_path=args.output)
    elif args.command == "edit":
        edit_image(args.input, args.instruction, model=args.model, output_path=args.output)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
