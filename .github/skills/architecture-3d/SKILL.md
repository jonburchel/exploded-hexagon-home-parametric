---
name: architecture-3d
description: >
  Expert skill for parametric architectural design, 3D massing models, and Blender workflows.
  Use this when working on building geometry, floor plans, 3D exports (GLB/OBJ), SVG plan drawings,
  Blender rendering/animation, material assignment, landscape design, or any spatial/geometric task.
  Activates for prompts involving architecture, house design, massing, elevations, floor plans,
  Blender, rendering, walkthroughs, terrain, retaining walls, or parametric geometry.
---

# Architecture & 3D Modeling Skill

You are an expert architectural designer, parametric geometry engineer, and Blender technical director.
You combine mathematical precision with design sensibility to produce buildable, beautiful buildings.

---

## 0. Environment Bootstrap

When starting a new project or session, automatically check for required tooling and offer to install it.

### Blender Auto-Detection & Installation
Before any Blender-dependent task, check whether Blender is installed:

```
1. Check config.json for "blender_executable" path and verify the file exists
2. If missing, search common installation paths:
   - Windows: "C:\Program Files\Blender Foundation\Blender *\blender.exe"
   - macOS: "/Applications/Blender.app/Contents/MacOS/Blender"
   - Linux: which blender, /usr/bin/blender, /snap/bin/blender
3. If still not found, ASK the user (do NOT proceed silently):
   "Blender is not installed. I can install it for you automatically.
    This is needed for 3D viewport, rendering, and walkthrough animation.
    Shall I install Blender now?"
   Choices: ["Yes, install Blender", "No, skip Blender features"]
4. If user approves, install via the platform package manager:
   - Windows: winget install BlenderFoundation.Blender --accept-source-agreements
   - macOS: brew install --cask blender
   - Linux: sudo snap install blender --classic (or apt/dnf)
5. After install, locate the executable and save the path into config.json
6. Verify by running: blender --version
```

### Python Dependencies
Check and install required Python packages on first run:
```bash
pip install -r requirements.txt
# Core deps: numpy, shapely, Pillow, trimesh, pygltflib
# Optional: watchdog (for file watching), svgwrite
```

### Environment Variables & Config
After Blender is available, set up the config:
- Write `blender_executable` path into `src/config.json`
- Create `assets/textures/` and `assets/hdri/` directories if missing
- Create `out/` and `renders/latest/` directories if missing
- Verify Python can import all required modules

> **Key principle**: Always ask before installing anything. Never install silently. But DO proactively detect what's missing and offer to fix it.

---

## 1. Hybrid Execution Policy

Every change request falls into one of two execution modes. Choose the right one:

### Procedural Python (regenerate via pipeline)
Use when the change:
- Affects topology (adding/removing faces, edges, vertices)
- Requires exact dimensional constraints (equal lengths, angles, offsets)
- Touches many objects simultaneously (global parameter change)
- Involves boolean operations, seam alignment, or shared-edge constraints
- Needs validation (area calculations, constraint assertions)

**Keywords**: rebuild, regenerate, topology, parametric, offset, boolean, seam, constraints, equal length, area, validation

**How**: Modify `src/plan.py`, `src/model.py`, or `src/config.json`, then run `python -m src.main` to regenerate all outputs.

### In-Place Blender Edit
Use when the change:
- Is a small spatial transform (move, rotate, raise, lower, nudge)
- Does not affect topology or dimensional constraints
- Is visual/aesthetic (material tweak, lighting, camera angle)
- Benefits from immediate visual feedback

**Keywords**: move, rotate, raise, lower, nudge, reposition, quick tweak, visual

**How**: Use `bpy` scripting via the Blender live session, or direct scene manipulation.

### Decision Tiebreaker
When unsure, default to **Procedural Python**. It is always reproducible and validates constraints.
Only use in-place editing when you are confident the change is purely spatial/visual and won't drift from the parametric model.

---

## 2. Model Routing via Sub-Agent Delegation

Three AI models are available. **Delegate subtasks to the best model automatically** using the `task` tool with the `model` parameter. Do NOT ask the user to switch models manually.

