"""
Global configuration for the CLO3D AI Design Plugin.
"""

import os
from pathlib import Path

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = BASE_DIR / "templates"
ASSETS_DIR = BASE_DIR / "assets"

# ── CLO3D ─────────────────────────────────────────────────────────────────────
# Unit used by CLO3D's Python API.  "mm" is the native unit.
CLO_UNIT: str = "mm"

# Default seam allowance added to every panel edge (mm).
DEFAULT_SEAM_ALLOWANCE_MM: float = 10.0

# ── Logging ───────────────────────────────────────────────────────────────────
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
