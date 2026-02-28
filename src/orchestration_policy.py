from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable, Literal


class ExecutionMode(str, Enum):
    PROCEDURAL_PYTHON = "procedural_python"
    IN_PLACE_BLENDER = "in_place_blender"
    HYBRID = "hybrid"


class ModelRoute(str, Enum):
    CODEX_GEOMETRY = "gpt-5.3-codex"
    CLAUDE_PLANNING = "claude-opus-4.6-fast"
    GEMINI_VISION = "gemini-3-pro-preview"


TaskKind = Literal["geometry", "planning", "coding", "validation", "visual", "texture"]


@dataclass(frozen=True)
class ChangeRequest:
    description: str
    affects_topology: bool = False
    needs_exact_dimensions: bool = False
    touches_many_objects: bool = False
    is_small_transform: bool = False


@dataclass(frozen=True)
class OrchestrationDecision:
    execution_mode: ExecutionMode
    primary_model: ModelRoute
    fallback_model: ModelRoute
    reason: str


PROCEDURAL_KEYWORDS = (
    "rebuild",
    "regenerate",
    "topology",
    "parametric",
    "offset",
    "boolean",
    "seam",
    "constraints",
    "equal length",
    "area",
    "validation",
)

IN_PLACE_KEYWORDS = (
    "move",
    "rotate",
    "raise",
    "lower",
    "nudge",
    "reposition",
    "quick tweak",
    "visual",
)


def choose_execution_mode(request: ChangeRequest) -> ExecutionMode:
    text = request.description.lower()
    if request.is_small_transform and not request.affects_topology:
        return ExecutionMode.IN_PLACE_BLENDER
    if (
        request.affects_topology
        or request.needs_exact_dimensions
        or request.touches_many_objects
        or any(token in text for token in PROCEDURAL_KEYWORDS)
    ):
        return ExecutionMode.PROCEDURAL_PYTHON
    if any(token in text for token in IN_PLACE_KEYWORDS):
        return ExecutionMode.IN_PLACE_BLENDER
    return ExecutionMode.HYBRID


def choose_primary_model(task_kind: TaskKind, explicit_values_from_python: bool) -> ModelRoute:
    if task_kind == "geometry" and not explicit_values_from_python:
        return ModelRoute.CODEX_GEOMETRY
    if task_kind in ("visual", "texture"):
        return ModelRoute.GEMINI_VISION
    return ModelRoute.CLAUDE_PLANNING


_ROTATION_ORDER = [
    ModelRoute.CODEX_GEOMETRY,
    ModelRoute.CLAUDE_PLANNING,
    ModelRoute.GEMINI_VISION,
]


def choose_model_with_fallback(
    task_kind: TaskKind,
    explicit_values_from_python: bool,
    failed_models: Iterable[ModelRoute] = (),
) -> tuple[ModelRoute, ModelRoute]:
    preferred = choose_primary_model(task_kind, explicit_values_from_python)
    failed = set(failed_models)
    # Build rotation: preferred first, then others in order
    rotation = [preferred] + [m for m in _ROTATION_ORDER if m != preferred]
    available = [m for m in rotation if m not in failed]
    if len(available) == 0:
        available = list(_ROTATION_ORDER)
    primary = available[0]
    fallback = available[1] if len(available) > 1 else available[0]
    return primary, fallback


def decide_orchestration(
    request: ChangeRequest,
    task_kind: TaskKind,
    explicit_values_from_python: bool,
    failed_models: Iterable[ModelRoute] = (),
) -> OrchestrationDecision:
    mode = choose_execution_mode(request)
    primary, fallback = choose_model_with_fallback(
        task_kind=task_kind,
        explicit_values_from_python=explicit_values_from_python,
        failed_models=failed_models,
    )
    reason = (
        f"mode={mode.value}; primary={primary.value}; "
        f"fallback={fallback.value}; explicit_values_from_python={explicit_values_from_python}"
    )
    return OrchestrationDecision(
        execution_mode=mode,
        primary_model=primary,
        fallback_model=fallback,
        reason=reason,
    )