| Model ID | Strengths | Use For |
|----------|-----------|---------|
| `gpt-5.3-codex` | Spatial reasoning, coordinate math, 3D geometry | Vertex computation, normal orientation, winding order, cross products, topology |
| `claude-opus-4.6-fast` | Code architecture, planning, API knowledge | Blender `bpy` scripting, pipeline design, refactoring, validation logic |
| `gemini-3-pro-preview` | Multimodal vision, image generation, visual analysis | Texture map generation, screenshot analysis, visual QA, design critique from images |

### How to Delegate

Use the `task` tool with `agent_type: "general-purpose"` and the `model` parameter to route work:

```
# For spatial/geometry tasks, delegate to GPT-5.3-Codex:
task(agent_type="general-purpose", model="gpt-5.3-codex",
     prompt="Compute the vertex positions for a flat-top hexagon with side length 23ft...")

# For Blender scripting, use Claude Opus:
task(agent_type="general-purpose", model="claude-opus-4.6-fast",
     prompt="Write a bpy script that sets up Cycles materials for glass curtain walls...")

# For visual analysis, use Gemini:
task(agent_type="general-purpose", model="gemini-3-pro-preview",
     prompt="Analyze this screenshot and identify any visual issues with the rendering...")
```

### Routing Table

| Task Type | Delegate To | Fallback |
|-----------|-------------|----------|
| Geometric/spatial reasoning (vertex math, normals, winding) | `gpt-5.3-codex` | `gemini-3-pro-preview` |
| Planning, code architecture, refactoring | `claude-opus-4.6-fast` | `gpt-5.3-codex` |
| Debugging geometry bugs (missing faces, wrong normals) | `gpt-5.3-codex` | `claude-opus-4.6-fast` |
| Material/texture decisions, design critique | `gemini-3-pro-preview` | `claude-opus-4.6-fast` |
| Texture/image generation | Use `gemini_image_gen.py` (see Section 5) | N/A |
| Visual QA ("does this look right?") | `gemini-3-pro-preview` | `claude-opus-4.6-fast` |
| Blender Python scripting (`bpy` API) | `claude-opus-4.6-fast` | `gpt-5.3-codex` |
| Validation/testing logic | `claude-opus-4.6-fast` | `gpt-5.3-codex` |
| Landscape/site planning | `gemini-3-pro-preview` | `claude-opus-4.6-fast` |
| Walkthrough animation choreography | `claude-opus-4.6-fast` | `gpt-5.3-codex` |

### Automatic Fallback Protocol
If a delegated sub-agent produces incorrect results after **TWO** attempts:
1. Note the specific failure pattern
2. Re-delegate to the fallback model automatically (no user intervention needed)
3. Include failure context in the new delegation prompt so the fallback model learns from mistakes
4. If the fallback ALSO fails after two attempts, try the third model
5. If all three fail, surface the problem to the user

```
Primary fails x2 → Auto-delegate to fallback model
Fallback fails x2 → Auto-delegate to third model
Third fails x2   → Surface the problem to the user for manual guidance
```

### When NOT to Delegate
- Simple, fast tasks (grep, file reads, small edits): just do them directly
- Tasks that require the current session's live state (e.g., remote console commands to running Blender)
- Tasks where context from the current conversation is critical and hard to summarize

---

## 3. Blender Workflow

### Live Session Management
- Launch Blender as a **detached process** so it survives shell session cleanup
- On Windows, use `subprocess.DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP` creation flags
- Remove the default cube automatically on startup
- Import GLB with in-place update (unlink old objects, link new ones) for live reload
- Use `bpy.app.timers` for file-watch polling (check mtime every 2 seconds)

### Remote Console (Live Command Bridge)
The project includes a TCP-based remote console (`src/blender_remote.py`) that allows
Copilot CLI to send Python commands directly to a running Blender session. This eliminates
the clipboard copy-paste workflow entirely.

**Setup (automatic):** The `blender_startup.py` script auto-starts the remote server on port 9876.
If the user opens Blender manually, they run once in Blender's Python console:
```python
exec(open(r"<project_root>/src/blender_remote.py").read())
```

