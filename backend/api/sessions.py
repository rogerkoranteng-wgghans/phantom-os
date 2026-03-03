"""
REST API endpoints for session management and audit log.
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from models.schemas import Action, SessionState
from services.session import SessionManager
from services.redis_bus import RedisBus

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/sessions", tags=["sessions"])


# Dependency injected from main.py via app.state
def get_session_manager(request) -> SessionManager:
    return request.app.state.session_manager


def get_bus(request) -> RedisBus:
    return request.app.state.bus


class ConfirmActionRequest(BaseModel):
    action_id: str


class RejectActionRequest(BaseModel):
    action_id: str
    reason: Optional[str] = None


@router.get("", response_model=list[SessionState])
async def list_sessions(request):
    manager: SessionManager = get_session_manager(request)
    return await manager.list_sessions()


@router.get("/{session_id}", response_model=SessionState)
async def get_session(session_id: str, request):
    manager: SessionManager = get_session_manager(request)
    state = await manager.get_session(session_id)
    if not state:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    return state


@router.delete("/{session_id}")
async def terminate_session(session_id: str, request):
    manager: SessionManager = get_session_manager(request)
    state = await manager.get_session(session_id)
    if not state:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    await manager.terminate_session(session_id)
    return {"status": "terminated", "session_id": session_id}


@router.get("/{session_id}/audit")
async def get_audit_log(session_id: str, request, limit: int = 100):
    bus: RedisBus = get_bus(request)
    entries = await bus.get_audit_log(session_id, limit=min(limit, 500))
    return {"session_id": session_id, "entries": entries, "count": len(entries)}


@router.post("/{session_id}/confirm")
async def confirm_action(session_id: str, body: ConfirmActionRequest, request):
    bus: RedisBus = get_bus(request)
    pending = await bus.get_pending_confirmation(session_id)
    if not pending:
        raise HTTPException(status_code=404, detail="No pending confirmation for this session")
    if pending.action_id != body.action_id:
        raise HTTPException(status_code=400, detail="Action ID mismatch")
    # Push confirmed action to queue
    await bus.push_action(session_id, pending)
    await bus.clear_pending_confirmation(session_id)
    # Notify via pub/sub
    await bus.publish(
        f"session:{session_id}:events",
        {"type": "action_confirmed", "action_id": body.action_id},
    )
    return {"status": "confirmed", "action_id": body.action_id}


@router.post("/{session_id}/reject")
async def reject_action(session_id: str, body: RejectActionRequest, request):
    bus: RedisBus = get_bus(request)
    await bus.clear_pending_confirmation(session_id)
    await bus.publish(
        f"session:{session_id}:events",
        {"type": "action_rejected", "action_id": body.action_id, "reason": body.reason},
    )
    return {"status": "rejected", "action_id": body.action_id}
