"""
Session lifecycle manager for Phantom OS.
"""
from __future__ import annotations

import logging
from datetime import datetime
from uuid import uuid4

from models.schemas import AgentStatus, SessionState, SessionStatus
from services.redis_bus import RedisBus

logger = logging.getLogger(__name__)

AGENT_NAMES = [
    "phantom_core",
    "orchestrator",
    "safety",
    "memory",
    "research",
    "prediction",
    "workflow",
    "communication",
]


class SessionManager:
    def __init__(self, bus: RedisBus):
        self._bus = bus
        # In-memory index for fast lookups
        self._sessions: dict[str, SessionState] = {}

    async def create_session(self, client_id: str) -> str:
        session_id = str(uuid4())
        agent_statuses = {
            name: AgentStatus(name=name, status="idle")
            for name in AGENT_NAMES
        }
        state = SessionState(
            session_id=session_id,
            client_id=client_id,
            status=SessionStatus.idle,
            agent_statuses=agent_statuses,
        )
        self._sessions[session_id] = state
        await self._bus.save_session_state(session_id, state)
        logger.info(f"Session created: {session_id} for client {client_id}")
        return session_id

    async def get_session(self, session_id: str) -> SessionState | None:
        # Check in-memory first
        if session_id in self._sessions:
            return self._sessions[session_id]
        # Fall back to Redis
        state = await self._bus.get_session_state(session_id)
        if state:
            self._sessions[session_id] = state
        return state

    async def update_session(self, session_id: str, **kwargs) -> None:
        state = await self.get_session(session_id)
        if not state:
            logger.warning(f"update_session: session {session_id} not found")
            return
        for key, value in kwargs.items():
            if hasattr(state, key):
                setattr(state, key, value)
        state.last_heartbeat = datetime.utcnow()
        self._sessions[session_id] = state
        await self._bus.save_session_state(session_id, state)

    async def update_agent_status(
        self, session_id: str, agent_name: str, status: str, task: str | None = None
    ) -> None:
        state = await self.get_session(session_id)
        if not state:
            return
        if agent_name in state.agent_statuses:
            state.agent_statuses[agent_name].status = status
            state.agent_statuses[agent_name].last_activity = datetime.utcnow().isoformat()
            state.agent_statuses[agent_name].current_task = task
        else:
            state.agent_statuses[agent_name] = AgentStatus(
                name=agent_name, status=status, current_task=task
            )
        self._sessions[session_id] = state
        await self._bus.save_session_state(session_id, state)
        await self._bus.set_agent_status(session_id, agent_name, status, task)

    async def terminate_session(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)
        await self._bus.delete_session_state(session_id)
        logger.info(f"Session terminated: {session_id}")

    async def list_sessions(self) -> list[SessionState]:
        return list(self._sessions.values())

    async def heartbeat(self, session_id: str) -> None:
        await self.update_session(session_id, last_heartbeat=datetime.utcnow())
