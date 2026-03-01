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


def generate_image(prompt, size="1024x1024", model="gemini-2.5-flash-image", output_path=None):
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
        response_modalities=["TEXT", "IMAGE"],
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


def generate_texture(material_name, normal=False, size="2048x2048", model="gemini-2.5-flash-image", output_path=None):
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


def edit_image(image_path, instruction, model="gemini-2.5-flash-image", output_path=None):
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


def refine_prompt(raw_prompt, context="architectural visualization texture"):
    """Use Gemini to rewrite a raw prompt into an optimized image generation prompt.

    Gemini writes the best prompts for its own image models. This function
    takes a rough idea and returns a polished, detailed prompt.

    Args:
        raw_prompt: Your rough description (e.g., "concrete wall texture")
        context: What kind of image (texture, concept art, etc.)

    Returns:
        Refined prompt string.
    """
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=get_api_key())

    meta_prompt = f"""You are an expert at writing prompts for AI image generation models.
Rewrite the following rough idea into a detailed, specific prompt optimized for
generating a high-quality {context} image.

Include specifics about:
- Exact visual qualities (lighting, angle, resolution)
- Material properties if applicable (finish, texture, color tone)
- Technical requirements (seamless/tileable if texture, perspective if scene)
- What to AVOID (no text, no watermarks, no borders, etc.)

Raw idea: {raw_prompt}

Return ONLY the refined prompt text, nothing else."""

    response = client.models.generate_content(
        model="gemini-2.0-flash-exp",
        contents=meta_prompt,
    )
    refined = response.text.strip()
    print(f"Refined prompt:\n{refined}")
    return refined


def generate_seamless_texture(material_name, size="2048x2048",
                               model="gemini-2.5-flash-preview-image-generation",
                               output_path=None):
    """Generate a seamless tileable texture using the offset-and-fix trick.

    Steps:
    1. Generate initial texture
    2. Roll image 50% in X and Y (moves seams to center)
    3. Use Gemini edit to fix visible seams in the center
    4. Save final seamless result

    Args:
        material_name: e.g., "polished concrete", "walnut hardwood"
        size: Output resolution.
        model: Gemini model to use.
        output_path: Where to save the final seamless texture.

    Returns:
        Path to saved seamless texture.
    """
    from PIL import Image
    import io

    if not output_path:
        safe_name = material_name.lower().replace(" ", "_").replace("/", "_")
        output_path = f"assets/textures/{safe_name}_basecolor_seamless.png"

    # Step 1: Generate initial texture
    print(f"Step 1/3: Generating initial {material_name} texture...")
    initial_bytes = generate_texture(material_name, size=size, model=model)

    # If generate_texture returned a path (it saved the file), read it back
    if isinstance(initial_bytes, str):
        with open(initial_bytes, "rb") as f:
            initial_bytes = f.read()

    # Step 2: Roll image 50% in X and Y to expose seams
    print("Step 2/3: Rolling image to expose seams...")
    img = Image.open(io.BytesIO(initial_bytes))
    w, h = img.size
    # Roll by half in both axes
    rolled = Image.new(img.mode, (w, h))
    rolled.paste(img.crop((w//2, h//2, w, h)), (0, 0))
    rolled.paste(img.crop((0, h//2, w//2, h)), (w//2, 0))
    rolled.paste(img.crop((w//2, 0, w, h//2)), (0, h//2))
    rolled.paste(img.crop((0, 0, w//2, h//2)), (w//2, h//2))

    # Save rolled version temporarily
    rolled_path = output_path.rsplit(".", 1)[0] + "_rolled.png"
    os.makedirs(os.path.dirname(rolled_path) or ".", exist_ok=True)
    rolled.save(rolled_path)

    # Step 3: Fix seams via Gemini edit
    print("Step 3/3: Fixing seams with AI editing...")
    try:
        edit_image(
            rolled_path,
            "Fix the visible seams (cross-shaped lines) in the center of this texture. "
            "Make the texture look uniform and continuous. Keep the same material appearance. "
            "Do not change the overall color or style.",
            model=model,
            output_path=output_path,
        )
    except Exception as e:
        print(f"Warning: Seam fix failed ({e}), using rolled version as fallback")
        rolled.save(output_path)

    # Clean up temp file
    if os.path.exists(rolled_path):
        os.remove(rolled_path)

    print(f"Seamless texture saved: {output_path}")
    return output_path


def main():
    parser = argparse.ArgumentParser(description="Gemini Image Generation for Architecture")
    sub = parser.add_subparsers(dest="command")

    # Generate free-form image
    gen = sub.add_parser("generate", help="Generate an image from a text prompt")
    gen.add_argument("--prompt", required=True, help="Text description")
    gen.add_argument("--size", default="1024x1024", help="Resolution (e.g., 1024x1024, 2048x2048)")
    gen.add_argument("--model", default="gemini-2.5-flash-image", help="Gemini model ID")
    gen.add_argument("--output", "-o", required=True, help="Output file path")

    # Generate tileable texture
    tex = sub.add_parser("texture", help="Generate a seamless tileable texture")
    tex.add_argument("--material", required=True, help="Material name (e.g., 'polished concrete')")
    tex.add_argument("--normal", action="store_true", help="Generate normal map instead of base color")
    tex.add_argument("--size", default="2048x2048", help="Resolution")
    tex.add_argument("--model", default="gemini-2.5-flash-image")
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
    ed.add_argument("--model", default="gemini-2.5-flash-image")
    ed.add_argument("--output", "-o", help="Output path (defaults to input_edited.ext)")

    # Refine a prompt using Gemini
    ref = sub.add_parser("refine", help="Use Gemini to optimize an image generation prompt")
    ref.add_argument("--prompt", required=True, help="Raw prompt idea")
    ref.add_argument("--context", default="architectural visualization texture",
                     help="Type of image (texture, concept art, interior, etc.)")

    # Generate seamless tileable texture (offset trick)
    seam = sub.add_parser("seamless", help="Generate a seamless tileable texture (3-step offset trick)")
    seam.add_argument("--material", required=True, help="Material name (e.g., 'polished concrete')")
    seam.add_argument("--size", default="2048x2048", help="Resolution")
    seam.add_argument("--model", default="gemini-2.5-flash-image")
    seam.add_argument("--output", "-o", help="Output file path (auto-named if omitted)")

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
    elif args.command == "refine":
        refine_prompt(args.prompt, context=args.context)
    elif args.command == "seamless":
        generate_seamless_texture(args.material, size=args.size, model=args.model,
                                  output_path=args.output)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
