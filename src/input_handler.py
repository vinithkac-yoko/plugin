"""
Input handler — validates, normalises, and packages user design inputs.

Accepts:
  • A free-text design prompt (str)
  • An optional image path (PNG, JPG, WEBP, GIF) or a URL to a reference image

Returns a clean DesignInput dataclass ready for the AIBrain.
"""

from __future__ import annotations

import logging
import mimetypes
import os
import re
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from config.settings import ASSETS_DIR

logger = logging.getLogger(__name__)

# Max pixel dimensions we allow before down-sampling the image
_MAX_IMAGE_DIM = 2048
# Max file size in bytes we send to the API (5 MB)
_MAX_IMAGE_BYTES = 5 * 1024 * 1024

SUPPORTED_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}


# ── Data model ────────────────────────────────────────────────────────────────

@dataclass
class DesignInput:
    """Normalised, validated design input ready for the AIBrain."""

    prompt: str
    """Natural-language description of the desired design."""

    image_path: Optional[str] = None
    """Absolute path to a local reference image (may have been downloaded /
    resized from the original source)."""

    extra_context: dict = field(default_factory=dict)
    """Any additional structured context the caller wants forwarded to the AI
    (e.g. target size, fabric preference)."""

    def has_image(self) -> bool:
        return self.image_path is not None and Path(self.image_path).exists()

    def summary(self) -> str:
        parts = [f"Prompt: "{self.prompt}""]
        if self.has_image():
            parts.append(f"Image: {self.image_path}")
        if self.extra_context:
            parts.append(f"Extra context: {self.extra_context}")
        return " | ".join(parts)


# ── InputHandler ──────────────────────────────────────────────────────────────

class InputHandler:
    """
    Validates and normalises a design request before it reaches the AI brain.

    Usage::

        handler = InputHandler()
        design = handler.process(
            prompt="A sleeveless A-line sundress with a V-neckline",
            image_source="~/references/dress.jpg",
            extra_context={"target_size": "M", "fabric": "linen"},
        )
    """

    def __init__(self, download_dir: Path | None = None) -> None:
        self._download_dir = download_dir or (ASSETS_DIR / "downloads")
        self._download_dir.mkdir(parents=True, exist_ok=True)

    # ── Public API ────────────────────────────────────────────────────────────

    def process(
        self,
        prompt: str,
        image_source: str | None = None,
        extra_context: dict | None = None,
    ) -> DesignInput:
        """
        Process raw user inputs into a validated DesignInput.

        Args:
            prompt:        User's design description.
            image_source:  File path or URL to a reference image (optional).
            extra_context: Any additional key-value pairs to include.

        Returns:
            A DesignInput ready for AIBrain.generate_actions().

        Raises:
            ValueError: If the prompt is empty or the image cannot be loaded.
        """
        prompt = self._validate_prompt(prompt)
        image_path = self._resolve_image(image_source) if image_source else None
        return DesignInput(
            prompt=prompt,
            image_path=image_path,
            extra_context=extra_context or {},
        )

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _validate_prompt(self, prompt: str) -> str:
        """Strip whitespace and ensure the prompt is non-empty."""
        prompt = prompt.strip()
        if not prompt:
            raise ValueError("Design prompt must not be empty.")
        if len(prompt) > 4000:
            logger.warning(
                "Prompt is very long (%d chars); truncating to 4000.", len(prompt)
            )
            prompt = prompt[:4000]
        return prompt

    def _resolve_image(self, source: str) -> str | None:
        """
        Return an absolute path to a usable image file.

        Handles:
          • Absolute / relative local paths
          • HTTP/HTTPS URLs (downloads to tmp dir)
        """
        source = source.strip()

        if self._is_url(source):
            return self._download_image(source)

        # Local file path
        path = Path(source).expanduser().resolve()
        if not path.exists():
            raise ValueError(f"Image file not found: {path}")
        if path.suffix.lower() not in SUPPORTED_IMAGE_EXTS:
            raise ValueError(
                f"Unsupported image format '{path.suffix}'. "
                f"Supported: {SUPPORTED_IMAGE_EXTS}"
            )

        # Resize if needed
        return self._maybe_resize(path)

    def _is_url(self, source: str) -> bool:
        return re.match(r"^https?://", source, re.IGNORECASE) is not None

    def _download_image(self, url: str) -> str | None:
        """Download a remote image and return the local path."""
        logger.info("Downloading reference image from %s", url)

        # Guess file extension from URL or Content-Type
        url_path = url.split("?")[0]
        ext = Path(url_path).suffix.lower()
        if ext not in SUPPORTED_IMAGE_EXTS:
            ext = ".jpg"  # fallback

        local_name = "ref_" + re.sub(r"[^a-zA-Z0-9]", "_", url)[-40:] + ext
        local_path = self._download_dir / local_name

        if local_path.exists():
            logger.info("Using cached download: %s", local_path)
            return str(local_path)

        try:
            headers = {"User-Agent": "CLO3D-AI-Plugin/1.0"}
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310
                content_type = resp.headers.get("Content-Type", "")
                if "image" not in content_type:
                    raise ValueError(
                        f"URL does not appear to serve an image "
                        f"(Content-Type: {content_type})"
                    )
                data = resp.read(_MAX_IMAGE_BYTES + 1)

            if len(data) > _MAX_IMAGE_BYTES:
                raise ValueError(
                    f"Remote image is too large (>{_MAX_IMAGE_BYTES // 1024 // 1024} MB)."
                )

            local_path.write_bytes(data)
            logger.info("Downloaded image saved to %s", local_path)

        except Exception as exc:
            logger.error("Failed to download image: %s", exc)
            return None

        return self._maybe_resize(local_path)

    def _maybe_resize(self, path: Path) -> str:
        """
        Resize the image if either dimension exceeds _MAX_IMAGE_DIM or
        the file exceeds _MAX_IMAGE_BYTES.

        Returns the path to the (possibly new) file as a string.
        """
        try:
            from PIL import Image  # type: ignore[import]
        except ImportError:
            logger.warning(
                "Pillow not installed — skipping image resize check. "
                "Install with: pip install Pillow"
            )
            return str(path)

        with Image.open(path) as img:
            w, h = img.size
            file_size = path.stat().st_size

            needs_resize = (
                w > _MAX_IMAGE_DIM
                or h > _MAX_IMAGE_DIM
                or file_size > _MAX_IMAGE_BYTES
            )

            if not needs_resize:
                return str(path)

            # Compute new size preserving aspect ratio
            ratio = min(_MAX_IMAGE_DIM / w, _MAX_IMAGE_DIM / h)
            new_w = int(w * ratio)
            new_h = int(h * ratio)

            logger.info(
                "Resizing image from %dx%d to %dx%d", w, h, new_w, new_h
            )

            resized = img.resize((new_w, new_h), Image.LANCZOS)

            # Save as PNG to a new path so we don't overwrite the original
            new_path = path.with_stem(path.stem + "_resized").with_suffix(".png")
            resized.save(new_path, format="PNG", optimize=True)
            return str(new_path)
