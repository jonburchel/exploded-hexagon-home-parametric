# Exploded Hexagon Home (Parametric)

![current design](out/plan_s23_d7.svg)

This project reproducibly generates:
- 2D plan SVG (labels on/off)
- 3D massing GLB (glass, concrete, ground materials)
- optional Blender renders (top/iso/front) when Blender is available

## Folder layout

```text
exploded-hexagon-home/
  archive/      # copied legacy outputs, originals preserved
  assets/       # reference inputs (master SVGs, blend reference)
  out/          # generated SVG/GLB/summary/quicklook
  renders/      # existing and new renders (renders/latest for current run)
  src/          # parametric source modules
```

## Setup (required once)

Install dependencies:

```powershell
python -m pip install -r requirements.txt
```

### Gemini Image Generation (optional, for AI-generated textures)

To generate photorealistic textures and concept art via the Gemini API:

```powershell
pip install google-genai
```

Set your API key (get one from https://aistudio.google.com/apikey):

```powershell
$env:GEMINI_API_KEY = "your-key-here"
```

Generate textures:

```powershell
python .github/skills/architecture-3d/gemini_image_gen.py texture --material "polished concrete" -o assets/textures/concrete_basecolor.png
python .github/skills/architecture-3d/gemini_image_gen.py texture --material "polished concrete" --normal -o assets/textures/concrete_normal.png
```

See `.github/skills/architecture-3d/gemini_image_gen.py --help` for all options (concept art, image editing, model selection, resolution control).

Verify watchdog (needed for `auto` mode):

```powershell
python -c "from watchdog.observers import Observer; print('watchdog OK:', Observer.__name__)"
```

## Config and CLI

Default parameters are in `src/config.json`.

Run baseline generation:

```powershell
python -m src.main --s 23 --d 7
```

Labels off:

```powershell
python -m src.main --s 23 --d 7 --no-labels
```

Timestamped outputs:

```powershell
python -m src.main regen --timestamped
```

## Auto mode

Preferred watcher (uses `watchdog` if installed):

```powershell
python -m src.main auto
```

If `watchdog` is unavailable, auto mode falls back to a single timestamped regen and prints a `make regen` fallback hint.

## Hybrid orchestration policy

`src/orchestration_policy.py` captures the project workflow for future skill packaging:
- decides when to use **procedural Python** vs **in-place Blender** edits
- routes geometry-first tasks to **GPT-5.3-Codex** when values are not yet explicitly derived in Python
- routes planning/coding tasks to **Claude Opus 4.6 Fast High Thinking**
- supports automatic model fallback when a prior model attempt is marked as failed

## Interactive UI

Launch the local parameter UI:

```powershell
python -m src.ui
```

UI features:
- live parameter editing for `s`, `d`, levels, roof, terrain, and driveway width
- auto-regenerate toggle for dynamic updates as you type
- detects `src/*.py` and `src/config.json` changes while UI is open (auto-regenerates when Auto is enabled)
- labels toggle and timestamped-output toggle
- courtyard on/off toggle (`on` = exterior full hex courtyard sharing the atrium front edge)
- optional Blender executable field (useful when Blender is installed but not on PATH)
- output path panel showing latest SVG/GLB/summary files
- interactive plan viewport (mouse wheel zoom, left-drag pan, right-drag orbit/rotate, Reset View)
- one-click `Launch Blender Live Reload` button (opens Blender and does in-place object updates when GLB changes)

Note: for Blender path input, paste it without surrounding quotes.

## Blender live reload

Blender does not auto-refresh a manually imported GLB by default. Use live reload instead:

- In UI: click **Launch Blender Live Reload**
- Or CLI:

```powershell
python -m src.blender_live_session --glb F:\home\exploded-hexagon-home\out\massing_s23_d7.glb --blender-executable "C:\Program Files\Blender Foundation\Blender 5.0\blender.exe"
```

Live reload now always uses in-place updates (preserves object names and updates meshes/transforms in place).

The exported GLB now includes:
- corrected orientation for Blender (`glb_rotate_x_deg: -90` by default)
- separate selectable objects/components (wings, master triangle, atrium, courtyard, ground, roof/facades)

You can also force Blender discovery from shell:

```powershell
$env:BLENDER_PATH="C:\Program Files\Blender Foundation\Blender 4.5\blender.exe"
python -m src.main --s 23 --d 7
```

## Outputs

Single-run baseline (`--s 23 --d 7`) writes:
- `out/plan_s23_d7.svg`
- `out/massing_s23_d7.glb`
- `out/summary_s23_d7.txt`
- `out/quicklook_s23_d7.png` (only when Blender renders succeed)

When Blender exists, renders are written to:
- `renders/latest/top.png`
- `renders/latest/iso.png`
- `renders/latest/front.png`

