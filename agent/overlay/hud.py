"""
Phantom HUD — small always-on-top corner widget.

Shows live status and narration without covering the screen or blocking clicks.
Runs in a dedicated thread (tkinter requires its own thread).
"""
from __future__ import annotations

import logging
import queue
import threading
from typing import Optional

logger = logging.getLogger(__name__)

try:
    import tkinter as tk
    TK_AVAILABLE = True
except ImportError:
    TK_AVAILABLE = False
    logger.warning("tkinter not available — HUD disabled")

# Widget dimensions and position
WIDGET_W = 320
WIDGET_H = 90
MARGIN   = 12          # pixels from screen edge


class PhantomHUD:
    def __init__(self, screen_width: int, screen_height: int):
        self.screen_width  = screen_width  or 1920
        self.screen_height = screen_height or 1080
        self._queue: queue.Queue = queue.Queue()
        self._thread: Optional[threading.Thread] = None
        self._root:   Optional[tk.Tk] = None
        self._running = False

        if TK_AVAILABLE:
            self._thread = threading.Thread(target=self._run_tk, daemon=True)
            self._thread.start()

    # ─── Private: tkinter thread ──────────────────────────────────────────────

    def _run_tk(self) -> None:
        try:
            self._root = tk.Tk()
            self._root.title("Phantom HUD")
            self._root.overrideredirect(True)   # no title bar
            self._root.attributes("-topmost", True)

            # Position: top-right corner
            x = self.screen_width  - WIDGET_W - MARGIN
            y = MARGIN
            self._root.geometry(f"{WIDGET_W}x{WIDGET_H}+{x}+{y}")
            self._root.configure(bg="#12121a")

            # ── Status row ────────────────────────────────────────────────────
            self._status_label = tk.Label(
                self._root,
                text="⚡ IDLE",
                fg="#64748b", bg="#12121a",
                font=("JetBrains Mono", 9, "bold"),
                anchor="w", padx=8,
            )
            self._status_label.pack(fill="x", pady=(6, 0))

            # ── Narration row ─────────────────────────────────────────────────
            self._narration_label = tk.Label(
                self._root,
                text="",
                fg="#e2e8f0", bg="#12121a",
                font=("JetBrains Mono", 8),
                anchor="w", padx=8,
                wraplength=WIDGET_W - 16,
                justify="left",
            )
            self._narration_label.pack(fill="x", pady=(2, 6))

            # Thin accent border on the left
            self._border = tk.Frame(self._root, bg="#7c3aed", width=3)
            self._border.place(x=0, y=0, relheight=1.0)

            self._running = True
            self._root.after(50, self._process_queue)
            self._root.mainloop()
        except Exception as e:
            logger.error(f"HUD tkinter error: {e}")

    def _process_queue(self) -> None:
        if not self._running or not self._root:
            return
        try:
            while True:
                cmd, args = self._queue.get_nowait()
                getattr(self, f"_do_{cmd}")(*args)
        except queue.Empty:
            pass
        self._root.after(50, self._process_queue)

    # ─── Private: draw commands (run in tkinter thread) ───────────────────────

    def _do_show_status(self, status: str) -> None:
        if not self._root:
            return
        colors = {
            "LISTENING":  "#10b981",
            "THINKING":   "#f59e0b",
            "EXECUTING":  "#7c3aed",
            "WAITING_CONFIRMATION": "#ef4444",
            "IDLE":       "#64748b",
        }
        color = colors.get(status.upper(), "#64748b")
        self._status_label.configure(text=f"⚡ {status}", fg=color)
        self._border.configure(bg=color)

    def _do_show_narration(self, text: str, duration_ms: int) -> None:
        if not self._root:
            return
        short = text[:80] + ("…" if len(text) > 80 else "")
        self._narration_label.configure(text=short)
        self._root.after(duration_ms, lambda: self._narration_label.configure(text=""))

    def _do_show_target(self, x: int, y: int, width: int, height: int, label: str, confidence: float) -> None:
        # Target highlighting requires a fullscreen overlay — skipped on Wayland.
        # The narration already describes what's being targeted.
        pass

    def _do_hide_target(self) -> None:
        pass

    def _do_toggle(self) -> None:
        if not self._root:
            return
        if self._root.winfo_viewable():
            self._root.withdraw()
        else:
            self._root.deiconify()

    # ─── Public: thread-safe API ──────────────────────────────────────────────

    def show_status(self, status: str) -> None:
        if TK_AVAILABLE and self._running:
            self._queue.put(("show_status", (status,)))

    def show_narration(self, text: str, duration_ms: int = 3000) -> None:
        if TK_AVAILABLE and self._running:
            self._queue.put(("show_narration", (text, duration_ms)))

    def show_target(self, x: int, y: int, width: int = 60, height: int = 30,
                    label: str = "", confidence: float = 1.0) -> None:
        if TK_AVAILABLE and self._running:
            self._queue.put(("show_target", (x, y, width, height, label, confidence)))

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
