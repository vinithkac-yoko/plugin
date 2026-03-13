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
if "clo" not in dir():
    clo = None
    log("CLO3D not found — running in stub mode")
else:
    log("CLO3D loaded")


# ── Config ────────────────────────────────────────────────────────────────────
AVATAR_PATH = r"C:\Users\Public\Documents\CLO\CLO Assets\Avatar\Male\MV2.1_Luka.avt"


# ── Helpers ───────────────────────────────────────────────────────────────────

def load_avatar(path):
    log(f"Loading avatar: {path}")
    if not os.path.exists(path):
        log(f"ERROR: Avatar file not found at {path}")
        return
    if clo:
        clo.LoadAvatar(path)
        log("Avatar loaded successfully")


def get_patterns():
    if not clo:
        return [0, 1, 2, 3]
    patterns = clo.GetAllPatternIDs()
    log(f"Found {len(patterns)} pattern pieces: {patterns}")
    return patterns


def move_pattern(pattern_id, x, y):
    log(f"Moving Pattern[{pattern_id}] to ({x}, {y})")
    if clo:
        clo.MovePattern(pattern_id, x, y)


def simulate():
    log("Running simulation...")
    if clo:
        clo.Simulate()
        log("Simulation complete")


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
