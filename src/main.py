from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import time
from typing import Any, Dict

from .export import write_glb, write_svg
from .model import build_model
from .plan import build_plan
from .render_blender import render_if_available
from .validate import validate_geometry, write_summary

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_PATH = Path(__file__).resolve().with_name("config.json")


def _load_config(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _apply_overrides(config: Dict[str, Any], args: argparse.Namespace) -> Dict[str, Any]:
    updated = dict(config)
    mapping = {
        "s": "s",
        "d": "d",
        "triangle_clockwise_backoff_deg": "triangle_clockwise_backoff_deg",
        "triangle_plan_down_shift_ft": "triangle_plan_down_shift_ft",
        "ceiling_height": "ceiling_height",
        "slab_thickness": "slab_thickness",
        "lower_ground": "lower_ground",
        "upper_ground": "upper_ground",
        "master_triangle_elevation": "master_triangle_elevation",
        "atrium_floor": "atrium_floor",
        "atrium_roof_base": "atrium_roof_base",
        "atrium_roof_rise": "atrium_roof_rise",
        "courtyard_drop": "courtyard_drop",
        "terrain_drop": "terrain_drop",
        "driveway_width": "driveway_width",
        "driveway_top_width": "driveway_top_width",
        "driveway_length": "driveway_length",
        "glb_rotate_x_deg": "glb_rotate_x_deg",
        "blender_executable": "blender_executable",
    }

    for arg_name, key in mapping.items():
        value = getattr(args, arg_name)
        if value is not None:
            updated[key] = value

    if args.labels is not None:
        updated["labels"] = args.labels
    return updated


def _fmt_num(value: float) -> str:
    value = float(value)
    if value.is_integer():
        return str(int(value))
    return str(value).replace(".", "p")


def _output_paths(config: Dict[str, Any], out_dir: Path, timestamped: bool) -> Dict[str, Any]:
    suffix = f"s{_fmt_num(config['s'])}_d{_fmt_num(config['d'])}"
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S") if timestamped else ""
    name_suffix = f"{suffix}_{stamp}" if stamp else suffix
    return {
        "suffix": suffix,
        "stamp": stamp,
        "plan": out_dir / f"plan_{name_suffix}.svg",
        "glb": out_dir / f"massing_{name_suffix}.glb",
        "summary": out_dir / f"summary_{name_suffix}.txt",
    }


def generate_once(
    config: Dict[str, Any],
    out_dir: Path,
    renders_dir: Path,
    timestamped: bool,
    blender_executable: str | None = None,
) -> Dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = _output_paths(config, out_dir, timestamped=timestamped)

    plan = build_plan(config)
    metrics = validate_geometry(plan, config)
    model = build_model(plan, config)
    include_courtyard = str(config.get("courtyard_module", "none")) != "none"

    write_svg(
        plan,
        paths["plan"],
        include_labels=bool(config.get("labels", True)),
        include_courtyard=include_courtyard,
        config=config,
        metrics=metrics,
    )
    write_glb(model, paths["glb"], rotate_x_deg=float(config.get("glb_rotate_x_deg", 0.0)))

    blender_available, render_paths, render_error = render_if_available(
        paths["glb"],
        renders_dir / "latest",
        blender_executable=blender_executable,
    )
    quicklook_path: Path | None = None
    if blender_available and render_paths:
        iso_path = next((path for path in render_paths if path.name == "iso.png"), render_paths[0])
        quicklook_name = f"quicklook_{paths['suffix']}"
        if paths["stamp"]:
            quicklook_name = f"{quicklook_name}_{paths['stamp']}"
        quicklook_path = out_dir / f"{quicklook_name}.png"
        quicklook_path.write_bytes(iso_path.read_bytes())

    write_summary(
        paths["summary"],
        config,
        metrics,
        outputs={"plan": paths["plan"], "glb": paths["glb"], "summary": paths["summary"]},
        render_paths=render_paths,
        quicklook_path=quicklook_path,
        blender_available=blender_available,
    )

    areas = metrics["areas"]
    print(
        f"[ok] areas sqft: atrium={areas['atrium']:.2f}, wings={areas['wings_total']:.2f}, "
        f"triangle={areas['master_triangle']:.2f}, courtyard={areas['courtyard']:.2f}"
    )
    print(f"[ok] plan: {paths['plan']}")
    print(f"[ok] glb: {paths['glb']}")
    print(f"[ok] summary: {paths['summary']}")
    if blender_available and render_paths:
        print(f"[ok] renders: {', '.join(str(path) for path in render_paths)}")
        if quicklook_path is not None:
            print(f"[ok] quicklook: {quicklook_path}")
    elif blender_available:
        if render_error:
            print(f"[warn] Blender render issue: {render_error}")
        else:
            print("[warn] Blender detected but renders were not produced.")
    else:
        print("[skip] Blender not found, renders skipped.")

    return {
        "paths": paths,
        "metrics": metrics,
        "blender_available": blender_available,
        "render_paths": render_paths,
        "quicklook_path": quicklook_path,
        "render_error": render_error,
    }


def run_auto(config_path: Path, args: argparse.Namespace) -> None:
    try:
        from watchdog.events import FileSystemEventHandler
        from watchdog.observers import Observer
    except ImportError:
        print("[auto] watchdog not installed, fallback to single timestamped regen. Optional fallback: make regen")
        config = _apply_overrides(_load_config(config_path), args)
        generate_once(
            config,
            Path(args.out_dir),
            Path(args.renders_dir),
            timestamped=True,
            blender_executable=(config.get("blender_executable") or None),
        )
        return

    class RegenHandler(FileSystemEventHandler):
        def __init__(self) -> None:
            self.last_run = 0.0
            super().__init__()

        def on_any_event(self, event) -> None:
            if event.is_directory:
                return
            src = Path(event.src_path)
            if src.suffix != ".py" and src.name != "config.json":
                return

            now = time.time()
            if now - self.last_run < 0.5:
                return
            self.last_run = now

            config = _apply_overrides(_load_config(config_path), args)
            try:
                generate_once(
                    config,
                    Path(args.out_dir),
                    Path(args.renders_dir),
                    timestamped=True,
                    blender_executable=(config.get("blender_executable") or None),
                )
            except Exception as exc:
                print(f"[auto] generation failed: {exc}")

    handler = RegenHandler()
    observer = Observer()
    watch_dir = config_path.parent
    observer.schedule(handler, str(watch_dir), recursive=False)
    observer.start()

    config = _apply_overrides(_load_config(config_path), args)
    generate_once(
        config,
        Path(args.out_dir),
        Path(args.renders_dir),
        timestamped=True,
        blender_executable=(config.get("blender_executable") or None),
    )
    print(f"[auto] watching: {watch_dir}")
    try:
        while True:
            time.sleep(1.0)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Exploded hexagon parametric generator")
    parser.add_argument("command", nargs="?", choices=("regen", "auto"), default="regen")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG_PATH))
    parser.add_argument("--out-dir", default=str(PROJECT_ROOT / "out"))
    parser.add_argument("--renders-dir", default=str(PROJECT_ROOT / "renders"))
    parser.add_argument("--timestamped", action="store_true", help="Add timestamp suffix to output filenames.")

    parser.add_argument("--s", type=float, default=None)
    parser.add_argument("--d", type=float, default=None)
    parser.add_argument(
        "--triangle-clockwise-backoff-deg",
        dest="triangle_clockwise_backoff_deg",
        type=float,
        default=None,
    )
    parser.add_argument("--triangle-plan-down-shift-ft", dest="triangle_plan_down_shift_ft", type=float, default=None)
    parser.add_argument("--ceiling-height", dest="ceiling_height", type=float, default=None)
    parser.add_argument("--slab-thickness", dest="slab_thickness", type=float, default=None)
    parser.add_argument("--lower-ground", dest="lower_ground", type=float, default=None)
    parser.add_argument("--upper-ground", dest="upper_ground", type=float, default=None)
    parser.add_argument("--master-triangle-elevation", dest="master_triangle_elevation", type=float, default=None)
    parser.add_argument("--atrium-floor", dest="atrium_floor", type=float, default=None)
    parser.add_argument("--atrium-roof-base", dest="atrium_roof_base", type=float, default=None)
    parser.add_argument("--atrium-roof-rise", dest="atrium_roof_rise", type=float, default=None)
    parser.add_argument("--courtyard-drop", dest="courtyard_drop", type=float, default=None)
    parser.add_argument("--terrain-drop", dest="terrain_drop", type=float, default=None)
    parser.add_argument("--driveway-width", dest="driveway_width", type=float, default=None)
    parser.add_argument("--driveway-top-width", dest="driveway_top_width", type=float, default=None)
    parser.add_argument("--driveway-length", dest="driveway_length", type=float, default=None)
    parser.add_argument("--glb-rotate-x-deg", dest="glb_rotate_x_deg", type=float, default=None)
    parser.add_argument("--blender-executable", dest="blender_executable", type=str, default=None)
    parser.add_argument("--labels", dest="labels", action="store_true")
    parser.add_argument("--no-labels", dest="labels", action="store_false")
    parser.set_defaults(labels=None)

    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config_path = Path(args.config)

    if args.command == "auto":
        run_auto(config_path, args)
        return

    config = _apply_overrides(_load_config(config_path), args)
    generate_once(
        config,
        Path(args.out_dir),
        Path(args.renders_dir),
        timestamped=args.timestamped,
        blender_executable=(config.get("blender_executable") or None),
    )


if __name__ == "__main__":
    main()

