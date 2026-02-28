# CHANGELOG

## Session 7 - Big Update: Terrain, Courtyards, Driveway, Walls, Textures

### Geometry / Model Changes (model.py, plan.py)
- **Wing A/B lower level walls**: Exterior-facing walls now concrete (were glass). Atrium-facing edge remains glass.
- **Terrain profile**: Terrain stays flat across to the back of Wings A and B, then steeply descends to ground level. Previously sloped from the wing outer midpoints.
- **Side courtyard voids**: Added hexagonal courtyard voids between Wing B/C and Wing A/C. Same hex size as atrium. Retaining walls rise 4' above surrounding terrain, open at the back where terrain meets ground level. Floor is lawn.
- **Driveway extension**: Ramp extended 50% (67.5'). Added 50' flat section beyond crest, then 50' curved section turning 90 degrees. Terrain gently slopes down on approach (2% grade) creating a crest that hides the entry courtyard.
- **Bedroom accent wall**: The hex edge 3→4 (Wing B atrium boundary) at the master triangle level is now concrete instead of glass, creating an opaque wall between the bedroom and atrium.

### Furniture (furnish_wingb.py)
- Bed and nightstands pushed against the interior wall (hex edge 3→4)
- Sitting area moved ~6' further toward the triangle tip for better spacing
- Rug resized (9'×8'), recentered under bed, recolored with jewel tones (deep blue, gold, burgundy)
- Duplicate print statement removed

### New Scripts
- **src/generate_textures.py**: Gemini API texture generation for all materials (marble Star of David, driveway, concrete, plant wall, accent wall, rug, sky, lawn). Requires GEMINI_API_KEY.
- **src/apply_textures.py**: Blender script to apply generated textures to scene materials with proper UV mapping and scaling.
- **src/clip_check.py**: Blender script for full-scene AABB clipping check on all plants and furniture, with auto-fix.

### Config Changes
- `driveway_length`: 45 → 67.5
- Added: `driveway_flat_length: 50`, `driveway_curve_length: 50`, `driveway_approach_slope: 0.02`

### Blender (blender_startup.py)
- Added "Side Courtyards" collection
- Added bedroom_accent_wall to collection map

## Session 6 - Feet-to-meters conversion
- **BREAKING**: GLB export now converts all geometry from feet to meters (multiply by 0.3048).
  This fixes Blender walk navigation so 1.7m walk height = actual 5'6" eye level.
- Updated `export.py`: `write_glb()` applies `feet_to_meters=True` by default.
- Updated `atrium_garden.py`: all constants and inline dimensions converted via `FT = 0.3048`.
- Updated `place_realistic_plants.py`: ring radii, floor Z, and placement distances converted.
- Updated `render_production.py`: camera positions converted; unit settings changed to METRIC/1.0.
- Updated `blender_startup.py`: unit system changed from IMPERIAL/0.3048 to METRIC/1.0.
- Updated `walkthrough.py`: all choreography coordinates and building constants converted.
- Updated `furnish_wingb.py`: all furniture dimensions and placement offsets converted.
- Config values (`config.json`) remain in feet for user-facing editing; conversion happens at export.

## 2026-02-26
- Added formal parametric project structure with `src/`, `out/`, `assets/`, and `archive/`.
- Preserved all original outputs in place and copied legacy generated files into timestamped `archive/` folders.
- Copied master reference SVGs into `assets/`:
  - `assets/master_plan_enhanced_labeled.svg`
  - `assets/master_plan_parametric_labeled_dims.svg`
- Added modular generator pipeline (`plan`, `model`, `export`, `validate`, `render_blender`, `main`) with CLI config overrides.
- Added validation summary export and optional Blender rendering integration.
- Added interactive Tk UI (`python -m src.ui`) for dynamic parameter editing and regeneration.
- Added Blender path override support via config/CLI/env (`blender_executable` / `--blender-executable` / `BLENDER_PATH`).
- Added explicit setup instructions and watchdog verification steps in `README.md`, plus `make setup`.
- Added courtyard on/off support (default now off via `courtyard_module: "none"`), with matching SVG/model/validation behavior.
- UI now detects source file changes and can auto-regenerate; preview fallback improved to use latest existing quicklook/render images.
- Blender executable parsing now strips accidental surrounding quotes and surfaces render errors in generation/UI status.
- Courtyard "on" now uses an exterior full hex attached to the atrium front edge (matching atrium size), and default config is set to `courtyard_module: "exterior_hex"`.
- Added interactive 2D plan viewport in the UI with zoom, pan, and orbit-style rotation controls.
- GLB export now writes independent component objects (atrium, wings, master triangle, courtyard, ground, etc.) for direct per-part Blender editing.
- Added GLB orientation correction parameter (`glb_rotate_x_deg`, default `-90`) to avoid manual X-axis rotation in Blender.
- Added Blender live reload helper (`src.blender_live_session.py`) and a one-click UI launcher.

## Session 4: Interior Design, Materials, and Realistic Assets

### Structural Fixes
- Triangle roof slab now has hexagonal cutout so atrium glass dome is unobstructed from above.
- Wing C floor lowered to atrium level (-2 ft) for seamless floor continuity.
- Wing A and Wing C atrium-facing walls removed (both wing facade and atrium facade skip edges).
- Wing C floor material changed to marble to match atrium.

### Lighting & Render Settings
- Added `src/sun_position.py`: solar position calculator (Spencer algorithm) for NC Triad location.
- Created `src/blender_startup.py`: comprehensive Blender startup script that sets up everything GLB cannot store (sun lamp, fill light, world sky, Filmic color management, exposure, material upgrades, scene organization, file-watch).
- Sun energy calibrated to 2.0 with altitude-based scaling to avoid overexposure.
- Filmic view transform with -0.3 exposure and Medium Contrast look.

### Interior Elements
- Atrium garden: tropical plants, fountain with water (transmission material), pathways, soil beds.
- Wing B bedroom: California King bed, nightstands with lamps, lounge chairs, coffee table, area rug.
- Fountain water upgraded with transmission=0.85, IOR=1.33 for realistic transparency.

### Realistic 3D Assets
- Created `src/download_assets.py`: automated downloader for CC0 plant models from Poly Haven API.
- Downloaded 11 realistic plant models (potted plants, tropical trees, ferns, shrubs, moss).
- Created `src/place_realistic_plants.py`: replaces procedural primitives with imported Poly Haven GLTF models.
- 36 realistic plants placed in concentric rings around the fountain.

### Scene Organization
- Blender startup script organizes objects into labeled collections: Building > {Atrium, Wing A/B/C, Master Triangle, Terrain}, Atrium Garden, Wing B Bedroom, Lighting.
- Live session launcher now uses `blender_startup.py` for full setup (lights, materials, collections).

### Material Upgrades (Procedural PBR)
- Concrete: noise texture + subtle bump for aggregate variation.
- Marble: wave veining + noise for natural variation.
- Glass: transmission 0.92, IOR 1.45, dithered alpha.
- Ground: voronoi cells + noise for grass variation with displacement.

### Config Additions
- `site_latitude`, `site_longitude`: 35.5°N, -80.0°W (NC Triad).
- `sun_month`, `sun_day`, `sun_hour`: configurable solar date/time.
- `site_north_offset_deg`: building orientation relative to true north.

### Files Added
- `src/sun_position.py`
- `src/blender_startup.py`
- `src/furnish_wingb.py`
- `src/download_assets.py`
- `src/place_realistic_plants.py`
- `.gitignore` (excludes downloaded assets, pycache, Blender temp files)