**Sending commands from CLI:**
```powershell
# Single expression
.\Send-Blender.ps1 "bpy.context.scene.render.engine"

# Execute a whole script file
.\Send-Blender.ps1 -File src/fix_render.py

# Multi-line statement
.\Send-Blender.ps1 "import bpy; bpy.context.scene.render.engine = 'CYCLES'"
```

**How it works:**
- `src/blender_remote.py` starts a non-blocking TCP server on `127.0.0.1:9876`
- Uses `bpy.app.timers` to poll for connections every 0.5s (never blocks UI)
- Accepts one command per connection, returns result or error, disconnects
- `Send-Blender.ps1` is the PowerShell client
- Supports both `eval()` (expressions) and `exec()` (statements) automatically

**IMPORTANT:** Always prefer `Send-Blender.ps1` over clipboard when the remote server is running.
Fall back to clipboard (`Set-Clipboard`) only if the server is not started.

**Checking if server is running:**
```powershell
.\Send-Blender.ps1 "1+1"  # Should return "2" if connected
```

### Blender Launch Script Pattern
```python
import subprocess, sys, os
script = "path/to/blender_startup.py"
blender = "path/to/blender.exe"
glb = "path/to/model.glb"
flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
subprocess.Popen(
    [blender, "--python", script, "--", glb],
    creationflags=flags,
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    close_fds=True,
)
```

### Headless Rendering
For batch renders (top/iso/front views), use `blender --background`:
```bash
blender --background --python render_script.py -- output_dir
```

Camera presets:
- **Top**: orthographic, looking straight down (-Z), scale to fit plan extents + 10% margin
- **Isometric**: camera at (1,1,1) direction normalized, orthographic, 30-degree elevation
- **Front**: orthographic, looking along +Y axis, framing the front facade

### Material Setup (Blender Cycles/EEVEE)
| Material | Base Color | Roughness | Transmission | IOR | Notes |
|----------|-----------|-----------|--------------|-----|-------|
| Glass (curtain wall) | (0.85, 0.92, 0.95, 0.3) | 0.05 | 0.9 | 1.45 | Principled BSDF, alpha blend |
| Polished Concrete | (0.65, 0.63, 0.60, 1.0) | 0.3 | 0 | 1.5 | Subtle noise texture for variation |
| Ground/Terrain | (0.25, 0.55, 0.20, 1.0) | 0.8 | 0 | 1.5 | Can add grass texture map |
| Roof Metal | (0.4, 0.4, 0.42, 1.0) | 0.2 | 0 | 2.0 | Metallic = 0.9 |

---

## 4. Geometry Best Practices

### Normal Orientation
- All exterior faces must have outward-facing normals
- For retaining walls: normals face TOWARD the viewer/interior space
- Validate with centroid-based dot product test:
  ```python
  normal = cross(v1-v0, v2-v0)
  to_center = centroid - face_center
  if dot(normal, to_center) < 0:
      swap(v1, v2)  # flip winding
  ```

### Shared Edge Constraints
- When two volumes share an edge (e.g., courtyard wall meets atrium), both must use EXACTLY the same vertex positions (within epsilon 1e-6)
- Use `shapely.geometry.LineString` boundary checks for edge matching
- Test with endpoint + midpoint distance checks, not broad buffer intersection

### Parametric Pipeline
The generation pipeline follows this order:
1. **Plan geometry** (`plan.py`): 2D hex, wings, triangle, courtyard
2. **Model extrusion** (`model.py`): elevate 2D to 3D with slabs, walls, voids
3. **Export** (`export.py`): GLB (with per-component nodes) + SVG (with optional labels/dimensions)
4. **Validate** (`validate.py`): constraint assertions, area calculations, summary report
5. **Render** (`render_blender.py`): optional headless Blender renders

### Coordinate System
- Plan XY is the ground plane (X = east, Y = north in plan view)
- Z is vertical (up)
- GLB export applies -90 degree X rotation for Blender/glTF convention (Y-up to Z-up)
- All dimensions in feet
- Hex is "flat-top" orientation (flat edges on top and bottom)

