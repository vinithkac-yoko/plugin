"""
CLO3D AI Design Plugin — main entry point.

How it works
────────────
1.  The user provides a text prompt and/or a reference image.
2.  The base sloper template (bodice + skirt + sleeve) is loaded and applied
    inside CLO3D, creating a set of pattern panels on the avatar.
3.  Claude (claude-opus-4-6) analyses the design request and the current sloper
    state, then emits one CLO3D action at a time as structured JSON.
4.  The ActionExecutor translates each action into a real CLO3D API call,
    refreshing the 3-D view after every step.
5.  This continues until the AI signals design_complete or the action limit is
    reached.

Running modes
─────────────
• Inside CLO3D  → CLO3D calls plugin.run() automatically on script launch.
                  A Tkinter UI panel opens for input.
• CLI / testing → python plugin.py --prompt "..." [--image path] [--no-ui]
                  Useful for automated testing without CLO3D installed.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

# Ensure project root is on sys.path when run as a script
_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.logger_setup import setup_logging
from src.clo3d_api import CLO3DApi
from src.ai_brain import AIBrain
from src.action_executor import ActionExecutor
from src.input_handler import InputHandler
from src.sloper_template import SlopeTemplateManager

setup_logging()
logger = logging.getLogger(__name__)


# ── Core pipeline ─────────────────────────────────────────────────────────────

class DesignPipeline:
    """
    Orchestrates the full AI-driven design loop.

    Typical usage::

        pipeline = DesignPipeline()
        pipeline.run(
            prompt="A sleeveless midi dress with a plunging V-neck",
            image_path="/path/to/reference.jpg",
            output_path="/path/to/result.zprj",
            on_action=lambda action, result: ...,  # optional progress callback
        )
    """

    def __init__(self) -> None:
        self._api = CLO3DApi()
        self._brain = AIBrain()
        self._executor = ActionExecutor(self._api)
        self._input_handler = InputHandler()
        self._sloper_mgr = SlopeTemplateManager(self._api)

    # ── Public API ────────────────────────────────────────────────────────────

    def run(
        self,
        prompt: str,
        image_path: str | None = None,
        output_path: str | None = None,
        on_action=None,
    ) -> None:
        """
        Execute the full design pipeline.

        Args:
            prompt:      User's design description.
            image_path:  Optional path to a reference image.
            output_path: If given, save the resulting CLO3D project here.
            on_action:   Optional callback(action_dict, ActionResult) called
                         after every AI action — useful for UI progress updates.
        """
        logger.info("=== CLO3D AI Design Plugin ===")
        logger.info("Prompt: %s", prompt)
        if image_path:
            logger.info("Reference image: %s", image_path)

        # 1. Validate and normalise input
        design_input = self._input_handler.process(prompt, image_path)
        logger.info("Design input: %s", design_input.summary())

        # 2. Set up a fresh CLO3D project
        self._api.new_project()

        # 3. Load and apply the base sloper
        self._sloper_mgr.load()
        self._sloper_mgr.apply()
        sloper_state = self._sloper_mgr.get_state()
        logger.info(
            "Base sloper applied: %d panels", len(sloper_state.get("panels", []))
        )

        # 4. Reset executor log for this session
        self._executor.reset_log()

        # 5. Drive the AI action loop
        logger.info("Starting AI action loop…")
        action_count = 0
        for action in self._brain.generate_actions(
            prompt=design_input.prompt,
            image_path=design_input.image_path,
            sloper_state=sloper_state,
        ):
            result = self._executor.execute(action)
            action_count += 1

            if on_action:
                on_action(action, result)

            if not result.success:
                logger.warning("Action %d failed: %s", action_count, result.error)

            if action.get("done"):
                break

        # 6. Log summary
        logger.info(self._executor.log.summary())

        # 7. Optionally save the project
        if output_path:
            self._api.save_project(output_path)
            logger.info("Project saved to %s", output_path)

        logger.info("=== Design pipeline complete ===")

    @property
    def api(self) -> CLO3DApi:
        return self._api

    @property
    def executor(self) -> ActionExecutor:
        return self._executor


# ── UI entry point (CLO3D script runner) ──────────────────────────────────────

def run() -> None:
    """
    Called by CLO3D when the plugin script is loaded.
    Opens the Tkinter UI panel.
    """
    from ui.panel import PluginPanel

    pipeline = DesignPipeline()

    def on_generate(prompt: str, image_path: str | None) -> None:
        panel.log_action(f"⚙  Starting: {prompt[:80]}…")

        def _progress(action: dict, result) -> None:
            icon = "✓" if result.success else "✗"
            panel.log_action(
                f"  {icon} [{action['action']}] {action.get('reasoning', '')}"
            )

        pipeline.run(
            prompt=prompt,
            image_path=image_path,
            on_action=_progress,
        )

    def on_cancel() -> None:
        logger.info("User cancelled generation.")

    panel = PluginPanel(on_generate=on_generate, on_cancel=on_cancel)
    panel.show()


# ── CLI entry point ───────────────────────────────────────────────────────────

def _cli() -> None:
    """Command-line interface for headless / testing usage."""
    parser = argparse.ArgumentParser(
        description="CLO3D AI Design Plugin — CLI mode",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python plugin.py --prompt "A-line skirt with inverted pleat"
  python plugin.py --prompt "Wrap dress" --image ref.jpg --output result.zprj
        """,
    )
    parser.add_argument(
        "--prompt", "-p",
        required=True,
        help="Design description",
    )
    parser.add_argument(
        "--image", "-i",
        default=None,
        help="Path to a reference image (PNG/JPG/WEBP/GIF)",
    )
    parser.add_argument(
        "--output", "-o",
        default=None,
        help="Path to save the resulting .zprj project",
    )
    parser.add_argument(
        "--no-ui",
        action="store_true",
        help="Skip the Tkinter UI and run headlessly",
    )
    args = parser.parse_args()

    pipeline = DesignPipeline()
    pipeline.run(
        prompt=args.prompt,
        image_path=args.image,
        output_path=args.output,
        on_action=lambda action, result: print(
            f"  {'OK' if result.success else 'FAIL'} "
            f"[{action['action']}] {action.get('reasoning', '')}"
        ),
    )


# ── Script entry point ────────────────────────────────────────────────────────

if __name__ == "__main__":
    # When invoked directly (python plugin.py) use CLI mode
    _cli()
else:
    # When imported by CLO3D's script runner, launch the UI
    run()
