"""
Action Executor — translates AI-generated action dicts into CLO3D API calls.

The AI brain emits one JSON action at a time.  This module:
  1. Validates the action schema.
  2. Dispatches it to the correct CLO3DApi method.
  3. Records an execution log for debugging / replay.

Every handler is a private method named _handle_<action_type>.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

from src.clo3d_api import CLO3DApi, Point2D

logger = logging.getLogger(__name__)


# ── Result objects ────────────────────────────────────────────────────────────

@dataclass
class ActionResult:
    """Outcome of executing a single AI action."""
    action: str
    params: dict
    success: bool
    error: str = ""
    elapsed_ms: float = 0.0

    def __str__(self) -> str:
        status = "OK" if self.success else f"FAIL({self.error})"
        return f"[{status}] {self.action} {self.params} ({self.elapsed_ms:.0f} ms)"


@dataclass
class ExecutionLog:
    """Full log of all actions executed in a single design session."""
    results: list[ActionResult] = field(default_factory=list)

    def append(self, result: ActionResult) -> None:
        self.results.append(result)
        logger.info(str(result))

    @property
    def success_count(self) -> int:
        return sum(1 for r in self.results if r.success)

    @property
    def failure_count(self) -> int:
        return sum(1 for r in self.results if not r.success)

    def summary(self) -> str:
        total = len(self.results)
        return (
            f"Executed {total} actions: "
            f"{self.success_count} succeeded, {self.failure_count} failed."
        )


# ── ActionExecutor ────────────────────────────────────────────────────────────

class ActionExecutor:
    """
    Dispatches AI-generated action dicts to the CLO3D API.

    Usage::

        api = CLO3DApi()
        executor = ActionExecutor(api)
        for action in brain.generate_actions(...):
            result = executor.execute(action)
    """

    def __init__(self, api: CLO3DApi) -> None:
        self._api = api
        self.log = ExecutionLog()

        # Dispatch table: action_type → handler method
        self._dispatch: dict[str, Any] = {
            # Panel management
            "add_panel":            self._handle_add_panel,
            "duplicate_panel":      self._handle_duplicate_panel,
            "delete_panel":         self._handle_delete_panel,
            # Geometry
            "move_panel_point":              self._handle_move_panel_point,
            "set_panel_point_position":      self._handle_set_panel_point_position,
            "scale_panel":                   self._handle_scale_panel,
            "rotate_panel":                  self._handle_rotate_panel,
            # Darts
            "add_dart":             self._handle_add_dart,
            "modify_dart":          self._handle_modify_dart,
            "delete_dart":          self._handle_delete_dart,
            # Seam allowances
            "set_seam_allowance":       self._handle_set_seam_allowance,
            "set_all_seam_allowances":  self._handle_set_all_seam_allowances,
            # Fabric
            "set_fabric":           self._handle_set_fabric,
            "set_fabric_color":     self._handle_set_fabric_color,
            # Stitching
            "stitch_edges":         self._handle_stitch_edges,
            "remove_stitch":        self._handle_remove_stitch,
            # Avatar
            "set_avatar_measurement": self._handle_set_avatar_measurement,
            # Simulation
            "run_simulation":       self._handle_run_simulation,
            "reset_simulation":     self._handle_reset_simulation,
            # Grading
            "apply_grade":          self._handle_apply_grade,
            # Notches / grain
            "add_notch":            self._handle_add_notch,
            "set_grain_line":       self._handle_set_grain_line,
            # Terminal
            "design_complete":      self._handle_design_complete,
        }

    # ── Public API ────────────────────────────────────────────────────────────

    def execute(self, action: dict) -> ActionResult:
        """
        Execute a single AI action dict.

        Returns:
            ActionResult with success/error info.
        """
        action_type = action.get("action", "")
        params = action.get("params", {})

        handler = self._dispatch.get(action_type)
        if handler is None:
            result = ActionResult(
                action=action_type,
                params=params,
                success=False,
                error=f"Unknown action type '{action_type}'",
            )
            self.log.append(result)
            return result

        t0 = time.perf_counter()
        try:
            handler(**params)
            success = True
            error = ""
        except TypeError as exc:
            # Wrong params passed by the AI
            success = False
            error = f"Parameter error: {exc}"
            logger.error("Action '%s' parameter error: %s", action_type, exc)
        except Exception as exc:  # noqa: BLE001
            success = False
            error = str(exc)
            logger.error("Action '%s' raised: %s", action_type, exc)
        elapsed_ms = (time.perf_counter() - t0) * 1000

        # Refresh CLO3D UI after every action so the user sees incremental progress
        if success and self._api.is_available():
            self._api.refresh_ui()

        result = ActionResult(
            action=action_type,
            params=params,
            success=success,
            error=error,
            elapsed_ms=elapsed_ms,
        )
        self.log.append(result)
        return result

    def reset_log(self) -> None:
        self.log = ExecutionLog()

    # ── Handlers ──────────────────────────────────────────────────────────────
    # Each handler signature must match the params schema defined in ai_brain.py.

    # Panel management ─────────────────────────────────────────────────────────

    def _handle_add_panel(self, name: str, vertices: list[list[float]]) -> None:
        points = [Point2D(x=v[0], y=v[1]) for v in vertices]
        self._api.add_panel(name, points)

    def _handle_duplicate_panel(self, source_name: str, new_name: str) -> None:
        self._api.duplicate_panel(source_name, new_name)

    def _handle_delete_panel(self, panel_name: str) -> None:
        self._api.delete_panel(panel_name)

    # Geometry ─────────────────────────────────────────────────────────────────

    def _handle_move_panel_point(
        self, panel_name: str, point_index: int, dx: float, dy: float
    ) -> None:
        self._api.move_panel_point(panel_name, point_index, dx, dy)

    def _handle_set_panel_point_position(
        self, panel_name: str, point_index: int, x: float, y: float
    ) -> None:
        self._api.set_panel_point_position(panel_name, point_index, x, y)

    def _handle_scale_panel(
        self, panel_name: str, scale_x: float, scale_y: float
    ) -> None:
        self._api.scale_panel(panel_name, scale_x, scale_y)

    def _handle_rotate_panel(self, panel_name: str, angle_deg: float) -> None:
        self._api.rotate_panel(panel_name, angle_deg)

    # Darts ────────────────────────────────────────────────────────────────────

    def _handle_add_dart(
        self,
        panel_name: str,
        edge_index: int,
        position_mm: float,
        width_mm: float,
        length_mm: float,
    ) -> None:
        self._api.add_dart(panel_name, edge_index, position_mm, width_mm, length_mm)

    def _handle_modify_dart(
        self,
        panel_name: str,
        dart_index: int,
        width_mm: float | None = None,
        length_mm: float | None = None,
    ) -> None:
        self._api.modify_dart(panel_name, dart_index, width_mm, length_mm)

    def _handle_delete_dart(self, panel_name: str, dart_index: int) -> None:
        self._api.delete_dart(panel_name, dart_index)

    # Seam allowances ─────────────────────────────────────────────────────────

    def _handle_set_seam_allowance(
        self, panel_name: str, edge_index: int, allowance_mm: float
    ) -> None:
        self._api.set_seam_allowance(panel_name, edge_index, allowance_mm)

    def _handle_set_all_seam_allowances(
        self, panel_name: str, allowance_mm: float
    ) -> None:
        self._api.set_all_seam_allowances(panel_name, allowance_mm)

    # Fabric ───────────────────────────────────────────────────────────────────

    def _handle_set_fabric(self, panel_name: str, fabric_name: str) -> None:
        self._api.set_fabric(panel_name, fabric_name)

    def _handle_set_fabric_color(
        self,
        panel_name: str,
        r: int,
        g: int,
        b: int,
        a: int = 255,
    ) -> None:
        self._api.set_fabric_color(panel_name, r, g, b, a)

    # Stitching ────────────────────────────────────────────────────────────────

    def _handle_stitch_edges(
        self,
        panel_a: str,
        edge_a: int,
        panel_b: str,
        edge_b: int,
        reversed_b: bool = False,
    ) -> None:
        self._api.stitch_edges(panel_a, edge_a, panel_b, edge_b, reversed_b)

    def _handle_remove_stitch(self, panel_a: str, edge_a: int) -> None:
        self._api.remove_stitch(panel_a, edge_a)

    # Avatar ───────────────────────────────────────────────────────────────────

    def _handle_set_avatar_measurement(
        self, measurement: str, value_mm: float
    ) -> None:
        self._api.set_avatar_measurement(measurement, value_mm)

    # Simulation ───────────────────────────────────────────────────────────────

    def _handle_run_simulation(self, quality: str = "normal") -> None:
        self._api.run_simulation(quality)

    def _handle_reset_simulation(self) -> None:
        self._api.reset_simulation()

    # Grading ──────────────────────────────────────────────────────────────────

    def _handle_apply_grade(self, panel_name: str, size: str) -> None:
        self._api.apply_grade(panel_name, size)

    # Notches / grain ──────────────────────────────────────────────────────────

    def _handle_add_notch(
        self, panel_name: str, edge_index: int, position_mm: float
    ) -> None:
        self._api.add_notch(panel_name, edge_index, position_mm)

    def _handle_set_grain_line(self, panel_name: str, angle_deg: float) -> None:
        self._api.set_grain_line(panel_name, angle_deg)

    # Terminal ─────────────────────────────────────────────────────────────────

    def _handle_design_complete(self) -> None:
        logger.info("Design complete signal received.")
