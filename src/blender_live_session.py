from __future__ import annotations

import argparse
from pathlib import Path
import json
import shutil
import subprocess


def _resolve_blender(blender_executable: str | None) -> str | None:
    if blender_executable:
        cleaned = blender_executable.strip().strip('"').strip("'")
        explicit = Path(cleaned).expanduser()
        if explicit.exists():
            return str(explicit)
        found = shutil.which(cleaned)
        if found:
            return found
    return shutil.which("blender")


def launch_live_reload(
    blender_executable: str | None,
    glb_path: Path,
) -> subprocess.Popen:
    blender = _resolve_blender(blender_executable)
    if blender is None:
        raise RuntimeError("Blender executable not found.")
    if not glb_path.exists():
        raise RuntimeError(f"GLB path does not exist: {glb_path}")

    startup_script = Path(__file__).parent / "blender_startup.py"
    if not startup_script.exists():
        raise RuntimeError(f"blender_startup.py not found at {startup_script}")

    creationflags = 0
    detached = int(getattr(subprocess, "DETACHED_PROCESS", 0))
    new_group = int(getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))
    if detached and new_group:
        creationflags = detached | new_group

    return subprocess.Popen(
        [blender, "--python", str(startup_script), "--", str(glb_path.resolve())],
        creationflags=creationflags,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        close_fds=True,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Launch Blender with live GLB reload watcher")
    parser.add_argument("--glb", required=True, help="Path to GLB file to watch/import.")
    parser.add_argument("--blender-executable", default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    blender_exe = args.blender_executable
    if blender_exe is None:
        import json
        config_path = Path(__file__).parent / "config.json"
        if config_path.exists():
            cfg = json.loads(config_path.read_text())
            blender_exe = cfg.get("blender_executable")
    proc = launch_live_reload(blender_exe, Path(args.glb))
    print(f"Started Blender live reload session (pid={proc.pid}).")


if __name__ == "__main__":
    main()
