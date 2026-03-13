# CLO3D AI Design Plugin

An AI-powered CLO3D plugin that accepts a user's design intent — as a **text prompt**, a **reference image**, or both — and automatically manipulates a base sloper template to produce the target garment, entirely within CLO3D.

Claude (`claude-opus-4-6`) acts as the **AI brain**, reasoning about the design and emitting one structured CLO3D action at a time. CLO3D's Python API is the **execution layer** that applies each action to the live 3-D garment.

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    plugin.py  (entry)                   │
│                  DesignPipeline.run()                   │
└───────┬──────────────────────────────────┬──────────────┘
        │                                  │
        ▼                                  ▼
┌───────────────┐                 ┌─────────────────────┐
│ InputHandler  │                 │ SlopeTemplateManager│
│               │                 │                     │
│ • validates   │                 │ • loads JSON sloper │
│   prompt      │                 │ • applies panels,   │
│ • resolves /  │                 │   darts, stitches   │
│   resizes img │                 │   to CLO3D          │
└───────┬───────┘                 └──────────┬──────────┘
        │  DesignInput                        │ sloper_state
        ▼                                    ▼
┌───────────────────────────────────────────────────────┐
│                      AIBrain                          │
│                                                       │
│  Multi-turn conversation with Claude (claude-opus-4-6)│
│  Yields one JSON action per iteration:                │
│  { "action": "...", "params": {...}, "done": false }  │
└──────────────────────────┬────────────────────────────┘
                           │ action dict (one at a time)
                           ▼
┌──────────────────────────────────────────────────────┐
│                   ActionExecutor                     │
│                                                      │
│  Dispatches each action to the correct CLO3DApi      │
│  method; refreshes UI after every step.              │
└───────────────────────────┬──────────────────────────┘
                            │ CLO3D API calls
                            ▼
┌──────────────────────────────────────────────────────┐
│                     CLO3DApi                         │
│                                                      │
│  Thin wrapper around CLO3D's `clo` Python module.    │
│  Stubs out gracefully when `clo` is not available.   │
└──────────────────────────────────────────────────────┘
```

### Action language

Claude speaks a small, well-defined JSON vocabulary of CLO3D actions:

| Category | Actions |
|---|---|
| Panel management | `add_panel`, `duplicate_panel`, `delete_panel` |
| Geometry | `move_panel_point`, `set_panel_point_position`, `scale_panel`, `rotate_panel` |
| Darts | `add_dart`, `modify_dart`, `delete_dart` |
| Seam allowances | `set_seam_allowance`, `set_all_seam_allowances` |
| Fabric | `set_fabric`, `set_fabric_color` |
| Stitching | `stitch_edges`, `remove_stitch` |
| Avatar / sizing | `set_avatar_measurement` |
| Simulation | `run_simulation`, `reset_simulation` |
| Grading | `apply_grade` |
| Notation | `add_notch`, `set_grain_line` |
| Terminal | `design_complete` |

Each action is validated by the `ActionExecutor` before being forwarded to the CLO3D API, so malformed AI responses are safely rejected without crashing.

---

## File structure

```
plugin/
├── plugin.py                   # Main entry point (CLO3D script runner & CLI)
├── requirements.txt
├── .env.example
├── config/
│   └── settings.py             # All configuration constants
├── src/
│   ├── ai_brain.py             # Claude multi-turn conversation manager
│   ├── clo3d_api.py            # CLO3D Python API wrapper
│   ├── action_executor.py      # Dispatches AI actions → CLO3D calls
│   ├── input_handler.py        # Prompt + image validation & normalisation
│   ├── sloper_template.py      # Base sloper loader / applier
│   └── logger_setup.py         # Logging configuration
├── templates/
│   └── base_sloper.json        # Size-M bodice + skirt + sleeve template
└── ui/
    └── panel.py                # Tkinter UI panel (optional, CLO3D in-app use)
```

---

## Installation

### 1. Clone / copy into CLO3D's plugin directory

```bash
# Typical location on macOS
cp -r plugin/ ~/Documents/CLO3D/Plugin/ai-design-plugin/

# On Windows
xcopy /E plugin "C:\Users\<you>\Documents\CLO3D\Plugin\ai-design-plugin\"
```

### 2. Install Python dependencies

```bash
cd plugin/
pip install -r requirements.txt
```

### 3. Set your API key

```bash
cp .env.example .env
# Edit .env and set ANTHROPIC_API_KEY=sk-ant-...
```

---

## Usage

### A. From within CLO3D (recommended)

1. Open CLO3D.
2. Go to **Plugin → Script** and load `plugin.py`.
3. The AI Design Panel opens:
   - Type your design prompt.
   - Optionally click **Browse…** to attach a reference image.
   - Click **✦ Generate Design**.
4. Watch the action log as Claude designs your garment step by step.

### B. CLI / headless mode

```bash
# Text prompt only
python plugin.py --prompt "A sleeveless A-line sundress with a deep V-neckline"

# With a reference image
python plugin.py \
  --prompt "Recreate this dress silhouette" \
  --image  reference.jpg \
  --output my_dress.zprj
```

---

## Configuration

| Variable | Default | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | _(required)_ | Anthropic API key |
| `CLAUDE_MODEL` | `claude-opus-4-6` | Model ID to use |
| `LOG_LEVEL` | `INFO` | Python log level |

These can be set in `.env` or as regular environment variables.

### Advanced constants (`config/settings.py`)

| Constant | Default | Description |
|---|---|---|
| `MAX_ACTION_ROUNDS` | `30` | Max number of AI actions per design session |
| `CLAUDE_MAX_TOKENS` | `4096` | Max tokens per Claude response |
| `DEFAULT_SEAM_ALLOWANCE_MM` | `10.0` | Default seam allowance in mm |

---

## Extending the base sloper

Edit `templates/base_sloper.json` to add or adjust:
- Panel vertices (mm coordinates)
- Default darts (bust dart, waist dart, etc.)
- Seam allowances per panel / edge
- Avatar body measurements (size M by default)
- Stitch connections between panels

The AI receives a summary of this template as context before it starts generating actions, so it always knows what panels are available and where existing darts / stitches are.

---

## How the AI action loop works

```
User prompt + image
       │
       ▼
 AIBrain.generate_actions()
       │
       ├─► [Round 1] Claude → { "action": "set_avatar_measurement", ... }
       │         └─► ActionExecutor.execute() → CLO3DApi call → UI refresh
       │
       ├─► [Round 2] Claude → { "action": "modify_dart", ... }
       │         └─► ActionExecutor.execute() → CLO3DApi call → UI refresh
       │
       ├─► ...
       │
       └─► [Round N] Claude → { "action": "design_complete", "done": true }
```

Each round feeds the previous action result back into the conversation so Claude always has full context about what has already been applied.

---

## Running without CLO3D (stub mode)

When the `clo` Python module is not importable (e.g. in unit tests or CI), all `CLO3DApi` methods become no-ops that simply log what they _would_ do. The full pipeline still runs — you can validate AI output and action parsing without a CLO3D licence.

```bash
# No CLO3D installed — runs in stub mode, logs all actions
python plugin.py --prompt "Peplum blouse with bishop sleeves"
```
