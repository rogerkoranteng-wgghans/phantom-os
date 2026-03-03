"""
Phantom HUD — transparent overlay showing what Phantom is targeting in real-time.
Uses tkinter with transparency tricks.
Runs in a dedicated thread (tkinter requires its own thread).
"""
from __future__ import annotations

import logging
import queue
import threading
import time
from typing import Optional

logger = logging.getLogger(__name__)

try:
    import tkinter as tk
    TK_AVAILABLE = True
except ImportError:
    TK_AVAILABLE = False
    logger.warning("tkinter not available — HUD disabled")


class PhantomHUD:
    def __init__(self, screen_width: int, screen_height: int):
        self.screen_width = screen_width
        self.screen_height = screen_height
        self._queue: queue.Queue = queue.Queue()
        self._thread: Optional[threading.Thread] = None
        self._root: Optional[tk.Tk] = None
        self._canvas: Optional[tk.Canvas] = None
        self._visible = True
        self._running = False

        if TK_AVAILABLE:
            self._thread = threading.Thread(target=self._run_tk, daemon=True)
            self._thread.start()

    def _run_tk(self) -> None:
        """Run tkinter in its own thread."""
        try:
            self._root = tk.Tk()
            self._root.title("Phantom HUD")
            self._root.geometry(f"{self.screen_width}x{self.screen_height}+0+0")
            self._root.overrideredirect(True)  # No window decorations
            self._root.attributes("-topmost", True)
            self._root.attributes("-alpha", 0.0)  # Start fully transparent
            self._root.configure(bg="black")

            # Make window click-through on Linux
            try:
                self._root.attributes("-type", "splash")
            except Exception:
                pass

            self._canvas = tk.Canvas(
                self._root,
                width=self.screen_width,
                height=self.screen_height,
                bg="black",
                highlightthickness=0,
            )
            self._canvas.pack()

            self._running = True
            self._root.after(50, self._process_queue)
            self._root.mainloop()
        except Exception as e:
            logger.error(f"HUD tkinter error: {e}")

    def _process_queue(self) -> None:
        """Process pending HUD updates from main thread."""
        if not self._running or not self._root:
            return
        try:
            while True:
                cmd, args = self._queue.get_nowait()
                getattr(self, f"_do_{cmd}")(*args)
        except queue.Empty:
            pass
        self._root.after(50, self._process_queue)

    def _do_show_target(self, x: int, y: int, width: int, height: int, label: str, confidence: float) -> None:
        if not self._canvas:
            return
        self._canvas.delete("target")
        # Make window semi-visible
        self._root.attributes("-alpha", 0.85)
        # Draw red rectangle
        self._canvas.create_rectangle(
            x, y, x + width, y + height,
            outline="#ef4444", width=2, tags="target"
        )
        # Confidence label
        color = "#10b981" if confidence > 0.9 else "#f59e0b" if confidence > 0.7 else "#ef4444"
        self._canvas.create_text(
            x + width // 2, y - 15,
            text=f"{label} ({confidence:.0%})",
            fill=color, font=("JetBrains Mono", 11, "bold"),
            tags="target",
        )
        # Auto-hide target after 1.5s
        self._root.after(1500, lambda: self._canvas.delete("target"))

    def _do_show_narration(self, text: str, duration_ms: int) -> None:
        if not self._canvas:
            return
        self._canvas.delete("narration")
        y_pos = self.screen_height - 60
        # Background pill
        self._canvas.create_rectangle(
            20, y_pos - 18, min(len(text) * 8 + 40, self.screen_width - 20), y_pos + 10,
            fill="#12121a", outline="#7c3aed", width=1, tags="narration"
        )
        self._canvas.create_text(
            30, y_pos - 4,
            text=f"⚡ {text}",
            fill="#e2e8f0", font=("JetBrains Mono", 10),
            anchor="w", tags="narration",
        )
        self._root.after(duration_ms, lambda: self._canvas.delete("narration"))

    def _do_show_status(self, status: str) -> None:
        if not self._canvas:
            return
        self._canvas.delete("status")
        status_colors = {
            "LISTENING": "#10b981",
            "THINKING": "#f59e0b",
            "EXECUTING": "#7c3aed",
            "IDLE": "#64748b",
        }
        color = status_colors.get(status.upper(), "#64748b")
        self._canvas.create_rectangle(
            self.screen_width - 160, 10,
            self.screen_width - 10, 35,
            fill="#12121a", outline=color, width=1, tags="status",
        )
        self._canvas.create_text(
            self.screen_width - 85, 22,
            text=f"⚡ {status}",
            fill=color, font=("JetBrains Mono", 9, "bold"),
            tags="status",
        )

    def _do_hide_target(self) -> None:
        if self._canvas:
            self._canvas.delete("target")

    def _do_toggle(self) -> None:
        if not self._root:
            return
        self._visible = not self._visible
        if not self._visible:
            self._root.attributes("-alpha", 0.0)
            if self._canvas:
                self._canvas.delete("all")

    # ─── Public thread-safe methods ───────────────────────────────────────────

    def show_target(self, x: int, y: int, width: int = 60, height: int = 30, label: str = "", confidence: float = 1.0) -> None:
        if TK_AVAILABLE and self._running:
            self._queue.put(("show_target", (x, y, width, height, label, confidence)))

    def show_narration(self, text: str, duration_ms: int = 3000) -> None:
        if TK_AVAILABLE and self._running:
            self._queue.put(("show_narration", (text, duration_ms)))

    def show_status(self, status: str) -> None:
        if TK_AVAILABLE and self._running:
            self._queue.put(("show_status", (status,)))

    def hide_target(self) -> None:
        if TK_AVAILABLE and self._running:
            self._queue.put(("hide_target", ()))

    def toggle(self) -> None:
        if TK_AVAILABLE and self._running:
            self._queue.put(("toggle", ()))

    def stop(self) -> None:
        self._running = False
        if self._root:
            try:
                self._root.quit()
            except Exception:
                pass
