"""
WebSocket client connecting the desktop agent to the Phantom OS backend.
Auto-reconnects with exponential backoff.
"""
from __future__ import annotations

import asyncio
import base64
import json
import logging
from typing import Any, Callable, Awaitable, Optional

import websockets
import websockets.exceptions

logger = logging.getLogger(__name__)


class PhantomClient:
    def __init__(self, backend_url: str, session_id: str):
        # Convert http(s) to ws(s), handle ws:// prefix
        if backend_url.startswith("http://"):
            backend_url = "ws://" + backend_url[7:]
        elif backend_url.startswith("https://"):
            backend_url = "wss://" + backend_url[8:]
        self._url = f"{backend_url}/ws/{session_id}"
        self.session_id = session_id
        self._ws = None
        self._running = False
        self._reconnect_delay = 1.0

        # Dispatch callbacks
        self._on_action: Optional[Callable[[dict], Awaitable[None]]] = None
        self._on_audio: Optional[Callable[[bytes], Awaitable[None]]] = None
        self._on_text: Optional[Callable[[str], Awaitable[None]]] = None
        self._on_confirmation: Optional[Callable[[dict], Awaitable[None]]] = None
        self._on_session_state: Optional[Callable[[dict], Awaitable[None]]] = None

    def on_action(self, fn: Callable[[dict], Awaitable[None]]) -> None:
        self._on_action = fn

    def on_audio(self, fn: Callable[[bytes], Awaitable[None]]) -> None:
        self._on_audio = fn

    def on_text(self, fn: Callable[[str], Awaitable[None]]) -> None:
        self._on_text = fn

    def on_confirmation(self, fn: Callable[[dict], Awaitable[None]]) -> None:
        self._on_confirmation = fn

    def on_session_state(self, fn: Callable[[dict], Awaitable[None]]) -> None:
        self._on_session_state = fn

    async def connect(self) -> None:
        self._running = True
        while self._running:
            try:
                logger.info(f"Connecting to {self._url}")
                async with websockets.connect(
                    self._url,
                    ping_interval=None,   # Cloud Run handles keepalive; client pings cause timeout
                    max_size=10 * 1024 * 1024,  # 10MB for large frames
                ) as ws:
                    self._ws = ws
                    self._reconnect_delay = 1.0  # Reset on successful connection
                    logger.info(f"Connected to Phantom OS backend (session: {self.session_id})")
                    # Run receive loop and heartbeat concurrently
                    await asyncio.gather(
                        self._receive_loop(),
                        self._heartbeat_loop(),
                        return_exceptions=True,
                    )
            except websockets.exceptions.ConnectionClosed as e:
                logger.warning(f"Connection closed: {e}")
            except ConnectionRefusedError:
                logger.warning(f"Connection refused — backend may not be running")
            except Exception as e:
                logger.error(f"WebSocket error: {e}")

            if self._running:
                logger.info(f"Reconnecting in {self._reconnect_delay:.1f}s...")
                await asyncio.sleep(self._reconnect_delay)
                self._reconnect_delay = min(30.0, self._reconnect_delay * 2)

    async def _heartbeat_loop(self) -> None:
        """Send application-level heartbeat every 15s to keep Cloud Run WS alive."""
        while self._ws and not self._ws.closed:
            await asyncio.sleep(15)
            if self._ws and not self._ws.closed:
                await self._send("heartbeat", {})

    async def _receive_loop(self) -> None:
        async for raw in self._ws:
            try:
                msg = json.loads(raw)
                msg_type = msg.get("type", "")
                payload = msg.get("payload", {})

                logger.info(f"[CLIENT←WS] Received message type='{msg_type}'")

                if msg_type == "action" and self._on_action:
                    await self._on_action(payload)

                elif msg_type == "audio" and self._on_audio:
                    audio_b64 = payload.get("data", "")
                    logger.info(f"[CLIENT←WS] Audio message: audio_b64 len={len(audio_b64)}, _on_audio set={self._on_audio is not None}")
                    if audio_b64:
                        audio_bytes = base64.b64decode(audio_b64)
                        await self._on_audio(audio_bytes)

                elif msg_type == "text" and self._on_text:
                    await self._on_text(payload.get("content", ""))

                elif msg_type == "confirmation_request" and self._on_confirmation:
                    await self._on_confirmation(payload)

                elif msg_type == "session_state" and self._on_session_state:
                    await self._on_session_state(payload)

                else:
                    logger.info(f"[CLIENT←WS] Unhandled message type: '{msg_type}' (handler set: {bool(getattr(self, f'_on_{msg_type}', None))})")

            except json.JSONDecodeError:
                logger.warning("Invalid JSON from backend")
            except Exception as e:
                logger.error(f"Error handling message: {e}", exc_info=True)

    async def _send(self, msg_type: str, payload: dict[str, Any]) -> None:
        if self._ws and not self._ws.closed:
            try:
                await self._ws.send(json.dumps({"type": msg_type, "payload": payload}))
            except Exception as e:
                logger.error(f"Send error: {e}")

    async def send_frame(self, frame_b64: str) -> None:
        await self._send("frame", {"data": frame_b64})

    async def send_audio(self, audio_b64: str) -> None:
        await self._send("audio", {"data": audio_b64})

    async def send_end_of_turn(self) -> None:
        await self._send("end_of_turn", {})

    async def send_emotion(self, emotion_data: dict) -> None:
        await self._send("emotion", emotion_data)

    async def send_action_result(self, action_id: str, success: bool, error: str = "", screenshot_after: str = "") -> None:
        await self._send("action_result", {
            "action_id": action_id,
            "success": success,
            "error": error,
            "screenshot_after": screenshot_after,
        })

    async def confirm_action(self, action_id: str) -> None:
        await self._send("confirm_action", {"action_id": action_id})

    async def reject_action(self, action_id: str) -> None:
        await self._send("reject_action", {"action_id": action_id})

    async def heartbeat(self) -> None:
        await self._send("heartbeat", {})

    async def disconnect(self) -> None:
        self._running = False
        if self._ws:
            await self._ws.close()
