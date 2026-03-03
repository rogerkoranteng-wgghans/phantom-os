"""
System-level operations: app launch, clipboard, window management, file ops.
"""
from __future__ import annotations

import asyncio
import base64
import io
import logging
import os
import subprocess
import sys
from typing import Optional

logger = logging.getLogger(__name__)

try:
    import pyperclip
    CLIPBOARD_AVAILABLE = True
except ImportError:
    CLIPBOARD_AVAILABLE = False
    logger.warning("pyperclip not installed — clipboard operations limited")

try:
    import mss
    from PIL import Image
    SCREENSHOT_AVAILABLE = True
except ImportError:
    SCREENSHOT_AVAILABLE = False


class SystemExecutor:
    def __init__(self):
        self._screen_width = 0
        self._screen_height = 0
        self._update_screen_size()

    def _update_screen_size(self) -> None:
        if SCREENSHOT_AVAILABLE:
            with mss.mss() as sct:
                m = sct.monitors[1]
                self._screen_width = m["width"]
                self._screen_height = m["height"]

    async def get_screen_size(self) -> tuple[int, int]:
        return self._screen_width, self._screen_height

    async def open_app(self, app_name: str) -> bool:
        """Launch an application by name. Platform-aware."""
        def do():
            try:
                if sys.platform == "linux":
                    # Try xdg-open first for files, then direct launch
                    if os.path.exists(app_name):
                        subprocess.Popen(["xdg-open", app_name])
                    else:
                        subprocess.Popen([app_name])
                elif sys.platform == "darwin":
                    subprocess.Popen(["open", "-a", app_name])
                elif sys.platform == "win32":
                    os.startfile(app_name)
                return True
            except FileNotFoundError:
                # Try common app name variations
                variations = [app_name.lower(), app_name.lower().replace(" ", "-")]
                for v in variations:
                    try:
                        subprocess.Popen([v])
                        return True
                    except FileNotFoundError:
                        continue
                logger.error(f"Could not open app: {app_name}")
                return False
            except Exception as e:
                logger.error(f"open_app error: {e}")
                return False

        return await asyncio.get_event_loop().run_in_executor(None, do)

    async def open_url(self, url: str) -> None:
        """Open URL in default browser."""
        import webbrowser
        await asyncio.get_event_loop().run_in_executor(
            None, webbrowser.open, url
        )

    async def get_clipboard(self) -> str:
        """Read clipboard content."""
        if not CLIPBOARD_AVAILABLE:
            return ""
        try:
            return await asyncio.get_event_loop().run_in_executor(
                None, pyperclip.paste
            )
        except Exception as e:
            logger.error(f"get_clipboard error: {e}")
            return ""

    async def set_clipboard(self, text: str) -> None:
        """Write text to clipboard."""
        if not CLIPBOARD_AVAILABLE:
            return
        try:
            await asyncio.get_event_loop().run_in_executor(
                None, pyperclip.copy, text
            )
        except Exception as e:
            logger.error(f"set_clipboard error: {e}")

    async def take_screenshot(self) -> str:
        """Capture full screenshot, return base64 JPEG."""
        if not SCREENSHOT_AVAILABLE:
            return ""
        try:
            def do():
                with mss.mss() as sct:
                    monitor = sct.monitors[1]
                    screenshot = sct.grab(monitor)
                    img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")
                    buf = io.BytesIO()
                    img.save(buf, format="JPEG", quality=70)
                    return base64.b64encode(buf.getvalue()).decode("utf-8")

            return await asyncio.get_event_loop().run_in_executor(None, do)
        except Exception as e:
            logger.error(f"take_screenshot error: {e}")
            return ""

    async def list_windows(self) -> list[str]:
        """Get list of open window titles (Linux/X11)."""
        try:
            if sys.platform == "linux":
                result = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: subprocess.run(
                        ["wmctrl", "-l"], capture_output=True, text=True
                    ),
                )
                if result.returncode == 0:
                    lines = result.stdout.strip().split("\n")
                    titles = []
                    for line in lines:
                        parts = line.split(None, 3)
                        if len(parts) >= 4:
                            titles.append(parts[3])
                    return titles
        except Exception as e:
            logger.debug(f"list_windows error: {e}")
        return []

    async def focus_window(self, title_contains: str) -> bool:
        """Bring window containing title_contains to front."""
        try:
            if sys.platform == "linux":
                result = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: subprocess.run(
                        ["wmctrl", "-a", title_contains], capture_output=True
                    ),
                )
                return result.returncode == 0
        except Exception as e:
            logger.debug(f"focus_window error: {e}")
        return False