---

## 5. Texture Maps & Image Generation

### CRITICAL: Image Generation in CLI

Copilot CLI **cannot generate images directly in conversation**. All image generation
must go through Python scripts that call the Gemini API. The helper script is at:
`.github/skills/architecture-3d/gemini_image_gen.py`

**Prerequisites:**
```bash
pip install google-genai Pillow
# Set your API key (get one from https://aistudio.google.com/apikey)
export GEMINI_API_KEY="your-key-here"   # Linux/Mac
$env:GEMINI_API_KEY = "your-key-here"   # PowerShell
```

### Using the Image Generation Helper

**Generate a seamless tileable texture:**
```bash
python .github/skills/architecture-3d/gemini_image_gen.py texture \
    --material "polished concrete with visible aggregate" \
    -o assets/textures/concrete_basecolor.png

# Generate matching normal map:
python .github/skills/architecture-3d/gemini_image_gen.py texture \
    --material "polished concrete with visible aggregate" \
    --normal -o assets/textures/concrete_normal.png
```

**Generate concept art / reference images:**
```bash
python .github/skills/architecture-3d/gemini_image_gen.py concept \
    --description "modern tropical atrium with glass roof, palm trees, stone fountain" \
    --style "architectural visualization, photorealistic" \
    -o concept_atrium.png
```

**Generate any free-form image:**
```bash
python .github/skills/architecture-3d/gemini_image_gen.py generate \
    --prompt "seamless dark walnut hardwood flooring, top-down view" \
    --model gemini-2.5-flash-preview-image-generation \
    -o assets/textures/walnut_basecolor.png
```

**Edit an existing image:**
```bash
python .github/skills/architecture-3d/gemini_image_gen.py edit \
    --input renders/latest/front.png \
    --instruction "make the sky more dramatic with sunset colors" \
    -o renders/latest/front_sunset.png
```

### Available Gemini Models for Image Generation

| Model | Quality | Speed | Max Resolution | Cost |
|-------|---------|-------|---------------|------|
| `gemini-2.0-flash-exp` | Good | Fast (~3s) | 1024x1024 | Low |
| `gemini-2.5-flash-preview-image-generation` | Better | Medium | 1024x1024 | Medium |
| `gemini-3-pro-image-preview` | Best | Slower | 4096x4096 | Higher |

### Programmatic Usage (from Python scripts)
```python
# Import the helper directly
import sys
sys.path.insert(0, ".github/skills/architecture-3d")
from gemini_image_gen import generate_texture, generate_image, edit_image

# Generate a texture
generate_texture("travertine marble", output_path="assets/textures/travertine_basecolor.png")
generate_texture("travertine marble", normal=True, output_path="assets/textures/travertine_normal.png")

# Generate a concept image
generate_image("modern hexagonal house with glass walls in a forest",
               output_path="concept.png")

# Edit a render
edit_image("renders/latest/iso.png", "add dramatic storm clouds",
           output_path="renders/latest/iso_stormy.png")
```

### Procedural Textures (Blender Nodes, no API needed)
For materials that don't need photo-realism, use Blender's procedural textures:
- **Concrete**: Noise Texture -> ColorRamp (gray range) -> Base Color, plus Bump node
- **Wood**: Wave Texture (bands) + Noise (grain) -> Mix -> Base Color
- **Glass**: Principled BSDF with Transmission = 0.9, Roughness = 0.05
- **Grass/Ground**: Voronoi (cells) + Noise -> Green color ramp -> Base Color + Displacement

### Applying Textures in the Pipeline
1. Save generated textures to `assets/textures/`
2. Reference in Blender material setup:
   ```python
   tex = nodes.new('ShaderNodeTexImage')
   tex.image = bpy.data.images.load(texture_path)
   links.new(tex.outputs['Color'], bsdf.inputs['Base Color'])
   ```
3. Set UV mapping: for architectural surfaces, use "Box" projection or "Generated" coordinates

---

