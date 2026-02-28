from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import queue
import threading
import tkinter as tk
from tkinter import ttk
from typing import Any, Dict, List, Tuple

from .blender_live_session import launch_live_reload
from .main import DEFAULT_CONFIG_PATH, PROJECT_ROOT, _load_config, generate_once
from .plan import build_plan

Point2D = Tuple[float, float]

NUMERIC_FIELDS = [
    ("s", "Atrium side s (ft)"),
    ("d", "Master triangle offset d (ft)"),
    ("triangle_clockwise_backoff_deg", "Triangle clockwise backoff (deg)"),
    ("triangle_plan_down_shift_ft", "Triangle plan down shift (ft)"),
    ("ceiling_height", "Ceiling height (ft)"),
    ("slab_thickness", "Slab thickness (ft)"),
    ("lower_ground", "Lower ground (ft)"),
    ("upper_ground", "Upper ground (ft)"),
    ("master_triangle_elevation", "Master triangle elevation (ft)"),
    ("atrium_floor", "Atrium floor (ft)"),
    ("atrium_roof_base", "Atrium roof base (ft)"),
    ("atrium_roof_rise", "Atrium roof rise (ft)"),
    ("courtyard_drop", "Courtyard level (ft)"),
    ("terrain_drop", "Terrain drop (ft)"),
    ("driveway_width", "Driveway width (ft)"),
    ("driveway_top_width", "Driveway top width (ft)"),
    ("driveway_length", "Driveway length (ft)"),
    ("glb_rotate_x_deg", "GLB rotate X (deg)"),
]


