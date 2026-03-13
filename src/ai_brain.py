"""
AI Brain — Claude-powered design interpreter.

Given a user prompt (text and/or image) plus a description of the current
sloper state, this module drives a multi-turn conversation with Claude and
yields one structured CLO3D action at a time until the design is complete.

The model speaks a small, well-defined JSON "action language" so the
ActionExecutor can translate each action directly into CLO3D API calls.

Action schema (single action object):
{
  "action": "<action_type>",   // see ACTION_TYPES below
  "params": { ... },           // action-specific parameters
  "reasoning": "...",          // brief human-readable justification
  "done": false                // true only on the final message
}
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Generator

import anthropic

from config.settings import (
    ANTHROPIC_API_KEY,
    CLAUDE_MODEL,
    CLAUDE_MAX_TOKENS,
    MAX_ACTION_ROUNDS,
)

logger = logging.getLogger(__name__)

# ── Action vocabulary the model is allowed to emit ───────────────────────────
ACTION_TYPES = [
    # Panel management
    "add_panel",
    "duplicate_panel",
    "delete_panel",
    # Geometry
    "move_panel_point",
    "set_panel_point_position",
    "scale_panel",
    "rotate_panel",
    # Darts
    "add_dart",
    "modify_dart",
    "delete_dart",
    # Seam allowances
    "set_seam_allowance",
    "set_all_seam_allowances",
    # Fabric
    "set_fabric",
    "set_fabric_color",
    # Stitching
    "stitch_edges",
    "remove_stitch",
    # Avatar / sizing
    "set_avatar_measurement",
    # Simulation
    "run_simulation",
    "reset_simulation",
    # Grading
    "apply_grade",
    # Notches / grain lines
    "add_notch",
    "set_grain_line",
    # Special terminal action
    "design_complete",
]

# ── System prompt ─────────────────────────────────────────────────────────────
_SYSTEM_PROMPT = """You are an expert fashion designer and pattern-making AI assistant
integrated into CLO3D, a professional 3-D fashion design application.

Your role is to interpret a user's design intent (provided as text and/or an image)
and translate it into a precise, step-by-step sequence of CLO3D pattern-manipulation
actions, one action per response.

## Rules
1. Respond with EXACTLY ONE JSON object per turn — no prose, no markdown fences.
2. Each JSON object must conform to this schema:
   {
     "action": "<action_type>",
     "params": { ... },
     "reasoning": "<one sentence explaining why>",
     "done": false
   }
3. When the design is fully realised, emit:
   {
     "action": "design_complete",
     "params": {},
     "reasoning": "All requested design changes have been applied.",
     "done": true
   }
4. Valid action types and their required params:

   add_panel         → {"name": str, "vertices": [[x,y], ...]}
   duplicate_panel   → {"source_name": str, "new_name": str}
   delete_panel      → {"panel_name": str}

   move_panel_point  → {"panel_name": str, "point_index": int, "dx": float, "dy": float}
   set_panel_point_position → {"panel_name": str, "point_index": int, "x": float, "y": float}
   scale_panel       → {"panel_name": str, "scale_x": float, "scale_y": float}
   rotate_panel      → {"panel_name": str, "angle_deg": float}

   add_dart          → {"panel_name": str, "edge_index": int, "position_mm": float,
                         "width_mm": float, "length_mm": float}
   modify_dart       → {"panel_name": str, "dart_index": int,
                         "width_mm": float|null, "length_mm": float|null}
   delete_dart       → {"panel_name": str, "dart_index": int}

   set_seam_allowance     → {"panel_name": str, "edge_index": int, "allowance_mm": float}
   set_all_seam_allowances → {"panel_name": str, "allowance_mm": float}

   set_fabric        → {"panel_name": str, "fabric_name": str}
   set_fabric_color  → {"panel_name": str, "r": int, "g": int, "b": int, "a": int}

   stitch_edges      → {"panel_a": str, "edge_a": int,
                         "panel_b": str, "edge_b": int, "reversed_b": bool}
   remove_stitch     → {"panel_a": str, "edge_a": int}

   set_avatar_measurement → {"measurement": str, "value_mm": float}
     (measurements: bust, waist, hip, shoulder_width, neck,
                    back_length, sleeve_length, inseam)

   run_simulation    → {"quality": "draft"|"normal"|"high"}
   reset_simulation  → {}

   apply_grade       → {"panel_name": str, "size": str}
     (sizes: XS, S, M, L, XL, XXL)

   add_notch         → {"panel_name": str, "edge_index": int, "position_mm": float}
   set_grain_line    → {"panel_name": str, "angle_deg": float}

   design_complete   → {}

5. All measurements are in millimetres (mm) unless noted otherwise.
6. Think logically about which panels to modify for each design element
   (e.g. neckline → front/back bodice top edge, sleeve width → sleeve panel
   scale, waist suppression → side-seam points or darts, etc.).
