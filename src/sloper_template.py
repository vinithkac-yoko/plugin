"""
Sloper Template Manager.

Loads the JSON base sloper template, applies it to CLO3D (creating all panels,
darts, stitches, and seam allowances), and provides a live snapshot of the
current sloper state that can be fed to the AI brain as context.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from config.settings import TEMPLATES_DIR, DEFAULT_SEAM_ALLOWANCE_MM
from src.clo3d_api import CLO3DApi, Point2D

logger = logging.getLogger(__name__)

_DEFAULT_TEMPLATE = TEMPLATES_DIR / "base_sloper.json"


class SlopeTemplateManager:
    """
    Manages loading and applying the base sloper template to CLO3D.

    Usage::

        mgr = SlopeTemplateManager(api)
        mgr.load()      # loads from default JSON template
        mgr.apply()     # sends all panels / stitches to CLO3D
        state = mgr.get_state()   # returns dict for AI context
    """

    def __init__(
        self,
        api: CLO3DApi,
        template_path: Path | None = None,
    ) -> None:
        self._api = api
        self._template_path = template_path or _DEFAULT_TEMPLATE
        self._template: dict[str, Any] = {}
        self._applied = False

    # ── Public API ────────────────────────────────────────────────────────────

    def load(self, template_path: Path | None = None) -> None:
        """Load template JSON from disk."""
        path = template_path or self._template_path
        if not path.exists():
            raise FileNotFoundError(f"Sloper template not found: {path}")
        with path.open(encoding="utf-8") as fh:
            self._template = json.load(fh)
        logger.info("Sloper template loaded from %s", path)
        self._applied = False

    def apply(self) -> None:
        """
        Instantiate the template inside CLO3D:
          1. Set avatar measurements.
          2. Create all pattern panels with correct vertices.
          3. Add darts to each panel.
          4. Set seam allowances.
          5. Set grain lines.
          6. Apply stitches between panels.
        """
        if not self._template:
            raise RuntimeError("Call load() before apply().")

        logger.info("Applying base sloper template to CLO3D…")

        self._apply_avatar()
        self._apply_panels()
        self._apply_stitches()

        self._applied = True
        logger.info("Base sloper applied successfully.")

    def get_state(self) -> dict[str, Any]:
        """
        Return a structured dict describing the current sloper suitable for
        inclusion as context in the AI brain's first message.
        """
        if not self._template:
            return {}

        state: dict[str, Any] = {
            "avatar": self._template.get("avatar", {}),
            "panels": [],
        }

        for panel in self._template.get("panels", []):
            state["panels"].append({
                "name": panel["name"],
                "vertex_count": len(panel.get("vertices", [])),
                "dart_count": len(panel.get("darts", [])),
                "darts": [
                    {
                        "label": d.get("label", ""),
                        "edge_index": d["edge_index"],
                        "position_mm": d["position_mm"],
                        "width_mm": d["width_mm"],
                        "length_mm": d["length_mm"],
                    }
                    for d in panel.get("darts", [])
                ],
                "seam_allowances": panel.get("seam_allowances", {}),
                "grain_line_angle_deg": panel.get("grain_line_angle_deg", 0),
            })

        state["stitches"] = self._template.get("stitches", [])
        return state

    def get_panel_names(self) -> list[str]:
        """Return the names of all panels defined in the template."""
        return [p["name"] for p in self._template.get("panels", [])]

    @property
    def is_applied(self) -> bool:
        return self._applied

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _apply_avatar(self) -> None:
        avatar = self._template.get("avatar", {})
        measurements = avatar.get("measurements", {})
        for key, value_mm in measurements.items():
            self._api.set_avatar_measurement(key, float(value_mm))

    def _apply_panels(self) -> None:
        for panel_data in self._template.get("panels", []):
            name = panel_data["name"]
            raw_vertices = panel_data.get("vertices", [])
            vertices = [Point2D(x=float(v[0]), y=float(v[1])) for v in raw_vertices]

            # Create the panel
            self._api.add_panel(name, vertices)

            # Add darts
            for i, dart in enumerate(panel_data.get("darts", [])):
                self._api.add_dart(
                    panel_name=name,
                    edge_index=dart["edge_index"],
                    position_mm=float(dart["position_mm"]),
                    width_mm=float(dart["width_mm"]),
                    length_mm=float(dart["length_mm"]),
                )

            # Seam allowances
            sa_data = panel_data.get("seam_allowances", {})
            default_sa = float(sa_data.get("default_mm", DEFAULT_SEAM_ALLOWANCE_MM))
            self._api.set_all_seam_allowances(name, default_sa)

            # Hem — last edge gets a different allowance when specified
            hem_sa = sa_data.get("hem_mm")
            if hem_sa is not None:
                # Convention: hem = last edge (highest index)
                edge_count = len(raw_vertices)  # edge count == vertex count for polygons
                self._api.set_seam_allowance(name, edge_count - 1, float(hem_sa))

            # Grain line
            angle = float(panel_data.get("grain_line_angle_deg", 0))
            self._api.set_grain_line(name, angle)

    def _apply_stitches(self) -> None:
        for stitch in self._template.get("stitches", []):
            self._api.stitch_edges(
                panel_a=stitch["panel_a"],
                edge_a=stitch["edge_a"],
                panel_b=stitch["panel_b"],
                edge_b=stitch["edge_b"],
                reversed_b=stitch.get("reversed_b", False),
            )
