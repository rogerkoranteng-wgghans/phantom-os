"""
Precise mouse control with human-like bezier curve movement.
"""
from __future__ import annotations

import asyncio
import logging
import math
import random
import time

from pynput.mouse import Button, Controller as MouseController

logger = logging.getLogger(__name__)


class MouseExecutor:
    def __init__(self, screen_width: int, screen_height: int, human_speed: bool = True):
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.human_speed = human_speed
        self._mouse = MouseController()
        self._loop: asyncio.AbstractEventLoop | None = None

    async def _run_sync(self, fn, *args):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, fn, *args)

    def _resolve_coordinates(self, x: int | float, y: int | float) -> tuple[int, int]:
        """Handle both absolute pixel coords and 0-1 fractional coords."""
        if isinstance(x, float) and 0.0 <= x <= 1.0:
            x = int(x * self.screen_width)
        if isinstance(y, float) and 0.0 <= y <= 1.0:
            y = int(y * self.screen_height)
        # Clamp to screen bounds
        x = max(0, min(self.screen_width - 1, int(x)))
        y = max(0, min(self.screen_height - 1, int(y)))
        return x, y

    def _bezier_move(self, start: tuple, end: tuple, steps: int = 25) -> list[tuple]:
        """Generate smooth bezier curve points from start to end."""
        sx, sy = start
        ex, ey = end

        # Random control points for natural movement
        cp1x = sx + (ex - sx) * random.uniform(0.2, 0.4) + random.randint(-30, 30)
        cp1y = sy + (ey - sy) * random.uniform(0.2, 0.4) + random.randint(-30, 30)
        cp2x = sx + (ex - sx) * random.uniform(0.6, 0.8) + random.randint(-30, 30)
        cp2y = sy + (ey - sy) * random.uniform(0.6, 0.8) + random.randint(-30, 30)

        points = []
        for i in range(steps + 1):
            t = i / steps
            # Cubic bezier formula
            px = (
                (1 - t) ** 3 * sx
                + 3 * (1 - t) ** 2 * t * cp1x
                + 3 * (1 - t) * t ** 2 * cp2x
                + t ** 3 * ex
            )
            py = (
                (1 - t) ** 3 * sy
                + 3 * (1 - t) ** 2 * t * cp1y
                + 3 * (1 - t) * t ** 2 * cp2y
                + t ** 3 * ey
            )
            points.append((int(px), int(py)))
        return points

    def _do_move(self, x: int, y: int) -> None:
        """Synchronous smooth move."""
        current = self._mouse.position
        if self.human_speed:
            points = self._bezier_move(current, (x, y))
            dist = math.sqrt((x - current[0]) ** 2 + (y - current[1]) ** 2)
            duration = min(0.8, max(0.1, dist / 2000))
            delay = duration / len(points)
            for px, py in points:
                self._mouse.position = (px, py)
                time.sleep(delay + random.uniform(0, delay * 0.2))
        else:
            self._mouse.position = (x, y)

    async def move_to(self, x: int, y: int) -> None:
        x, y = self._resolve_coordinates(x, y)
        await asyncio.get_event_loop().run_in_executor(None, self._do_move, x, y)

    async def click(
        self,
        x: int,
        y: int,
        button: str = "left",
        double: bool = False,
    ) -> None:
        x, y = self._resolve_coordinates(x, y)
        btn = Button.left if button == "left" else Button.right

        def do():
            self._do_move(x, y)
            time.sleep(random.uniform(0.05, 0.12))
            if double:
                self._mouse.click(btn, 2)
            else:
                self._mouse.click(btn, 1)

        await asyncio.get_event_loop().run_in_executor(None, do)
        logger.debug(f"Clicked {button} at ({x}, {y}) double={double}")

    async def right_click(self, x: int, y: int) -> None:
        await self.click(x, y, button="right")

    async def drag(
        self, from_x: int, from_y: int, to_x: int, to_y: int
    ) -> None:
        from_x, from_y = self._resolve_coordinates(from_x, from_y)
        to_x, to_y = self._resolve_coordinates(to_x, to_y)

        def do():
            self._do_move(from_x, from_y)
            time.sleep(0.1)
            self._mouse.press(Button.left)
            time.sleep(0.05)
            self._do_move(to_x, to_y)
            time.sleep(0.05)
            self._mouse.release(Button.left)

        await asyncio.get_event_loop().run_in_executor(None, do)
        logger.debug(f"Dragged ({from_x},{from_y}) → ({to_x},{to_y})")

    async def scroll(
        self, x: int, y: int, amount: int = 3, direction: str = "down"
    ) -> None:
        x, y = self._resolve_coordinates(x, y)
        scroll_amount = -amount if direction == "down" else amount

        def do():
            self._mouse.position = (x, y)
            time.sleep(0.05)
            self._mouse.scroll(0, scroll_amount)

        await asyncio.get_event_loop().run_in_executor(None, do)
        logger.debug(f"Scrolled {direction} {amount} at ({x},{y})")
