"""
Minimal CLO3D Plugin
- Load an avatar
- Load a garment
- Move pattern pieces
"""

# clo is injected into globals by CLO3D at runtime — no import needed.
# If running outside CLO3D (e.g. cmd), define a stub so the script doesn't crash.
if "clo" not in dir():
    clo = None
    print("CLO3D not found — running in stub mode")
else:
    print("CLO3D loaded")


# ── Config: change these paths to your actual files ──────────────────────────

AVATAR_PATH  = r"C:\Users\shari\Documents\CLO3D\Avatar\female_M.avt"
GARMENT_PATH = r"C:\Users\shari\Documents\CLO3D\Garments\base_dress.zprj"


# ── Helpers ───────────────────────────────────────────────────────────────────

def load_avatar(path):
    print(f"Loading avatar: {path}")
    if clo:
        clo.LoadAvatar(path)


def load_garment(path):
    print(f"Loading garment: {path}")
    if clo:
        clo.OpenProject(path)


def get_patterns():
    if not clo:
        # Stub: return fake pattern IDs for testing
        return [0, 1, 2, 3]
    return clo.GetAllPatternIDs()


def move_pattern(pattern_id, x, y):
    name = f"Pattern[{pattern_id}]"
    print(f"Moving {name} to ({x}, {y})")
    if clo:
        clo.MovePattern(pattern_id, x, y)


def simulate():
    print("Running simulation...")
    if clo:
        clo.Simulate()


# ── Main ──────────────────────────────────────────────────────────────────────

def run():
    # 1. Load avatar and garment
    load_avatar(AVATAR_PATH)
    load_garment(GARMENT_PATH)

    # 2. Get all pattern pieces
    patterns = get_patterns()
    print(f"Found {len(patterns)} pattern pieces: {patterns}")

    # 3. Move each pattern piece (hardcoded positions)
    positions = [
        (  0,    0),   # Front Bodice  — centre
        (400,    0),   # Back Bodice   — right
        (  0,  500),   # Front Skirt   — below front
        (400,  500),   # Back Skirt    — below back
    ]

    for i, pattern_id in enumerate(patterns):
        if i < len(positions):
            x, y = positions[i]
            move_pattern(pattern_id, x, y)

    # 4. Simulate draping
    simulate()
    print("Done.")


run()