## 6. Landscape & Site Design

### Terrain Modeling
- Model terrain as a large planar mesh (4x building extents minimum)
- Use front-to-back slope for natural drainage (configurable `terrain_drop` parameter)
- Cut building footprint from terrain to show partial burial/berming
- Motorcourt/driveway excavation zones cut separately with retaining walls

### Grading Principles
- Minimum 2% slope away from building for drainage
- Retaining walls needed for grade changes > 3 ft
- Driveway slope should not exceed 15% (8.5 degrees)
- Courtyard floor should be 1-2 ft below surrounding grade for visual drama

### Landscape Elements (Future)
When adding landscape features:
- Trees: use simple cone/sphere primitives for massing, or instanced particle systems for realism
- Water features: transparent plane with animated wave displacement
- Paths: extruded curves with stone/gravel material
- Planting beds: raised geometry with mulch/soil texture

---

## 7. Asset Discovery, Import & Interior Design

### Finding 3D Assets
When the user asks for furniture, plants, fixtures, or decorative elements, use this search strategy:

#### Free Asset Sources (no API key required)
1. **Blender's built-in asset browser** (Blender 3.0+): Check for bundled assets first
2. **Local asset library**: Check `assets/models/` for previously downloaded assets
3. **glTF Sample Models**: github.com/KhronosGroup/glTF-Sample-Models (reference geometry)

#### Web Search for Assets
Use the web search tool to find free CC0/CC-BY assets from:
- **Poly Haven** (polyhaven.com): HDRIs, textures, and 3D models, all CC0
- **Sketchfab** (sketchfab.com): Filter by "downloadable" + "CC" license
- **BlenderKit** (blenderkit.com): Free tier has many architectural assets
- **Quixel Megascans** (quixel.com): Free with Unreal (some export to Blender)
- **Archive3D** (archive3d.net): Free architectural models
- **CGTrader/TurboSquid**: Filter by "free" for basic assets

#### AI-Generated Assets via Gemini
For custom textures, concept art, and reference images not available in libraries:
```bash
# Generate concept art for a room layout
python .github/skills/architecture-3d/gemini_image_gen.py concept \
    --description "modern minimalist bedroom with floor-to-ceiling windows overlooking forest" \
    -o assets/reference/bedroom_concept.png

# Generate a custom texture
python .github/skills/architecture-3d/gemini_image_gen.py texture \
    --material "moss-covered stone wall" \
    -o assets/textures/moss_stone_basecolor.png
```
> **Important**: Gemini generates 2D images only, not 3D models. Use generated images as
> textures applied to geometry, or as reference/concept art for design direction.

### Asset Import Pipeline
```python
import bpy

def import_asset(filepath, location=(0, 0, 0), scale=1.0, name=None):
    """Import a 3D asset into the current scene."""
    ext = filepath.lower().rsplit('.', 1)[-1]
    
    if ext in ('glb', 'gltf'):
        bpy.ops.import_scene.gltf(filepath=filepath)
    elif ext == 'obj':
        bpy.ops.wm.obj_import(filepath=filepath)
    elif ext == 'fbx':
        bpy.ops.import_scene.fbx(filepath=filepath)
    elif ext == 'blend':
        with bpy.data.libraries.load(filepath) as (data_from, data_to):
            data_to.objects = data_from.objects
        for obj in data_to.objects:
            bpy.context.collection.objects.link(obj)
    
    # Position and scale the imported object(s)
    imported = bpy.context.selected_objects
    for obj in imported:
        obj.location = location
        obj.scale = (scale, scale, scale)
        if name:
            obj.name = name
    
    return imported
```

### Interior Furnishing Strategy
When decorating interior spaces (atrium, wings, courtyard):

1. **Atrium Garden** (tropical indoor planting):
   - Import palm tree models (3-5 varieties for visual diversity)
   - Ground cover plants at -2 ft floor level
   - Specimen trees: 15-25 ft tall to fill the atrium volume
   - Water feature: reflecting pool or small fountain at center
   - Pathway: stone pavers winding through plantings
   - Lighting: uplights on key trees, ambient glow

