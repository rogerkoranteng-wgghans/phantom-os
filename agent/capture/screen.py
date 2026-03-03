"""
Adaptive screen capture module.
- 1fps idle / 4fps active with automatic switching
- Pixel-diff change detection to skip identical frames
- JPEG compression + downscaling for bandwidth efficiency
- Multi-monitor aware (defaults to primary)
"""
from __future__ import annotations

import asyncio
import base64
import io
import logging
import time
from typing import Callable, Awaitable

import mss
import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)


class ScreenCapture:
    def __init__(
        self,
        fps_idle: int = 1,
        fps_active: int = 4,
        quality: int = 70,
        scale: float = 0.75,
        change_threshold: float = 0.005,  # 0.5% pixel change to trigger send
    ):
        self.fps_idle = fps_idle
        self.fps_active = fps_active
        self.quality = quality
        self.scale = scale
        self.change_threshold = change_threshold

        self._active_mode = False
        self._running = False
        self._prev_frame: bytes | None = None
        self._sct: mss.mss | None = None

        # Get primary monitor info
        with mss.mss() as sct:
            # monitors[0] is all monitors combined; monitors[1] is the primary.
            # Guard against single-entry list on headless / minimal environments.
            idx = min(1, len(sct.monitors) - 1)
            if idx == 0:
                logger.warning(
                    "mss reported only 1 monitor entry; using monitors[0] (all screens combined)"
                )
            self._monitor = sct.monitors[idx]
            self.screen_width = self._monitor["width"]
            self.screen_height = self._monitor["height"]

    @property
    def fps(self) -> int:
        return self.fps_active if self._active_mode else self.fps_idle

    def set_active_mode(self, active: bool) -> None:
        self._active_mode = active
        logger.debug(f"ScreenCapture: {'active' if active else 'idle'} mode ({self.fps}fps)")

    def _capture_wayland_fallback(self) -> bytes | None:
        """Wayland-compatible screen capture via grim (best) or scrot (XWayland fallback)."""
        import subprocess
        import shutil
        import tempfile

        # ── Try grim (native Wayland) ─────────────────────────────────────────
        if shutil.which("grim"):
            try:
                with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
                    tmp = f.name
                result = subprocess.run(
                    ["grim", "-t", "png", tmp],
                    capture_output=True, timeout=3,
                )
                if result.returncode == 0:
                    img = Image.open(tmp)
                    new_w = int(img.width * self.scale)
                    new_h = int(img.height * self.scale)
                    img = img.resize((new_w, new_h), Image.LANCZOS)
                    buf = io.BytesIO()
                    img.save(buf, format="JPEG", quality=self.quality, optimize=True)
                    return buf.getvalue()
            except Exception as e:
                logger.debug(f"grim fallback error: {e}")

        # ── Try scrot (XWayland) ──────────────────────────────────────────────
        if shutil.which("scrot"):
            try:
                result = subprocess.run(
                    ["scrot", "-o", "/tmp/phantom_screen.jpg",
                     "--quality", str(self.quality)],
                    capture_output=True, timeout=3,
                )
                if result.returncode == 0:
                    with open("/tmp/phantom_screen.jpg", "rb") as f:
                        return f.read()
            except Exception as e:
                logger.debug(f"scrot fallback error: {e}")

        return None

    def capture_frame(self) -> str | None:
        """Capture screen, compress, return base64 JPEG. Returns None if no change."""
        frame_bytes: bytes | None = None

        # ── Primary: mss (fast, X11) ──────────────────────────────────────────
        try:
            with mss.mss() as sct:
                screenshot = sct.grab(self._monitor)
                img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")

                if self.scale < 1.0:
                    new_w = int(img.width * self.scale)
                    new_h = int(img.height * self.scale)
                    img = img.resize((new_w, new_h), Image.LANCZOS)

                buf = io.BytesIO()
                img.save(buf, format="JPEG", quality=self.quality, optimize=True)
                frame_bytes = buf.getvalue()

        except Exception as e:
            err_str = str(e)
            if "XGetImage" in err_str or "x_get_image" in err_str.lower():
                # ── Fallback: Wayland-compatible capture ──────────────────────
                if not getattr(self, "_wayland_warned", False):
                    logger.warning(
                        "ScreenCapture: XGetImage blocked (Wayland session). "
                        "Trying grim/scrot fallback. "
                        "For best results: sudo apt install grim"
                    )
                    self._wayland_warned = True
                frame_bytes = self._capture_wayland_fallback()
                if frame_bytes is None:
                    return None  # All methods failed — skip frame
            else:
                logger.error(f"ScreenCapture.capture_frame error: {e}")
                return None

        if frame_bytes is None:
            return None

        # Change detection
        if self._prev_frame is not None:
            change = self.detect_change(self._prev_frame, frame_bytes)
            if change < self.change_threshold:
                return None

        self._prev_frame = frame_bytes
        return base64.b64encode(frame_bytes).decode("utf-8")

    def detect_change(self, prev_frame: bytes, curr_frame: bytes) -> float:
        """Returns fraction of pixels that changed (0.0 - 1.0)."""
        try:
            prev_img = np.array(Image.open(io.BytesIO(prev_frame)).convert("L"))
            curr_img = np.array(Image.open(io.BytesIO(curr_frame)).convert("L"))

            if prev_img.shape != curr_img.shape:
                return 1.0  # Size changed = full update

            diff = np.abs(prev_img.astype(int) - curr_img.astype(int))
            changed_pixels = np.sum(diff > 10)  # >10 intensity change
            return changed_pixels / diff.size
        except Exception:
            return 1.0  # On error, assume changed

    async def start(self, on_frame: Callable[[str], Awaitable[None]]) -> None:
        """Start capture loop. Calls on_frame with each changed base64 JPEG frame."""
        self._running = True
        logger.info(f"ScreenCapture started ({self.screen_width}x{self.screen_height})")

        loop = asyncio.get_event_loop()

        while self._running:
            start_time = time.monotonic()

            # Run blocking capture in executor to not block event loop
            frame_b64 = await loop.run_in_executor(None, self.capture_frame)

            if frame_b64 is not None:
                try:
                    await on_frame(frame_b64)
                except Exception as e:
                    logger.error(f"on_frame callback error: {e}")

            elapsed = time.monotonic() - start_time
            sleep_time = max(0.0, (1.0 / self.fps) - elapsed)
            await asyncio.sleep(sleep_time)

    async def stop(self) -> None:
        self._running = False
        logger.info("ScreenCapture stopped")
