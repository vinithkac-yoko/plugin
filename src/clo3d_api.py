"""
CLO3D Python API wrapper.

All CLO3D interactions are centralised here so the rest of the plugin never
touches the raw `clo` module directly.  When running outside of CLO3D (e.g.
during unit-tests) every public method is a no-op / returns a stub, thanks to
the _StubClo fallback defined at the bottom of this file.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

# ── Try to import the real CLO3D Python module ────────────────────────────────
try:
    import clo  # type: ignore[import]
    _CLO_AVAILABLE = True
    logger.info("CLO3D Python API loaded successfully.")
except ImportError:
    clo = None  # type: ignore[assignment]
    _CLO_AVAILABLE = False
    logger.warning(
        "CLO3D Python API ('clo' module) not found. "
        "Running in STUB mode — no real garment will be modified."
    )


# ── Dataclasses used throughout the plugin ────────────────────────────────────

@dataclass
class Point2D:
    x: float
    y: float

    def __repr__(self) -> str:
        return f"Point2D({self.x:.2f}, {self.y:.2f})"


@dataclass
class PatternPanel:
    """Represents a single pattern panel (e.g. 'Front Bodice')."""
    name: str
    panel_id: Any = None          # CLO internal handle
    points: list[Point2D] = field(default_factory=list)


@dataclass
class DartInfo:
    panel_name: str
    dart_id: Any = None
    width_mm: float = 0.0
    length_mm: float = 0.0
    position_mm: float = 0.0     # distance from reference edge


@dataclass
class SeamInfo:
    panel_name: str
    edge_index: int
    allowance_mm: float = 10.0


# ── CLO3D wrapper ─────────────────────────────────────────────────────────────

class CLO3DApi:
    """
    Thin wrapper around CLO3D's `clo` Python module.

    Every method logs what it is doing and falls back gracefully when the real
    CLO3D environment is unavailable.
    """

    # ── Garment / project ─────────────────────────────────────────────────────

    def new_project(self) -> None:
        """Create a blank CLO3D project."""
        logger.info("[CLO3D] new_project()")
        if _CLO_AVAILABLE:
            clo.NewProject()

    def open_project(self, path: str) -> None:
        """Open an existing .zprj file."""
        logger.info("[CLO3D] open_project(%s)", path)
        if _CLO_AVAILABLE:
            clo.OpenProject(path)

    def save_project(self, path: str) -> None:
        """Save the current project."""
        logger.info("[CLO3D] save_project(%s)", path)
        if _CLO_AVAILABLE:
            clo.SaveProject(path)

    def export_obj(self, path: str) -> None:
        """Export the 3-D simulation as an OBJ file."""
        logger.info("[CLO3D] export_obj(%s)", path)
        if _CLO_AVAILABLE:
            clo.ExportOBJ(path)

    # ── Pattern panels ────────────────────────────────────────────────────────

    def get_all_panels(self) -> list[PatternPanel]:
        """Return a list of all pattern panels in the current project."""
        logger.info("[CLO3D] get_all_panels()")
        if not _CLO_AVAILABLE:
            return []
        panels = []
        for pid in clo.GetAllPatternIDs():
            name = clo.GetPatternName(pid)
            panels.append(PatternPanel(name=name, panel_id=pid))
        return panels

    def get_panel_by_name(self, name: str) -> PatternPanel | None:
        """Return the first panel whose name matches (case-insensitive)."""
        for p in self.get_all_panels():
            if p.name.lower() == name.lower():
                return p
        logger.warning("[CLO3D] Panel '%s' not found.", name)
        return None

    def add_panel(self, name: str, vertices: list[Point2D]) -> PatternPanel:
        """
        Create a new flat pattern panel from a list of 2-D vertices (mm).

        The vertices define the outer boundary of the panel in order.
        """
        logger.info("[CLO3D] add_panel('%s', %d vertices)", name, len(vertices))
        panel = PatternPanel(name=name, points=vertices)
        if _CLO_AVAILABLE:
            coords = []
            for pt in vertices:
                coords.extend([pt.x, pt.y])
            pid = clo.AddPattern(name, coords)
            panel.panel_id = pid
        return panel

    def duplicate_panel(self, source_name: str, new_name: str) -> PatternPanel | None:
        """Duplicate an existing panel under a new name."""
        logger.info("[CLO3D] duplicate_panel('%s' -> '%s')", source_name, new_name)
        src = self.get_panel_by_name(source_name)
        if src is None:
            return None
        panel = PatternPanel(name=new_name)
        if _CLO_AVAILABLE:
            pid = clo.DuplicatePattern(src.panel_id)
            clo.SetPatternName(pid, new_name)
            panel.panel_id = pid
        return panel

    def delete_panel(self, name: str) -> bool:
        """Delete a panel by name. Returns True if the panel existed."""
        logger.info("[CLO3D] delete_panel('%s')", name)
        panel = self.get_panel_by_name(name)
        if panel is None:
            return False
        if _CLO_AVAILABLE:
            clo.DeletePattern(panel.panel_id)
        return True

    # ── Panel geometry ────────────────────────────────────────────────────────

    def move_panel_point(
        self, panel_name: str, point_index: int, dx: float, dy: float
    ) -> None:
        """
        Translate a single boundary point of a panel by (dx, dy) in mm.

        point_index follows CLO3D's 0-based vertex ordering.
        """
        logger.info(
            "[CLO3D] move_panel_point('%s', idx=%d, dx=%.2f, dy=%.2f)",
            panel_name, point_index, dx, dy,
        )
        panel = self.get_panel_by_name(panel_name)
        if panel is None or not _CLO_AVAILABLE:
            return
        clo.MovePatternPoint(panel.panel_id, point_index, dx, dy)

    def set_panel_point_position(
        self, panel_name: str, point_index: int, x: float, y: float
    ) -> None:
        """Set a boundary point to an absolute (x, y) position (mm)."""
        logger.info(
            "[CLO3D] set_panel_point_position('%s', idx=%d, x=%.2f, y=%.2f)",
            panel_name, point_index, x, y,
        )
        panel = self.get_panel_by_name(panel_name)
        if panel is None or not _CLO_AVAILABLE:
            return
        clo.SetPatternPointPosition(panel.panel_id, point_index, x, y)

    def scale_panel(self, panel_name: str, scale_x: float, scale_y: float) -> None:
        """
        Uniformly or non-uniformly scale a panel around its centroid.

        scale_x=1.0, scale_y=1.0 → no change.
        """
        logger.info(
            "[CLO3D] scale_panel('%s', sx=%.3f, sy=%.3f)", panel_name, scale_x, scale_y
        )
        panel = self.get_panel_by_name(panel_name)
        if panel is None or not _CLO_AVAILABLE:
            return
        clo.ScalePattern(panel.panel_id, scale_x, scale_y)

    def rotate_panel(self, panel_name: str, angle_deg: float) -> None:
        """Rotate a pattern panel by angle_deg degrees around its centroid."""
        logger.info("[CLO3D] rotate_panel('%s', %.2f°)", panel_name, angle_deg)
        panel = self.get_panel_by_name(panel_name)
        if panel is None or not _CLO_AVAILABLE:
            return
        clo.RotatePattern(panel.panel_id, angle_deg)

    # ── Darts ─────────────────────────────────────────────────────────────────

    def add_dart(
        self,
        panel_name: str,
        edge_index: int,
        position_mm: float,
        width_mm: float,
        length_mm: float,
    ) -> DartInfo:
        """
        Add a dart to a panel edge.

        Args:
            panel_name:   Target panel name.
            edge_index:   Which boundary edge (0-based) to attach the dart to.
            position_mm:  Distance along that edge from its start vertex (mm).
            width_mm:     Opening width of the dart (mm).
            length_mm:    Depth of the dart (mm).
        """
        logger.info(
            "[CLO3D] add_dart('%s', edge=%d, pos=%.1f, w=%.1f, l=%.1f)",
            panel_name, edge_index, position_mm, width_mm, length_mm,
        )
        dart = DartInfo(
            panel_name=panel_name,
            width_mm=width_mm,
            length_mm=length_mm,
            position_mm=position_mm,
        )
        panel = self.get_panel_by_name(panel_name)
        if panel is None or not _CLO_AVAILABLE:
            return dart
        dart_id = clo.AddDart(
            panel.panel_id, edge_index, position_mm, width_mm, length_mm
        )
        dart.dart_id = dart_id
        return dart

    def modify_dart(
        self,
        panel_name: str,
        dart_index: int,
        width_mm: float | None = None,
        length_mm: float | None = None,
    ) -> None:
        """
        Change the width and/or length of an existing dart.

        dart_index is the 0-based index among darts on that panel.
        """
        logger.info(
            "[CLO3D] modify_dart('%s', idx=%d, w=%s, l=%s)",
            panel_name, dart_index, width_mm, length_mm,
        )
        panel = self.get_panel_by_name(panel_name)
        if panel is None or not _CLO_AVAILABLE:
            return
        if width_mm is not None:
            clo.SetDartWidth(panel.panel_id, dart_index, width_mm)
        if length_mm is not None:
            clo.SetDartLength(panel.panel_id, dart_index, length_mm)

    def delete_dart(self, panel_name: str, dart_index: int) -> None:
        """Remove a dart from a panel."""
        logger.info("[CLO3D] delete_dart('%s', idx=%d)", panel_name, dart_index)
        panel = self.get_panel_by_name(panel_name)
        if panel is None or not _CLO_AVAILABLE:
            return
        clo.DeleteDart(panel.panel_id, dart_index)

    # ── Seam allowances ───────────────────────────────────────────────────────

    def set_seam_allowance(
        self, panel_name: str, edge_index: int, allowance_mm: float
    ) -> None:
        """Set the seam allowance on a specific panel edge."""
        logger.info(
            "[CLO3D] set_seam_allowance('%s', edge=%d, %.1f mm)",
            panel_name, edge_index, allowance_mm,
        )
        panel = self.get_panel_by_name(panel_name)
        if panel is None or not _CLO_AVAILABLE:
            return
        clo.SetSeamAllowance(panel.panel_id, edge_index, allowance_mm)

    def set_all_seam_allowances(self, panel_name: str, allowance_mm: float) -> None:
        """Apply the same seam allowance to every edge of a panel."""
        logger.info(
            "[CLO3D] set_all_seam_allowances('%s', %.1f mm)", panel_name, allowance_mm
        )
        panel = self.get_panel_by_name(panel_name)
        if panel is None or not _CLO_AVAILABLE:
            return
        edge_count = clo.GetPatternEdgeCount(panel.panel_id)
        for i in range(edge_count):
            clo.SetSeamAllowance(panel.panel_id, i, allowance_mm)

    # ── Fabric / material ─────────────────────────────────────────────────────

    def set_fabric(self, panel_name: str, fabric_name: str) -> None:
        """Assign a fabric from the CLO library to a panel."""
        logger.info("[CLO3D] set_fabric('%s', '%s')", panel_name, fabric_name)
        panel = self.get_panel_by_name(panel_name)
        if panel is None or not _CLO_AVAILABLE:
            return
        clo.SetFabric(panel.panel_id, fabric_name)

    def set_fabric_color(
        self, panel_name: str, r: int, g: int, b: int, a: int = 255
    ) -> None:
        """Set fabric colour (0-255 per channel)."""
        logger.info(
            "[CLO3D] set_fabric_color('%s', r=%d, g=%d, b=%d, a=%d)",
            panel_name, r, g, b, a,
        )
        panel = self.get_panel_by_name(panel_name)
        if panel is None or not _CLO_AVAILABLE:
            return
        clo.SetFabricColor(panel.panel_id, r, g, b, a)

    # ── Stitching ─────────────────────────────────────────────────────────────

    def stitch_edges(
        self,
        panel_a: str,
        edge_a: int,
        panel_b: str,
        edge_b: int,
        reversed_b: bool = False,
    ) -> None:
        """
        Stitch two panel edges together.

        Args:
            panel_a / edge_a:  First panel name + edge index.
            panel_b / edge_b:  Second panel name + edge index.
            reversed_b:        Whether to reverse the direction of edge_b.
        """
        logger.info(
            "[CLO3D] stitch_edges('%s'[%d] <-> '%s'[%d], rev=%s)",
            panel_a, edge_a, panel_b, edge_b, reversed_b,
        )
        pa = self.get_panel_by_name(panel_a)
        pb = self.get_panel_by_name(panel_b)
        if pa is None or pb is None or not _CLO_AVAILABLE:
            return
        clo.StitchPatternEdges(pa.panel_id, edge_a, pb.panel_id, edge_b, reversed_b)

    def remove_stitch(self, panel_a: str, edge_a: int) -> None:
        """Remove the stitch from a panel edge."""
        logger.info("[CLO3D] remove_stitch('%s'[%d])", panel_a, edge_a)
        pa = self.get_panel_by_name(panel_a)
        if pa is None or not _CLO_AVAILABLE:
            return
        clo.RemoveStitch(pa.panel_id, edge_a)

    # ── Avatar / sizing ───────────────────────────────────────────────────────

    def set_avatar_measurement(self, measurement: str, value_mm: float) -> None:
        """
        Adjust a body measurement on the active avatar.

        Common measurements: 'bust', 'waist', 'hip', 'shoulder_width',
        'neck', 'back_length', 'sleeve_length', 'inseam'.
        """
        logger.info(
            "[CLO3D] set_avatar_measurement('%s', %.1f mm)", measurement, value_mm
        )
        if not _CLO_AVAILABLE:
            return
        clo.SetAvatarMeasurement(measurement, value_mm)

    # ── Simulation ────────────────────────────────────────────────────────────

    def run_simulation(self, quality: str = "normal") -> None:
        """
        Drape / simulate the garment.

        quality: 'draft' | 'normal' | 'high'
        """
        logger.info("[CLO3D] run_simulation(quality='%s')", quality)
        if not _CLO_AVAILABLE:
            return
        quality_map = {"draft": 0, "normal": 1, "high": 2}
        clo.Simulate(quality_map.get(quality, 1))

    def reset_simulation(self) -> None:
        """Reset the garment to its flat-pattern state."""
        logger.info("[CLO3D] reset_simulation()")
        if not _CLO_AVAILABLE:
            return
        clo.ResetSimulation()

    # ── Grading ───────────────────────────────────────────────────────────────

    def apply_grade(self, panel_name: str, size: str) -> None:
        """Grade a panel to a standard size ('XS','S','M','L','XL','XXL')."""
        logger.info("[CLO3D] apply_grade('%s', '%s')", panel_name, size)
        panel = self.get_panel_by_name(panel_name)
        if panel is None or not _CLO_AVAILABLE:
            return
        clo.ApplyGrade(panel.panel_id, size)

    # ── Notches / grain lines ─────────────────────────────────────────────────

    def add_notch(
        self, panel_name: str, edge_index: int, position_mm: float
    ) -> None:
        """Add a sewing notch at position_mm along an edge."""
        logger.info(
            "[CLO3D] add_notch('%s', edge=%d, pos=%.1f)", panel_name, edge_index, position_mm
        )
        panel = self.get_panel_by_name(panel_name)
        if panel is None or not _CLO_AVAILABLE:
            return
        clo.AddNotch(panel.panel_id, edge_index, position_mm)

    def set_grain_line(
        self, panel_name: str, angle_deg: float
    ) -> None:
        """Set the grain-line angle (degrees from vertical)."""
        logger.info("[CLO3D] set_grain_line('%s', %.1f°)", panel_name, angle_deg)
        panel = self.get_panel_by_name(panel_name)
        if panel is None or not _CLO_AVAILABLE:
            return
        clo.SetGrainLine(panel.panel_id, angle_deg)

    # ── Utility ───────────────────────────────────────────────────────────────

    def is_available(self) -> bool:
        """Return True when the real CLO3D API is present."""
        return _CLO_AVAILABLE

    def refresh_ui(self) -> None:
        """Force CLO3D to redraw its UI."""
        if _CLO_AVAILABLE:
            clo.RefreshUI()