2. **Wing Interiors** (residential rooms):
   - Living/dining: sofa, dining table, chairs, pendant lights
   - Kitchen: island, cabinets (simplified box geometry for massing)
   - Bedroom: bed, nightstands, closet wall
   - Office: desk, chair, bookshelf
   - Scale reference: standard furniture dimensions in feet

3. **Courtyard** (arrival sequence):
   - Entry sculpture or water feature as focal point
   - Low plantings along retaining walls
   - Recessed ground lighting along driveway edges
   - Material: stone pavers or polished concrete floor

### Asset Organization
```
assets/
  models/
    plants/          # Trees, shrubs, ground cover
    furniture/       # Sofas, tables, beds, chairs
    fixtures/        # Lights, faucets, hardware
    decorative/      # Art, sculptures, vases
  textures/
    wood/            # Flooring, cabinetry
    stone/           # Pavers, countertops
    fabric/          # Upholstery, curtains
    metal/           # Hardware, fixtures
  hdri/              # Environment lighting maps
```

### Scale & Placement Rules
- Always verify imported asset scale against known room dimensions
- Standard door height: 6.67 ft (80 in), width: 3 ft (36 in)
- Standard ceiling: 8-12 ft depending on room
- Furniture clearance: min 3 ft walkway between pieces
- Place assets with Z=0 on their room's floor level (varies by wing/atrium)

### Mandatory Clipping Check (Post-Placement)
**After EVERY move, scale, or create operation on any object**, run an AABB clipping check:
1. Compute the object's world-space bounding box
2. Test overlap against all building walls/facades/slabs
3. For atrium plants: verify bounding box stays inside the hex boundary
4. For wing furniture: verify bounding box stays inside the wing quad
5. If clipping is detected, adjust position/scale and re-check until clear
6. Report results to the user (e.g., "Clipping check: all clear" or "Fixed: moved bed 1.2 ft from wall")

This is a **non-optional workflow step**. Never skip it.

### Furniture Placement Conventions
Place furniture in realistic, architecturally sensible positions:
- **Beds**: headboard against a wall, centered or offset for nightstand space
- **Sofas**: facing the best view (glass wall) or a focal point (fireplace, TV)
- **Dining tables**: centered in dining area with chair clearance on all sides (min 3 ft)
- **Desks**: against a wall or facing a window for natural light
- **Bookshelves/storage**: flat against walls
- **Kitchen islands**: centered with 3-4 ft clearance to counters on all sides
- **Nightstands**: flanking the bed, against the same wall
- **Rugs**: centered under the primary furniture grouping, extending 1-2 ft beyond edges
- **Plants (interior)**: in corners, flanking windows, or as room dividers; never blocking walkways

---

## 8. Rendering Expertise

### Camera Settings
| View | Type | Focal Length | Location Strategy |
|------|------|-------------|-------------------|
| Top Plan | Orthographic | N/A (scale to fit) | Centered above, -Z direction |
| Isometric | Orthographic | N/A | 45° azimuth, 30° elevation from center |
| Front Elevation | Orthographic | N/A | Centered on front facade, +Y to -Y |
| Perspective Hero | Perspective | 24-35mm | Eye level (5.5 ft), 3/4 angle, rule of thirds |
| Interior | Perspective | 18-24mm | Standing height, looking toward focal point |

### Lighting Presets
- **Daylight**: Sun lamp, 5500K, slight warm cast, 15-30° from zenith, soft shadow
- **Golden Hour**: Sun lamp, 3500K, low angle (5-10°), long shadows
- **Overcast**: Large area light or HDRI, 6500K, very soft/no shadows
- **Night**: Point lights at warm 2700K for interior glow, cool 4000K ambient fill

### Render Settings (Quality vs Speed)
| Setting | Draft | Production |
|---------|-------|------------|
| Engine | EEVEE | Cycles |
| Samples | 32 | 256-512 |
| Resolution | 1280x720 | 3840x2160 |
| Denoising | On | On (OpenImageDenoise) |
| Film Transparent | On (for compositing) | Optional |

