"""
AI Brain — VLA model interface (hardcoded stub).

This module defines the interface that any VLA (Vision-Language-Action) model
must satisfy to drive the CLO3D action loop.  The hardcoded stub below emits a
realistic sequence of actions so the rest of the pipeline can be developed and
tested end-to-end without a live model.

To plug in your proprietary VLA model, replace the body of
VLAModelStub.generate_actions() (or subclass AIBrain) and keep the same
generator signature:

    def generate_actions(
        self,
        prompt: str,
        image_path: str | None = None,
        sloper_state: dict | None = None,
    ) -> Generator[dict, None, None]:
        ...

Each yielded dict must follow the action schema:
    {
        "action": "<action_type>",
        "params": { ... },
        "reasoning": "<one sentence>",
        "done": False          # True only on the final action
    }
"""

from __future__ import annotations

import logging
from typing import Generator

logger = logging.getLogger(__name__)


# ── Hardcoded action sequences ────────────────────────────────────────────────
# Each entry in this list is a complete action dict the executor will run.
# Swap / extend these to simulate different design scenarios while your VLA
# model is under development.

_HARDCODED_ACTIONS: list[dict] = [
    # ── 1. Fit avatar to a standard size-M ───────────────────────────────────
    {
        "action": "set_avatar_measurement",
        "params": {"measurement": "bust",  "value_mm": 920},
        "reasoning": "Set bust to size-M standard (920 mm).",
        "done": False,
    },
    {
        "action": "set_avatar_measurement",
        "params": {"measurement": "waist", "value_mm": 720},
        "reasoning": "Set waist to size-M standard (720 mm).",
        "done": False,
    },
    {
        "action": "set_avatar_measurement",
        "params": {"measurement": "hip",   "value_mm": 980},
        "reasoning": "Set hip to size-M standard (980 mm).",
        "done": False,
    },

    # ── 2. Remove sleeves (sleeveless design) ─────────────────────────────────
    {
        "action": "delete_panel",
        "params": {"panel_name": "Sleeve"},
        "reasoning": "Design is sleeveless — remove the sleeve panel.",
        "done": False,
    },

    # ── 3. Widen the skirt panels for an A-line flare ─────────────────────────
    {
        "action": "scale_panel",
        "params": {"panel_name": "Front Skirt", "scale_x": 1.25, "scale_y": 1.0},
        "reasoning": "Scale front skirt width ×1.25 to create A-line silhouette.",
        "done": False,
    },
    {
        "action": "scale_panel",
        "params": {"panel_name": "Back Skirt",  "scale_x": 1.25, "scale_y": 1.0},
        "reasoning": "Mirror the A-line flare on the back skirt panel.",
        "done": False,
    },

    # ── 4. Deepen the V-neckline on front bodice ──────────────────────────────
    # Point 0 = top-left (CF neck), point 1 = top-right (shoulder)
    # Move CF neck point down by 60 mm to create a deep V
    {
        "action": "move_panel_point",
        "params": {
            "panel_name":  "Front Bodice",
            "point_index": 0,
            "dx": 0,
            "dy": 60,
        },
        "reasoning": "Drop CF neck point 60 mm to form a deep V-neckline.",
        "done": False,
    },

    # ── 5. Raise the empire waist line ────────────────────────────────────────
    # Shorten the bodice by moving the hem points up 40 mm
    {
        "action": "move_panel_point",
        "params": {
            "panel_name":  "Front Bodice",
            "point_index": 9,
            "dx": 0,
            "dy": -40,
        },
        "reasoning": "Raise front bodice hem 40 mm to create an empire waist.",
        "done": False,
    },
    {
        "action": "move_panel_point",
        "params": {
            "panel_name":  "Back Bodice",
            "point_index": 9,
            "dx": 0,
            "dy": -40,
        },
        "reasoning": "Raise back bodice hem 40 mm to match empire waist.",
        "done": False,
    },

    # ── 6. Increase bust dart for more shape ──────────────────────────────────
    {
        "action": "modify_dart",
        "params": {
            "panel_name":  "Front Bodice",
            "dart_index":  0,
            "width_mm":    28,
            "length_mm":   90,
        },
        "reasoning": "Widen bust dart to 28 mm for a more fitted bodice.",
        "done": False,
    },

    # ── 7. Set fabric colour (light yellow sundress) ──────────────────────────
    {
        "action": "set_fabric_color",
        "params": {"panel_name": "Front Bodice", "r": 255, "g": 236, "b": 120, "a": 255},
        "reasoning": "Apply a warm yellow fabric colour to the front bodice.",
        "done": False,
    },
    {
        "action": "set_fabric_color",
        "params": {"panel_name": "Back Bodice",  "r": 255, "g": 236, "b": 120, "a": 255},
        "reasoning": "Match fabric colour on back bodice.",
        "done": False,
    },
    {
        "action": "set_fabric_color",
        "params": {"panel_name": "Front Skirt",  "r": 255, "g": 236, "b": 120, "a": 255},
        "reasoning": "Match fabric colour on front skirt.",
        "done": False,
    },
    {
        "action": "set_fabric_color",
        "params": {"panel_name": "Back Skirt",   "r": 255, "g": 236, "b": 120, "a": 255},
        "reasoning": "Match fabric colour on back skirt.",
        "done": False,
    },

    # ── 8. Set hem allowance on skirts ────────────────────────────────────────
    {
        "action": "set_seam_allowance",
        "params": {"panel_name": "Front Skirt", "edge_index": 4, "allowance_mm": 30},
        "reasoning": "Set a 30 mm hem allowance on the front skirt.",
        "done": False,
    },
    {
        "action": "set_seam_allowance",
        "params": {"panel_name": "Back Skirt",  "edge_index": 4, "allowance_mm": 30},
        "reasoning": "Match 30 mm hem allowance on the back skirt.",
        "done": False,
    },

    # ── 9. Simulate ───────────────────────────────────────────────────────────
    {
        "action": "run_simulation",
        "params": {"quality": "normal"},
        "reasoning": "Drape the garment to validate the final silhouette.",
        "done": False,
    },

    # ── 10. Done ──────────────────────────────────────────────────────────────
    {
        "action": "design_complete",
        "params": {},
        "reasoning": "All design actions applied — A-line sundress with V-neckline complete.",
        "done": True,
    },
]


# ── AIBrain (stub) ────────────────────────────────────────────────────────────

class AIBrain:
    """
    Stub AI brain that replays _HARDCODED_ACTIONS.

    Replace generate_actions() with a call to your proprietary VLA model
    while keeping the same generator interface.
    """

    def generate_actions(
        self,
        prompt: str,
        image_path: str | None = None,
        sloper_state: dict | None = None,
    ) -> Generator[dict, None, None]:
        """
        Yield one action dict at a time.

        Args:
            prompt:       User design description (passed to VLA model).
            image_path:   Optional path to a reference image.
            sloper_state: Current sloper state dict for context.

        Yields:
            Action dicts conforming to the CLO3D action schema.
        """
        logger.info(
            "AIBrain (stub) — replaying %d hardcoded actions for prompt: %r",
            len(_HARDCODED_ACTIONS),
            prompt[:80],
        )

        for i, action in enumerate(_HARDCODED_ACTIONS, start=1):
            logger.info(
                "Action %d/%d: %s — %s",
                i, len(_HARDCODED_ACTIONS),
                action["action"],
                action.get("reasoning", ""),
            )
            yield action
            if action.get("done"):
                break

    def reset(self) -> None:
        """No-op — stub has no conversation state."""