class ParametricUI:
    def __init__(self, root: tk.Tk, config_path: Path, out_dir: Path, renders_dir: Path) -> None:
        self.root = root
        self.config_path = config_path
        self.out_dir = out_dir
        self.renders_dir = renders_dir
        self.config: Dict[str, Any] = _load_config(config_path)

        self.numeric_vars: Dict[str, tk.StringVar] = {}
        self.labels_var = tk.BooleanVar(value=bool(self.config.get("labels", True)))
        self.auto_var = tk.BooleanVar(value=True)
        self.timestamped_var = tk.BooleanVar(value=False)
        self.courtyard_var = tk.BooleanVar(value=str(self.config.get("courtyard_module", "none")) != "none")
        self.blender_var = tk.StringVar(value=str(self.config.get("blender_executable", "")))
        self.status_var = tk.StringVar(value="Ready.")
        self.plan_var = tk.StringVar(value="")
        self.glb_var = tk.StringVar(value="")
        self.summary_var = tk.StringVar(value="")

        self._queue: queue.Queue[tuple[str, Any, Dict[str, Any] | None]] = queue.Queue()
        self._is_generating = False
        self._rerun_requested = False
        self._auto_after_id: str | None = None
        self._src_mtimes: Dict[Path, float] = {}
        self._src_scan_seconds = 1.0

        self._viewport_points: List[Point2D] = []
        self._vp_scale = 1.0
        self._vp_pan_x = 0.0
        self._vp_pan_y = 0.0
        self._vp_rotation = 0.0
        self._vp_pan_anchor: Tuple[int, int] | None = None
        self._vp_rotate_anchor_x: int | None = None

        self._build_ui()
        self._populate_from_config(self.config)
        self._refresh_source_mtimes()
        self._update_viewport(self.config, reset_view=True)

        self.root.after(150, self._poll_queue)
        self.root.after(1000, self._poll_source_changes)

    def _build_ui(self) -> None:
        self.root.title("Exploded Hexagon Home - Parametric UI")
        self.root.geometry("1240x840")

        container = ttk.Frame(self.root, padding=12)
        container.pack(fill="both", expand=True)

        title = ttk.Label(container, text="Parametric Controls", font=("Segoe UI", 16, "bold"))
        title.pack(anchor="w")

        controls = ttk.Frame(container)
        controls.pack(fill="x", pady=(10, 8))

        for row, (key, label) in enumerate(NUMERIC_FIELDS):
            ttk.Label(controls, text=label).grid(row=row, column=0, sticky="w", padx=(0, 8), pady=3)
            var = tk.StringVar()
            entry = ttk.Entry(controls, textvariable=var, width=18)
            entry.grid(row=row, column=1, sticky="w", pady=3)
            entry.bind("<KeyRelease>", self._on_value_changed)
            entry.bind("<FocusOut>", self._on_value_changed)
            self.numeric_vars[key] = var

        options = ttk.LabelFrame(container, text="Options", padding=8)
        options.pack(fill="x", pady=(8, 8))
        ttk.Checkbutton(options, text="Labels on SVG", variable=self.labels_var, command=self._on_value_changed).grid(
            row=0, column=0, sticky="w"
        )
        ttk.Checkbutton(
            options,
            text="Auto regenerate on change",
            variable=self.auto_var,
            command=self._on_value_changed,
        ).grid(row=0, column=1, sticky="w", padx=(16, 0))
        ttk.Checkbutton(
            options,
            text="Timestamped output filenames",
            variable=self.timestamped_var,
            command=self._on_value_changed,
        ).grid(row=0, column=2, sticky="w", padx=(16, 0))
        ttk.Checkbutton(
            options,
            text="Include courtyard",
            variable=self.courtyard_var,
            command=self._on_value_changed,
        ).grid(row=0, column=3, sticky="w", padx=(16, 0))

        ttk.Label(options, text="Blender executable (optional):").grid(row=1, column=0, sticky="w", pady=(8, 0))
        blender_entry = ttk.Entry(options, textvariable=self.blender_var, width=80)
        blender_entry.grid(row=1, column=1, columnspan=3, sticky="we", pady=(8, 0), padx=(8, 0))
        blender_entry.bind("<KeyRelease>", self._on_value_changed)
        blender_entry.bind("<FocusOut>", self._on_value_changed)

        actions = ttk.Frame(container)
        actions.pack(fill="x", pady=(4, 8))
        self.generate_btn = ttk.Button(actions, text="Generate Now", command=self.generate_now)
        self.generate_btn.pack(side="left")
        ttk.Button(actions, text="Save to config.json", command=self.save_config).pack(side="left", padx=(8, 0))
        ttk.Button(actions, text="Reload config.json", command=self.reload_config).pack(side="left", padx=(8, 0))
        ttk.Button(actions, text="Reset View", command=self._reset_view).pack(side="left", padx=(8, 0))
        ttk.Button(actions, text="Launch Blender Live Reload", command=self.launch_blender_live).pack(side="left", padx=(8, 0))

        self.status_label = ttk.Label(container, textvariable=self.status_var, foreground="#174d2a")
        self.status_label.pack(anchor="w", pady=(0, 8))

        outputs = ttk.LabelFrame(container, text="Latest Outputs", padding=8)
        outputs.pack(fill="x")
        ttk.Label(outputs, text="Plan SVG:").grid(row=0, column=0, sticky="w")
        ttk.Entry(outputs, textvariable=self.plan_var, width=130).grid(row=0, column=1, sticky="we", padx=(6, 0), pady=2)
        ttk.Label(outputs, text="Massing GLB:").grid(row=1, column=0, sticky="w")
        ttk.Entry(outputs, textvariable=self.glb_var, width=130).grid(row=1, column=1, sticky="we", padx=(6, 0), pady=2)
        ttk.Label(outputs, text="Summary TXT:").grid(row=2, column=0, sticky="w")
        ttk.Entry(outputs, textvariable=self.summary_var, width=130).grid(row=2, column=1, sticky="we", padx=(6, 0), pady=2)
        outputs.columnconfigure(1, weight=1)

        viewport_frame = ttk.LabelFrame(container, text="Interactive Plan Viewport", padding=8)
        viewport_frame.pack(fill="both", expand=True, pady=(8, 0))
        hint = ttk.Label(
            viewport_frame,
            text="Mouse wheel: zoom, left drag: pan, right drag: orbit (rotate), Reset View to reframe.",
        )
        hint.pack(anchor="w", pady=(0, 6))
        self.view_canvas = tk.Canvas(viewport_frame, background="#f8fafc", highlightthickness=1, highlightbackground="#b9c7d6")
        self.view_canvas.pack(fill="both", expand=True)
        self.view_canvas.bind("<Configure>", lambda _e: self._draw_viewport())
        self.view_canvas.bind("<MouseWheel>", self._on_wheel)
        self.view_canvas.bind("<Button-4>", self._on_wheel)
        self.view_canvas.bind("<Button-5>", self._on_wheel)
        self.view_canvas.bind("<ButtonPress-1>", self._on_pan_start)
        self.view_canvas.bind("<B1-Motion>", self._on_pan_move)
        self.view_canvas.bind("<ButtonRelease-1>", self._on_pan_end)
        self.view_canvas.bind("<ButtonPress-3>", self._on_rotate_start)
        self.view_canvas.bind("<B3-Motion>", self._on_rotate_move)
        self.view_canvas.bind("<ButtonRelease-3>", self._on_rotate_end)

    def _populate_from_config(self, config: Dict[str, Any]) -> None:
        for key, _ in NUMERIC_FIELDS:
            self.numeric_vars[key].set(str(config.get(key, "")))
        self.labels_var.set(bool(config.get("labels", True)))
        self.courtyard_var.set(str(config.get("courtyard_module", "none")) != "none")
        self.blender_var.set(str(config.get("blender_executable", "")))

    def _collect_config(self) -> Dict[str, Any]:
        cfg = dict(self.config)
        for key, _ in NUMERIC_FIELDS:
            text = self.numeric_vars[key].get().strip()
            if not text:
                raise ValueError(f"'{key}' cannot be empty.")
            cfg[key] = float(text)
        cfg["labels"] = bool(self.labels_var.get())
        cfg["courtyard_module"] = "exterior_hex" if self.courtyard_var.get() else "none"
        cfg["blender_executable"] = self.blender_var.get().strip()
        return cfg

    def _set_status(self, message: str, error: bool = False) -> None:
        self.status_var.set(message)
        self.status_label.configure(foreground="#8b0000" if error else "#174d2a")

    def _try_config_from_inputs(self) -> Dict[str, Any] | None:
        try:
            return self._collect_config()
        except ValueError:
            return None

    def _on_value_changed(self, _event=None) -> None:
        cfg = self._try_config_from_inputs()
        if cfg is not None:
            self._update_viewport(cfg, reset_view=False)
        if not self.auto_var.get():
            return
        if self._auto_after_id is not None:
            self.root.after_cancel(self._auto_after_id)
        self._auto_after_id = self.root.after(500, self.generate_now)

    def generate_now(self) -> None:
        if self._is_generating:
            self._rerun_requested = True
            return
        try:
            config = self._collect_config()
        except ValueError as exc:
            self._set_status(f"Invalid input: {exc}", error=True)
            return

        self._is_generating = True
        self.generate_btn.configure(state="disabled")
        self._set_status("Generating outputs...")
        self._update_viewport(config, reset_view=False)
        threading.Thread(target=self._worker_generate, args=(config,), daemon=True).start()

    def _worker_generate(self, config: Dict[str, Any]) -> None:
        try:
            result = generate_once(
                config,
                self.out_dir,
                self.renders_dir,
                timestamped=bool(self.timestamped_var.get()),
                blender_executable=(config.get("blender_executable") or None),
            )
            self._queue.put(("ok", result, config))
        except Exception as exc:
            self._queue.put(("err", str(exc), config))

    def _poll_queue(self) -> None:
        handled = False
        while True:
            try:
                kind, payload, cfg = self._queue.get_nowait()
            except queue.Empty:
                break
            handled = True
            if kind == "ok":
                assert isinstance(payload, dict)
                if cfg is not None:
                    self.config.update(cfg)
                    self._update_viewport(self.config, reset_view=False)
                paths = payload["paths"]
                self.plan_var.set(str(paths["plan"]))
                self.glb_var.set(str(paths["glb"]))
                self.summary_var.set(str(paths["summary"]))
                render_error = payload.get("render_error")
                if render_error:
                    self._set_status(f"Generation complete (render warning: {render_error})", error=True)
                else:
                    self._set_status("Generation complete.")
            else:
                self._set_status(f"Generation failed: {payload}", error=True)

        if handled:
            self._is_generating = False
            self.generate_btn.configure(state="normal")
            if self._rerun_requested:
                self._rerun_requested = False
                self.generate_now()

        self.root.after(150, self._poll_queue)

    def _refresh_source_mtimes(self) -> None:
        self._src_mtimes.clear()
        src_dir = self.config_path.parent
        for path in src_dir.glob("*.py"):
            try:
                self._src_mtimes[path] = path.stat().st_mtime
            except OSError:
                continue
        try:
            self._src_mtimes[self.config_path] = self.config_path.stat().st_mtime
        except OSError:
            pass

    def _poll_source_changes(self) -> None:
        changed = False
        src_dir = self.config_path.parent
        paths = list(src_dir.glob("*.py")) + [self.config_path]
        if set(paths) != set(self._src_mtimes.keys()):
            changed = True
        for path in paths:
            try:
                mtime = path.stat().st_mtime
            except OSError:
                continue
            if self._src_mtimes.get(path) != mtime:
                self._src_mtimes[path] = mtime
                changed = True

        if changed:
            if self.auto_var.get():
                self._set_status("Source changed, regenerating...")
                self.generate_now()
            else:
                self._set_status("Source changed. Click Generate Now, or enable auto regenerate.")

        self.root.after(int(self._src_scan_seconds * 1000), self._poll_source_changes)

    def _reset_view(self) -> None:
        cfg = self._try_config_from_inputs() or self.config
        self._update_viewport(cfg, reset_view=True)

    def _update_viewport(self, config: Dict[str, Any], reset_view: bool) -> None:
        try:
            plan = build_plan(config)
        except Exception:
            return

        self._viewport_points = (
            plan.master_triangle
            + plan.hex_vertices
            + ([pt for wing in plan.wing_polygons.values() for pt in wing])
            + (plan.courtyard_polygon if plan.courtyard_polygon else [])
        )
        if reset_view or self._vp_scale <= 0:
            self._vp_rotation = 0.0
            self._fit_view()
        self._draw_viewport(plan=plan)

    def _fit_view(self) -> None:
        if not self._viewport_points:
            return
        w = max(self.view_canvas.winfo_width(), 100)
        h = max(self.view_canvas.winfo_height(), 100)
        min_x = min(p[0] for p in self._viewport_points)
        max_x = max(p[0] for p in self._viewport_points)
        min_y = min(p[1] for p in self._viewport_points)
        max_y = max(p[1] for p in self._viewport_points)
        span_x = max(max_x - min_x, 1e-6)
        span_y = max(max_y - min_y, 1e-6)
        self._vp_scale = min((w - 60) / span_x, (h - 60) / span_y)
        self._vp_pan_x = 0.0
        self._vp_pan_y = 0.0

    def _world_to_screen(self, point: Point2D) -> Point2D:
        w = self.view_canvas.winfo_width()
        h = self.view_canvas.winfo_height()
        cx, cy = w * 0.5, h * 0.5
        x, y = point
        c, s = math.cos(self._vp_rotation), math.sin(self._vp_rotation)
        xr = c * x - s * y
        yr = s * x + c * y
        sx = cx + self._vp_pan_x + xr * self._vp_scale
        sy = cy + self._vp_pan_y - yr * self._vp_scale
        return (sx, sy)

    def _screen_to_world(self, sx: float, sy: float) -> Point2D:
        w = self.view_canvas.winfo_width()
        h = self.view_canvas.winfo_height()
        cx, cy = w * 0.5, h * 0.5
        xr = (sx - cx - self._vp_pan_x) / self._vp_scale
        yr = -(sy - cy - self._vp_pan_y) / self._vp_scale
        c, s = math.cos(self._vp_rotation), math.sin(self._vp_rotation)
        x = c * xr + s * yr
        y = -s * xr + c * yr
        return (x, y)

    def _draw_poly(self, points: List[Point2D], fill: str, outline: str, width: int = 1) -> None:
        if len(points) < 3:
            return
        coords: List[float] = []
        for p in points:
            sx, sy = self._world_to_screen(p)
            coords.extend((sx, sy))
        self.view_canvas.create_polygon(*coords, fill=fill, outline=outline, width=width)

    def _label(self, points: List[Point2D], text: str) -> None:
        if not points:
            return
        cx = sum(p[0] for p in points) / len(points)
        cy = sum(p[1] for p in points) / len(points)
        sx, sy = self._world_to_screen((cx, cy))
        self.view_canvas.create_text(sx, sy, text=text, fill="#1f2b38", font=("Segoe UI", 10, "bold"))

    def _draw_viewport(self, plan=None) -> None:
        self.view_canvas.delete("all")
        if plan is None:
            cfg = self._try_config_from_inputs() or self.config
            try:
                plan = build_plan(cfg)
            except Exception:
                return
        self._draw_poly(plan.wing_polygons["A"], fill="#dbe6f4", outline="#304d6d", width=1)
        self._draw_poly(plan.wing_polygons["B"], fill="#c8dbf0", outline="#304d6d", width=1)
        self._draw_poly(plan.wing_polygons["C"], fill="#dbe6f4", outline="#304d6d", width=1)
        self._draw_poly(plan.hex_vertices, fill="#f1f8ff", outline="#2f4f6f", width=2)
        if plan.courtyard_polygon:
            self._draw_poly(plan.courtyard_polygon, fill="#ececec", outline="#707070", width=1)
        self._draw_poly(plan.master_triangle, fill="", outline="#2d5d2a", width=2)

        if self.labels_var.get():
            self._label(plan.wing_polygons["A"], "A")
            self._label(plan.wing_polygons["B"], "B")
            self._label(plan.wing_polygons["C"], "C")
            self._label(plan.hex_vertices, "Atrium")
            if plan.courtyard_polygon:
                self._label(plan.courtyard_polygon, "Courtyard")

    def _on_pan_start(self, event) -> None:
        self._vp_pan_anchor = (event.x, event.y)

    def _on_pan_move(self, event) -> None:
        if self._vp_pan_anchor is None:
            return
        dx = event.x - self._vp_pan_anchor[0]
        dy = event.y - self._vp_pan_anchor[1]
        self._vp_pan_x += dx
        self._vp_pan_y += dy
        self._vp_pan_anchor = (event.x, event.y)
        self._draw_viewport()

    def _on_pan_end(self, _event) -> None:
        self._vp_pan_anchor = None

    def _on_rotate_start(self, event) -> None:
        self._vp_rotate_anchor_x = event.x

    def _on_rotate_move(self, event) -> None:
        if self._vp_rotate_anchor_x is None:
            return
        dx = event.x - self._vp_rotate_anchor_x
        self._vp_rotation += dx * 0.008
        self._vp_rotate_anchor_x = event.x
        self._draw_viewport()

    def _on_rotate_end(self, _event) -> None:
        self._vp_rotate_anchor_x = None

    def _on_wheel(self, event) -> None:
        if self._vp_scale <= 0:
            return
        if hasattr(event, "num") and event.num in (4, 5):
            zoom_in = event.num == 4
        else:
            zoom_in = event.delta > 0
        factor = 1.1 if zoom_in else 1.0 / 1.1

        world_before = self._screen_to_world(event.x, event.y)
        self._vp_scale = max(0.05, min(5000.0, self._vp_scale * factor))
        screen_after = self._world_to_screen(world_before)
        self._vp_pan_x += event.x - screen_after[0]
        self._vp_pan_y += event.y - screen_after[1]
        self._draw_viewport()

    def save_config(self) -> None:
        try:
            config = self._collect_config()
        except ValueError as exc:
            self._set_status(f"Cannot save config: {exc}", error=True)
            return
        self.config = config
        self.config_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
        self._refresh_source_mtimes()
        self._set_status(f"Saved config to {self.config_path}")

    def reload_config(self) -> None:
        self.config = _load_config(self.config_path)
        self._populate_from_config(self.config)
        self._refresh_source_mtimes()
        self._update_viewport(self.config, reset_view=True)
        self._set_status(f"Reloaded config from {self.config_path}")

    def launch_blender_live(self) -> None:
        glb_text = self.glb_var.get().strip()
        default_glb = self.out_dir / "massing_s23_d7.glb"
        candidate = Path(glb_text) if glb_text else default_glb
        glb_path = candidate if candidate.exists() else default_glb
        self.glb_var.set(str(glb_path))
        cfg = self._try_config_from_inputs() or self.config
        blender_exec = str(cfg.get("blender_executable", "")).strip() or None
        try:
            launch_live_reload(blender_exec, glb_path)
            self._set_status(f"Started Blender live reload (in-place) for {glb_path}")
        except Exception as exc:
            self._set_status(f"Could not start Blender live reload: {exc}", error=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Interactive UI for exploded hexagon parameters")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG_PATH))
    parser.add_argument("--out-dir", default=str(PROJECT_ROOT / "out"))
    parser.add_argument("--renders-dir", default=str(PROJECT_ROOT / "renders"))
    parser.add_argument("--timestamped", action="store_true")
    parser.add_argument("--test-run", action="store_true", help="Run one generation and exit (no window).")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config_path = Path(args.config)
    out_dir = Path(args.out_dir)
    renders_dir = Path(args.renders_dir)

    if args.test_run:
        cfg = _load_config(config_path)
        generate_once(
            cfg,
            out_dir,
            renders_dir,
            timestamped=args.timestamped,
            blender_executable=(cfg.get("blender_executable") or None),
        )
        return

    root = tk.Tk()
    app = ParametricUI(root, config_path=config_path, out_dir=out_dir, renders_dir=renders_dir)
    if args.timestamped:
        app.timestamped_var.set(True)
    root.mainloop()


if __name__ == "__main__":
    main()