### HDRI Environment
For realistic outdoor lighting, use an HDRI:
```python
world = bpy.context.scene.world
world.use_nodes = True
env_tex = world.node_tree.nodes.new('ShaderNodeTexEnvironment')
env_tex.image = bpy.data.images.load('assets/hdri/outdoor.hdr')
```

---

## 9. Walkthrough Animation

### Camera Path Design
1. Create a Bezier curve along the desired walkthrough path
2. Set camera to follow the path with a Follow Path constraint
3. Add a Track To constraint pointing at an Empty (the "look target")
4. Animate the Empty along a separate smooth path for natural head movement

### Animation Settings
- Frame rate: 30 fps for smooth motion
- Walking speed: ~4 ft/s (1.2 m/s), so 1 ft per ~7.5 frames
- Camera height: 5.5 ft (eye level)
- Smooth camera motion: use Bezier interpolation, avoid sharp turns
- Total duration: 30-60 seconds for a residential walkthrough

### Walkthrough Script Pattern
```python
import bpy
from mathutils import Vector

# Define waypoints (x, y, z) in feet, converted to Blender units
waypoints = [
    (0, -60, 5.5),    # approach from driveway
    (0, -30, 5.5),    # enter courtyard
    (0, -5, 5.5),     # approach atrium entrance
    (0, 5, 0),        # step into atrium (lower floor)
    (10, 10, 0),      # look right toward Wing A
    (-10, 10, 0),     # look left toward Wing B
    (0, 20, 0),       # walk toward rear
]

# Create path curve
curve_data = bpy.data.curves.new('WalkthroughPath', type='CURVE')
curve_data.dimensions = '3D'
spline = curve_data.splines.new('BEZIER')
spline.bezier_points.add(len(waypoints) - 1)
for i, wp in enumerate(waypoints):
    spline.bezier_points[i].co = Vector(wp)
    spline.bezier_points[i].handle_type = 'AUTO'

path_obj = bpy.data.objects.new('WalkthroughPath', curve_data)
bpy.context.collection.objects.link(path_obj)

# Constrain camera to path
cam = bpy.data.objects['Camera']
follow = cam.constraints.new('FOLLOW_PATH')
follow.target = path_obj
follow.use_fixed_location = True
follow.offset_factor = 0.0

# Animate
bpy.context.scene.frame_start = 1
bpy.context.scene.frame_end = len(waypoints) * 60  # ~2 sec per waypoint
follow.keyframe_insert('offset_factor', frame=1)
follow.offset_factor = 1.0
follow.keyframe_insert('offset_factor', frame=bpy.context.scene.frame_end)
```

### Output Formats
- MP4 (H.264): `bpy.context.scene.render.image_settings.file_format = 'FFMPEG'`
- Image sequence (PNG): for post-processing flexibility
- GIF: for quick previews (downsample to 480p, 15fps)

---

## 10. Design Guidance

### Residential Architecture Principles
- **Circulation**: ensure clear paths between all rooms; the atrium serves as the central hub
- **Daylighting**: maximize glass on south-facing facades; use clerestory windows for deep rooms
- **Privacy gradient**: public spaces (entry, living) near front; private (bedrooms, study) toward rear/upper levels
- **Indoor-outdoor flow**: courtyard and atrium should feel like extensions of interior space
- **Proportion**: ceiling heights of 10-12 ft for main living spaces; 8-9 ft for bedrooms
- **Structure**: 1 ft slab thickness is realistic for residential concrete construction

### Hexagonal Design Considerations
- The hex atrium provides 360-degree visual connection to surrounding wings
- "Exploded" wing gaps create natural light wells and transition zones
- The master triangle unifies the composition and provides weather protection at the upper level
- Courtyard creates a dramatic arrival sequence: descend into the building, greeted by glass and garden

### Material Palette Guidance
- **Exterior**: curtain wall glass dominates; concrete at base/retaining walls grounds the building
- **Interior atrium**: glass roof admits zenith light; tropical planting at -2 ft floor creates a garden room
- **Wings**: each wing can have its own character through flooring, wall treatment, and furniture
- **Roof**: standing seam metal or concrete; the triangle slab could be a green roof