7. Always end with run_simulation to drape the final garment, then
   design_complete.
"""


# ── AIBrain ───────────────────────────────────────────────────────────────────

class AIBrain:
    """
    Stateful conversation manager between the plugin and Claude.

    Usage::

        brain = AIBrain()
        for action in brain.generate_actions(prompt="...", image_path="..."):
            executor.execute(action)
    """

    def __init__(self) -> None:
        if not ANTHROPIC_API_KEY:
            raise ValueError(
                "ANTHROPIC_API_KEY is not set. "
                "Add it to your .env file or environment variables."
            )
        self._client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        self._history: list[dict] = []   # multi-turn conversation history

    # ── Public API ────────────────────────────────────────────────────────────

    def generate_actions(
        self,
        prompt: str,
        image_path: str | None = None,
        sloper_state: dict | None = None,
    ) -> Generator[dict, None, None]:
        """
        Drive a multi-turn conversation and yield one parsed action dict per
        iteration until `done` is True or MAX_ACTION_ROUNDS is reached.

        Args:
            prompt:       User design description.
            image_path:   Optional path to a reference image (PNG/JPG/WEBP/GIF).
            sloper_state: Dict describing the current state of the sloper
                          (panel names, measurements, existing darts, etc.).
        """
        self._history = []

        first_user_content = self._build_first_user_message(
            prompt, image_path, sloper_state
        )
        self._history.append({"role": "user", "content": first_user_content})

        for round_num in range(1, MAX_ACTION_ROUNDS + 1):
            logger.info("AI round %d / %d", round_num, MAX_ACTION_ROUNDS)

            raw = self._call_claude()
            action = self._parse_action(raw)

            if action is None:
                logger.warning("Could not parse action on round %d; stopping.", round_num)
                break

            logger.info(
                "Action %d: %s  |  %s",
                round_num, action.get("action"), action.get("reasoning", "")
            )

            yield action

            if action.get("done") or action.get("action") == "design_complete":
                logger.info("AI signalled design_complete.")
                break

            # Feed the action back as the assistant turn so the model has
            # context for the next step.
            self._history.append({"role": "assistant", "content": raw})
            self._history.append({
                "role": "user",
                "content": (
                    f"Action applied successfully. "
                    f"Continue with the next action (round {round_num + 1})."
                ),
            })
        else:
            logger.warning("Reached MAX_ACTION_ROUNDS (%d).", MAX_ACTION_ROUNDS)

    def reset(self) -> None:
        """Clear conversation history."""
        self._history = []

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _build_first_user_message(
        self,
        prompt: str,
        image_path: str | None,
        sloper_state: dict | None,
    ) -> list[dict] | str:
        """Build the first user message (may include an image block)."""
        state_text = ""
        if sloper_state:
            state_text = (
                "\n\nCurrent sloper state:\n"
                + json.dumps(sloper_state, indent=2)
            )

        text_block = {
            "type": "text",
            "text": (
                f"Design request: {prompt}"
                + state_text
                + "\n\nPlease begin issuing CLO3D actions to realise this design. "
                "Start with the first action now."
            ),
        }

        if image_path:
            image_block = self._load_image_block(image_path)
            if image_block:
                return [image_block, text_block]

        return [text_block]

    def _load_image_block(self, image_path: str) -> dict | None:
        """Read an image file and return an Anthropic image content block."""
        path = Path(image_path)
        if not path.exists():
            logger.warning("Image path does not exist: %s", image_path)
            return None

        suffix = path.suffix.lower()
        media_type_map = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".gif": "image/gif",
            ".webp": "image/webp",
        }
        media_type = media_type_map.get(suffix)
        if not media_type:
            logger.warning("Unsupported image format: %s", suffix)
            return None

        import base64
        data = base64.standard_b64encode(path.read_bytes()).decode("utf-8")
        return {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": media_type,
                "data": data,
            },
        }

    def _call_claude(self) -> str:
        """Send the current conversation to Claude and return the raw text."""
        response = self._client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=CLAUDE_MAX_TOKENS,
            system=_SYSTEM_PROMPT,
            messages=self._history,
        )
        text = response.content[0].text.strip()
        logger.debug("Claude raw response: %s", text)
        return text

    def _parse_action(self, raw: str) -> dict | None:
        """
        Parse a JSON action from Claude's raw response.

        Strips markdown fences if present, then parses JSON.
        Returns None on failure.
        """
        # Strip optional markdown code fences
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            lines = cleaned.splitlines()
            # Remove first and last fence lines
            cleaned = "\n".join(lines[1:-1]) if len(lines) > 2 else cleaned

        try:
            action = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            logger.error("JSON parse error: %s\nRaw: %s", exc, raw)
            return None

        if "action" not in action:
            logger.error("Parsed object missing 'action' key: %s", action)
            return None

        if action["action"] not in ACTION_TYPES:
            logger.warning("Unknown action type '%s'; skipping.", action["action"])
            return None

        return action
