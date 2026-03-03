"""
Keyboard input executor with realistic typing timing and shortcut support.
"""
from __future__ import annotations

import asyncio
import logging
import random
import time

from pynput.keyboard import Controller as KeyboardController, Key, KeyCode

logger = logging.getLogger(__name__)

SPECIAL_KEYS = {
    "enter": Key.enter,
    "return": Key.enter,
    "tab": Key.tab,
    "escape": Key.esc,
    "esc": Key.esc,
    "backspace": Key.backspace,
    "delete": Key.delete,
    "up": Key.up,
    "down": Key.down,
    "left": Key.left,
    "right": Key.right,
    "home": Key.home,
    "end": Key.end,
    "page_up": Key.page_up,
    "page_down": Key.page_down,
    "space": Key.space,
    "ctrl": Key.ctrl,
    "control": Key.ctrl,
    "alt": Key.alt,
    "shift": Key.shift,
    "cmd": Key.cmd,
    "super": Key.cmd,
    "f1": Key.f1,
    "f2": Key.f2,
    "f3": Key.f3,
    "f4": Key.f4,
    "f5": Key.f5,
    "f6": Key.f6,
    "f7": Key.f7,
    "f8": Key.f8,
    "f9": Key.f9,
    "f10": Key.f10,
    "f11": Key.f11,
    "f12": Key.f12,
}


class KeyboardExecutor:
    def __init__(self):
        self._kb = KeyboardController()

    def _resolve_key(self, key_str: str):
        """Convert string key name to pynput Key or KeyCode."""
        lower = key_str.lower()
        if lower in SPECIAL_KEYS:
            return SPECIAL_KEYS[lower]
        if len(key_str) == 1:
            return KeyCode.from_char(key_str)
        return KeyCode.from_char(key_str[0])

    async def type_text(self, text: str, wpm: int = 80) -> None:
        """Type text with realistic variable keystroke timing."""
        if not text:
            return

        # Average char delay from WPM (5 chars per word)
        base_delay = 60.0 / (wpm * 5)

        def do():
            for char in text:
                self._kb.type(char)
                # Variable delay: faster for common chars, slower for special
                multiplier = 1.0
                if char in " \t\n":
                    multiplier = 1.5
                elif char in "!@#$%^&*(){}[]|\\\"':;<>?":
                    multiplier = 1.8
                jitter = random.uniform(-0.3, 0.5)
                delay = base_delay * multiplier * (1 + jitter)
                time.sleep(max(0.01, delay))

        await asyncio.get_event_loop().run_in_executor(None, do)
        logger.debug(f"Typed {len(text)} chars at ~{wpm}wpm")

    async def press_key(self, key: str) -> None:
        """Press and release a single key."""
        k = self._resolve_key(key)

        def do():
            self._kb.press(k)
            time.sleep(random.uniform(0.05, 0.1))
            self._kb.release(k)

        await asyncio.get_event_loop().run_in_executor(None, do)
        logger.debug(f"Pressed key: {key}")

    async def hotkey(self, *keys: str) -> None:
        """Press a key combination: hotkey('ctrl', 'c')."""
        resolved = [self._resolve_key(k) for k in keys]

        def do():
            # Press all keys in order
            for k in resolved:
                self._kb.press(k)
                time.sleep(0.02)
            time.sleep(0.05)
            # Release in reverse order
            for k in reversed(resolved):
                self._kb.release(k)
                time.sleep(0.02)

        await asyncio.get_event_loop().run_in_executor(None, do)
        logger.debug(f"Hotkey: {' + '.join(keys)}")

    async def select_all(self) -> None:
        await self.hotkey("ctrl", "a")

    async def copy(self) -> None:
        await self.hotkey("ctrl", "c")

    async def paste(self) -> None:
        await self.hotkey("ctrl", "v")

    async def undo(self) -> None:
        await self.hotkey("ctrl", "z")

    async def redo(self) -> None:
        await self.hotkey("ctrl", "y")

    async def save(self) -> None:
        await self.hotkey("ctrl", "s")