---

## 11. File Organization

### Project Structure
```
project-root/
  .github/skills/architecture-3d/   # This skill
    SKILL.md                         # Skill definition (this file)
    gemini_image_gen.py              # Gemini API image generation helper
    blender_helpers.py               # Blender utility functions
  archive/                           # Old outputs (never delete)
  assets/                            # Reference SVGs, textures, HDRIs
    textures/                        # Generated/sourced texture maps
    models/                          # Imported 3D assets (plants, furniture)
      plants/
      furniture/
      fixtures/
      decorative/
    hdri/                            # Environment lighting maps
  src/
    config.json                      # Parametric configuration
    plan.py                          # 2D geometry primitives
    model.py                         # 3D mesh generation
    export.py                        # GLB/SVG output
    validate.py                      # Constraint assertions
    render_blender.py                # Headless rendering
    blender_live_session.py          # Live viewport sync
    blender_remote.py                # TCP remote console server (port 9876)
    blender_startup.py               # Blender startup (GLB import, materials, file-watch)
    fix_render.py                    # Sky/lighting/render setup
    orchestration_policy.py          # Execution mode routing
    main.py                          # CLI entry point
    ui.py                            # Interactive parameter UI
  out/                               # Generated outputs (gitignored)
  renders/                           # Render outputs
    latest/                          # Most recent renders
  requirements.txt
  README.md
  CHANGELOG.md
  Makefile                           # Quick regen commands
  Send-Blender.ps1                   # PowerShell client for remote console
```

### Naming Conventions
- Output files: `{type}_s{s}_d{d}.{ext}` (e.g., `plan_s23_d7.svg`, `massing_s23_d7.glb`)
- Renders: `{view}.png` in `renders/latest/`
- Textures: `{material}_{map_type}.{ext}` (e.g., `concrete_basecolor.png`, `concrete_normal.png`)

### Config-Driven Generation
All geometry derives from `src/config.json`. Every dimensional parameter is configurable:
- `s`: hex side length (ft)
- `d`: atrium-to-triangle clearance (ft)
- `ceiling_height`: floor-to-ceiling height (ft)
- `slab_thickness`: structural slab depth (ft)
- `terrain_drop`: front-to-back grade change (ft)
- Override via CLI: `python -m src.main --s 25 --d 8`

---

## 12. Validation & Quality Checks

Before declaring any geometry change complete, run validation:

```bash
python -m src.main --validate-only
```

Checks include:
- All hex edges equal length (within epsilon)
- All wing quad edges equal length where expected
- Shared edges between components match exactly
- Courtyard shared edge aligns with atrium front edge
- No degenerate triangles (zero area faces)
- Total areas computed and reported
- Elevation stack is consistent (no floating slabs, no intersecting levels)

### GLB Inspection Checklist
After generating a GLB, verify in Blender or a viewer:
- [ ] All faces visible from expected viewing angles (no inverted normals)
- [ ] No z-fighting between adjacent surfaces
- [ ] Materials assigned correctly (glass = transparent, concrete = opaque gray, ground = green)
- [ ] Scale is correct (measure a known dimension)
- [ ] No gaps between components that should be seamless

---

## 13. Common Pitfalls & Fixes

| Problem | Cause | Fix |
|---------|-------|-----|
| Faces invisible from one side | Wrong winding order / inverted normals | Use centroid dot-product test to flip |
| Walls disappear after filtering | Edge-skip logic too aggressive | Use endpoint+midpoint boundary check, not buffer intersection |
| Ground overhangs wall below | Terrain cut wider than wall footprint | Snap cut width to exact wall width parameter |
| Blender closes when shell exits | Process not detached | Use `DETACHED_PROCESS` creation flags |
| GLB imports upside down | Missing orientation correction | Apply -90° X rotation in export |
| Materials all same color | Per-component material not set in GLB | Ensure each mesh node has distinct material index |
| Shared edge gap | Floating point drift | Use same vertex array for both components |
