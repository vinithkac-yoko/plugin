"""
Minimal CLO3D Plugin
- Load an avatar
- Move pattern pieces
"""

import os

# ── Log to file (visible after running via Script Editor or Plugin Manager) ───
LOG_PATH = r"C:\Users\shari\Desktop\clo_log.txt"

# Clear log on each run
with open(LOG_PATH, "w") as f:
    f.write("=== CLO3D Plugin Log ===\n")

def log(msg):
    print(msg)
    with open(LOG_PATH, "a") as f:
        f.write(msg + "\n")


# ── CLO3D detection ───────────────────────────────────────────────────────────
# CLO3D injects `clo` into globals — grab it explicitly so functions can use it.
_clo = globals().get("clo", None)
if _clo is None:
    log("CLO3D not found — running in stub mode")
else:
    log(f"CLO3D loaded: {_clo}")


# ── Config ────────────────────────────────────────────────────────────────────
AVATAR_PATH = r"C:\Users\Public\Documents\CLO\CLO Assets\Avatar\Male\MV2.1_Luka.avt"


# ── Helpers ───────────────────────────────────────────────────────────────────

def load_avatar(path):
    log(f"Loading avatar: {path}")
    if not os.path.exists(path):
        log(f"ERROR: Avatar file not found at {path}")
        return
    if _clo is not None:
        _clo.LoadAvatar(path)
        log("Avatar loaded successfully")


def get_patterns():
    if _clo is None:
        log("STUB: returning fake pattern IDs")
        return [0, 1, 2, 3]
    raw = _clo.GetAllPatternIDs()
    log(f"GetAllPatternIDs() returned: {raw} (type: {type(raw)})")
    if not raw:
        log("WARNING: no patterns found — open a garment in CLO3D first")
    return raw


def move_pattern(pattern_id, x, y):
    log(f"Moving Pattern[{pattern_id}] to ({x}, {y})")
    if _clo is not None:
        try:
            _clo.MovePattern(pattern_id, x, y)
            log(f"  => moved OK")
        except Exception as e:
            log(f"  => ERROR: {e}")


def simulate():
    log("Running simulation...")
    if _clo is not None:
        try:
            _clo.Simulate()
            log("Simulation complete")
        except Exception as e:
            log(f"Simulation ERROR: {e}")


# ── Main ──────────────────────────────────────────────────────────────────────

def run():
    log("--- Starting plugin ---")

    load_avatar(AVATAR_PATH)

    patterns = get_patterns()

    positions = [
        (  0,    0),
        (400,    0),
        (  0,  500),
        (400,  500),
    ]

    for i, pattern_id in enumerate(patterns):
        if i < len(positions):
            x, y = positions[i]
            move_pattern(pattern_id, x, y)

    simulate()
    log("--- Done ---")


run()
