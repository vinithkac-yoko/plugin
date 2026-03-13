"""
CLO3D Plugin UI Panel.

Renders a simple Tkinter dialog when the plugin is launched from inside CLO3D.
If Tkinter is unavailable (headless CI / server environment) the UI is skipped
and inputs are taken from the DesignInput object passed directly.

The panel:
  • Text area for the design prompt
  • File-picker button for an optional reference image
  • "Generate Design" button that kicks off the AI pipeline
  • Real-time action log (scrollable text box)
  • Progress bar
"""

from __future__ import annotations

import logging
import os
import threading
from pathlib import Path
from typing import Callable

logger = logging.getLogger(__name__)


class PluginPanel:
    """
    Tkinter-based UI panel for the CLO3D AI Design Plugin.

    Args:
        on_generate: Callback invoked with (prompt, image_path) when the user
                     clicks "Generate Design".
        on_cancel:   Callback invoked when the user clicks "Cancel / Stop".
    """

    def __init__(
        self,
        on_generate: Callable[[str, str | None], None],
        on_cancel: Callable[[], None] | None = None,
    ) -> None:
        self._on_generate = on_generate
        self._on_cancel = on_cancel or (lambda: None)
        self._root = None
        self._image_path: str | None = None
        self._running = False

    # ── Public API ────────────────────────────────────────────────────────────

    def show(self) -> None:
        """Launch the Tkinter window (blocks until window is closed)."""
        try:
            import tkinter as tk
            from tkinter import filedialog, scrolledtext, ttk
        except ImportError:
            logger.warning("Tkinter not available — UI skipped.")
            return

        self._root = tk.Tk()
        root = self._root
        root.title("CLO3D AI Design Plugin")
        root.resizable(True, True)
        root.minsize(560, 600)

        padding = {"padx": 10, "pady": 6}

        # ── Prompt ────────────────────────────────────────────────────────────
        tk.Label(root, text="Design Prompt:", anchor="w").pack(fill="x", **padding)
        self._prompt_box = scrolledtext.ScrolledText(root, height=6, wrap="word")
        self._prompt_box.pack(fill="x", expand=False, **padding)
        self._prompt_box.insert(
            "1.0",
            "e.g. A sleeveless A-line sundress with a deep V-neckline and empire waist"
        )
        self._prompt_box.bind("<FocusIn>", self._clear_placeholder)

        # ── Image picker ──────────────────────────────────────────────────────
        img_frame = tk.Frame(root)
        img_frame.pack(fill="x", **padding)
        tk.Label(img_frame, text="Reference Image (optional):").pack(side="left")
        self._img_label = tk.Label(img_frame, text="None selected", fg="grey")
        self._img_label.pack(side="left", padx=6)
        tk.Button(img_frame, text="Browse…", command=self._pick_image).pack(side="right")

        # ── Buttons ───────────────────────────────────────────────────────────
        btn_frame = tk.Frame(root)
        btn_frame.pack(fill="x", **padding)
        self._gen_btn = tk.Button(
            btn_frame,
            text="✦ Generate Design",
            bg="#2196F3",
            fg="white",
            padx=12,
            command=self._start_generation,
        )
        self._gen_btn.pack(side="left")
        tk.Button(
            btn_frame,
            text="Stop",
            command=self._cancel,
        ).pack(side="left", padx=6)

        # ── Progress bar ──────────────────────────────────────────────────────
        self._progress = ttk.Progressbar(root, mode="indeterminate")
        self._progress.pack(fill="x", **padding)

        # ── Action log ────────────────────────────────────────────────────────
        tk.Label(root, text="Action Log:", anchor="w").pack(fill="x", **padding)
        self._log_box = scrolledtext.ScrolledText(
            root, height=16, wrap="word", state="disabled", bg="#1e1e1e", fg="#d4d4d4",
            font=("Consolas", 10),
        )
        self._log_box.pack(fill="both", expand=True, **padding)

        root.mainloop()

    def log_action(self, message: str) -> None:
        """Append a line to the action log (thread-safe)."""
        if self._log_box is None:
            return
        def _append():
            self._log_box.configure(state="normal")
            self._log_box.insert("end", message + "\n")
            self._log_box.see("end")
            self._log_box.configure(state="disabled")
        if self._root:
            self._root.after(0, _append)

    def set_done(self) -> None:
        """Called when generation is complete."""
        if self._root:
            self._root.after(0, self._on_done_ui)

    # ── Internal ──────────────────────────────────────────────────────────────

    def _clear_placeholder(self, event) -> None:  # noqa: ANN001
        current = self._prompt_box.get("1.0", "end-1c")
        if current.startswith("e.g. "):
            self._prompt_box.delete("1.0", "end")

    def _pick_image(self) -> None:
        try:
            from tkinter import filedialog
        except ImportError:
            return
        path = filedialog.askopenfilename(
            title="Select reference image",
            filetypes=[
                ("Image files", "*.png *.jpg *.jpeg *.webp *.gif"),
                ("All files", "*.*"),
            ],
        )
        if path:
            self._image_path = path
            self._img_label.configure(text=Path(path).name, fg="black")

    def _start_generation(self) -> None:
        prompt = self._prompt_box.get("1.0", "end-1c").strip()
        if not prompt or prompt.startswith("e.g. "):
            self.log_action("⚠  Please enter a design prompt first.")
            return

        self._gen_btn.configure(state="disabled")
        self._progress.start(12)
        self._running = True

        def _run():
            try:
                self._on_generate(prompt, self._image_path)
            except Exception as exc:  # noqa: BLE001
                self.log_action(f"ERROR: {exc}")
            finally:
                self.set_done()

        threading.Thread(target=_run, daemon=True).start()

    def _cancel(self) -> None:
        self._running = False
        self._on_cancel()
        self.log_action("⛔  Generation cancelled by user.")

    def _on_done_ui(self) -> None:
        self._progress.stop()
        self._gen_btn.configure(state="normal")
        self.log_action("✅  Design generation complete.")
