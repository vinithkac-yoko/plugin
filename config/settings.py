"""
Global configuration for the CLO3D AI Design Plugin.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = BASE_DIR / "templates"
ASSETS_DIR = BASE_DIR / "assets"

# ── Anthropic / Claude ─────────────────────────────────────────────────────────
ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL: str = os.getenv("CLAUDE_MODEL", "claude-opus-4-6")

# Max tokens the model may use in a single response (actions are JSON, so keep
# generous but bounded).
CLAUDE_MAX_TOKENS: int = 4096

# How many AI action rounds we allow before declaring the design "complete".
MAX_ACTION_ROUNDS: int = 30

# ── CLO3D ─────────────────────────────────────────────────────────────────────
# Unit used by CLO3D's Python API.  "mm" is the native unit.
CLO_UNIT: str = "mm"

# Default seam allowance added to every panel edge (mm).
DEFAULT_SEAM_ALLOWANCE_MM: float = 10.0

# ── Logging ───────────────────────────────────────────────────────────────────
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
