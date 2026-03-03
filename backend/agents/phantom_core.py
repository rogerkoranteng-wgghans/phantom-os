"""
PhantomCoreAgent: Manages the Gemini Live session, routes actions through
the safety pipeline, and coordinates with specialist agents.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Optional

from fastapi import WebSocket

from agents.safety import SafetyAgent
from agents.memory import MemoryAgent
from models.schemas import Action, RiskLevel, SessionStatus
from services.redis_bus import RedisBus

logger = logging.getLogger(__name__)


class PhantomCoreAgent:
    """
    Top-level agent that:
    1. Owns the GeminiLiveSession
    2. Receives actions from Gemini
    3. Routes them through SafetyAgent
    4. Handles confirmation flow
    5. Pushes confirmed actions to the desktop client
    """

    def __init__(
        self,
        session_id: str,
        bus: RedisBus,
        safety_agent: SafetyAgent,
        memory_agent: MemoryAgent,
    ):
        self.session_id = session_id
        self._bus = bus
        self._safety = safety_agent
        self._memory = memory_agent
        self._websocket: Optional[WebSocket] = None
        self._task_context: str = ""
        self._action_count: int = 0

    def set_websocket(self, ws: WebSocket) -> None:
        self._websocket = ws

    def set_task_context(self, context: str) -> None:
        self._task_context = context

    async def handle_action_pipeline(self, action: Action) -> None:
        """
        Full pipeline: classify risk → check safety → confirmation → queue.
        """
        self._action_count += 1

        # 1. Safety classification
        action = await self._safety.classify(action, self._task_context)

        # 2. Safety gate
        proceed, reason = await self._safety.check(action)
        if not proceed:
            logger.warning(f"Action blocked by safety: {reason}")
            if self._websocket:
                await self._send("text", {"content": f"⚠️ Action blocked: {reason}"})
            return

        # 3. Confirmation gate for high/critical
        if action.requires_confirmation:
            confirmed = await self._request_confirmation(action)
            if not confirmed:
                if self._websocket:
                    await self._send("text", {"content": "Action cancelled — confirmation declined."})
                return

        # 4. Push to desktop agent
        await self._bus.push_action(self.session_id, action)
        if self._websocket:
            await self._send("action", action.model_dump(mode="json"))

        # 5. Audit
        await self._bus.append_audit(
            self.session_id,
            {"action": action.model_dump(mode="json"), "status": "queued"},
        )

        # 6. Update session status
        await self._bus.update_session_state(
            self.session_id, {"status": SessionStatus.executing.value}
        )

        logger.info(
            f"[PhantomCore] Action queued #{self._action_count}: "
            f"{action.action_type.value} | risk={action.risk_level.value} | "
            f"confidence={action.confidence:.2f}"
        )

    async def _request_confirmation(self, action: Action) -> bool:
        """Send confirmation request and wait for user response."""
        await self._bus.set_pending_confirmation(self.session_id, action)
        await self._bus.update_session_state(
            self.session_id,
            {"status": SessionStatus.waiting_confirmation.value},
        )

        if self._websocket:
            await self._send(
                "confirmation_request",
                {"action": action.model_dump(mode="json"), "timeout_seconds": 30},
            )

        # Poll for confirmation (max 30s)
        for _ in range(300):
            await asyncio.sleep(0.1)
            pending = await self._bus.get_pending_confirmation(self.session_id)
            if pending is None:
                # Check if action is now in queue (confirmed) or not (rejected)
                queue = await self._bus.peek_action_queue(self.session_id)
                return any(a.action_id == action.action_id for a in queue)

        # Timeout — reject
        await self._bus.clear_pending_confirmation(self.session_id)
        return False

    async def _send(self, msg_type: str, payload: dict) -> None:
        if self._websocket:
            import json
            try:
                await self._websocket.send_text(
                    json.dumps({"type": msg_type, "payload": payload})
                )
            except Exception as e:
                logger.warning(f"PhantomCore send error: {e}")
