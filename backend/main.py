"""
Phantom OS — Backend Entry Point
FastAPI app with WebSocket for real-time Gemini Live streaming.
"""
from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
from contextlib import asynccontextmanager
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

from agents.orchestrator import OrchestratorAgent
from agents.safety import SafetyAgent
from agents.memory import MemoryAgent
from agents.research import ResearchAgent
from agents.workflow import WorkflowAgent
from agents.prediction import PredictionAgent
from agents.communication import CommunicationAgent
from agents.phantom_core import PhantomCoreAgent
from models.schemas import (
    Action,
    RiskLevel,
    SessionStatus,
    WebSocketMessage,
)
from services.gemini_live import GeminiLiveSession
from services.redis_bus import RedisBus, get_bus
from services.session import SessionManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

# ─── Active WebSocket connections keyed by session_id ────────────────────────
active_connections: dict[str, WebSocket] = {}
active_gemini_sessions: dict[str, GeminiLiveSession] = {}
active_phantom_agents: dict[str, PhantomCoreAgent] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    bus = get_bus()
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
    bus._url = redis_url
    await bus.connect()

    app.state.bus = bus
    app.state.session_manager = SessionManager(bus)
    app.state.memory_agent = MemoryAgent(bus)
    app.state.workflow_agent = WorkflowAgent(bus, app.state.memory_agent)
    app.state.research_agent = ResearchAgent()
    app.state.orchestrator_agent = OrchestratorAgent(
        bus,
        app.state.memory_agent,
        app.state.research_agent,
        app.state.workflow_agent,
    )
    app.state.safety_agent = SafetyAgent(bus)
    app.state.prediction_agent = PredictionAgent(bus)
    app.state.communication_agent = CommunicationAgent(app.state.memory_agent)

    logger.info("🚀 Phantom OS backend started")
    yield

    # Shutdown
    for session_id, gs in list(active_gemini_sessions.items()):
        await gs.stop()
    await bus.disconnect()
    logger.info("Phantom OS backend stopped")


app = FastAPI(title="Phantom OS", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Routers ─────────────────────────────────────────────────────────────────
from api.sessions import router as sessions_router
from api.memory import router as memory_router
from api.workflows import router as workflows_router

app.include_router(sessions_router)
app.include_router(memory_router)
app.include_router(workflows_router)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "phantom-os-backend"}


# ─── WebSocket endpoint ───────────────────────────────────────────────────────

async def _send_ws(ws: WebSocket, msg_type: str, payload: dict[str, Any]) -> None:
    try:
        await ws.send_text(json.dumps({"type": msg_type, "payload": payload}))
    except Exception:
        pass


@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    await websocket.accept()
    active_connections[session_id] = websocket

    bus: RedisBus = app.state.bus
    session_manager: SessionManager = app.state.session_manager
    safety_agent: SafetyAgent = app.state.safety_agent
    memory_agent: MemoryAgent = app.state.memory_agent
    prediction_agent: PredictionAgent = app.state.prediction_agent

    # Create or resume session
    existing = await session_manager.get_session(session_id)
    if not existing:
        await session_manager.create_session(session_id)

    await session_manager.update_session(session_id, status=SessionStatus.listening)

    # ── Callbacks from GeminiLiveSession ──────────────────────────────────────

    async def on_action(action: Action) -> None:
        """Called when Gemini produces an action command."""
        # 1. Safety check + risk re-classification
        action = await safety_agent.classify(action, screen_context="")
        proceed, reason = await safety_agent.check(action)

        if not proceed:
            # Log blocked action
            await _send_ws(websocket, "text", {"content": f"⚠️ Blocked: {reason}"})
            return

        if action.requires_confirmation:
            # Hold for user confirmation
            await bus.set_pending_confirmation(session_id, action)
            await session_manager.update_session(
                session_id, status=SessionStatus.waiting_confirmation
            )
            await _send_ws(
                websocket,
                "confirmation_request",
                {"action": action.model_dump(mode="json"), "timeout_seconds": 30},
            )
            # Wait for confirmation event (up to 30s)
            confirmed = await _wait_for_confirmation(session_id, bus, timeout=30)
            if not confirmed:
                await bus.clear_pending_confirmation(session_id)
                await _send_ws(websocket, "text", {"content": "Action cancelled — no confirmation received."})
                await session_manager.update_session(session_id, status=SessionStatus.listening)
                return
            await session_manager.update_session(session_id, status=SessionStatus.executing)

        # 2. Push to action queue (desktop agent polls this)
        await bus.push_action(session_id, action)

        # 3. Send action to desktop client
        await _send_ws(websocket, "action", action.model_dump(mode="json"))

        # 4. Update prediction agent
        asyncio.create_task(
            prediction_agent.update_prediction_queue(session_id, [])
        )

        # 5. Record in audit log
        await bus.append_audit(
            session_id,
            {"action": action.model_dump(mode="json"), "status": "queued"},
        )

        await session_manager.update_session(session_id, status=SessionStatus.listening)

    async def on_audio(audio_bytes: bytes) -> None:
        """Forward Gemini voice output to desktop client."""
        audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")
        await _send_ws(websocket, "audio", {"data": audio_b64})

    async def on_text(text: str) -> None:
        """Forward Gemini text output to dashboard and desktop client."""
        await _send_ws(websocket, "text", {"content": text})

    # ── Start Gemini Live session ─────────────────────────────────────────────
    gemini_session = GeminiLiveSession(
        session_id=session_id,
        on_action=on_action,
        on_audio=on_audio,
        on_text=on_text,
    )

    try:
        await gemini_session.start()
        active_gemini_sessions[session_id] = gemini_session

        # Notify client that session is ready
        state = await session_manager.get_session(session_id)
        await _send_ws(
            websocket,
            "session_state",
            state.model_dump(mode="json") if state else {"session_id": session_id},
        )

        # ── Main receive loop ─────────────────────────────────────────────────
        while True:
            try:
                raw = await websocket.receive_text()
                msg = json.loads(raw)
                msg_type = msg.get("type", "")
                payload = msg.get("payload", {})

                if msg_type == "frame":
                    frame_b64 = payload.get("data", "")
                    if frame_b64:
                        await gemini_session.send_frame(frame_b64)

                elif msg_type == "audio":
                    audio_b64 = payload.get("data", "")
                    if audio_b64:
                        await gemini_session.send_audio(audio_b64)

                elif msg_type == "end_of_turn":
                    await gemini_session.send_end_of_turn()
                    await session_manager.update_session(
                        session_id, status=SessionStatus.thinking
                    )

                elif msg_type == "emotion":
                    await session_manager.update_session(
                        session_id, emotion_context=payload
                    )
                    # If highly frustrated, inject context into Gemini
                    if payload.get("frustration", 0) > 0.7:
                        await gemini_session.send_text(
                            "[SYSTEM: The user appears frustrated. Be extra careful and ask for confirmation on next action.]"
                        )

                elif msg_type == "confirm_action":
                    action_id = payload.get("action_id", "")
                    pending = await bus.get_pending_confirmation(session_id)
                    if pending and pending.action_id == action_id:
                        await bus.push_action(session_id, pending)
                        await bus.clear_pending_confirmation(session_id)
                        await _send_ws(websocket, "action", pending.model_dump(mode="json"))
                        await session_manager.update_session(
                            session_id, status=SessionStatus.executing
                        )

                elif msg_type == "reject_action":
                    await bus.clear_pending_confirmation(session_id)
                    await session_manager.update_session(
                        session_id, status=SessionStatus.listening
                    )
                    await gemini_session.send_text(
                        "[SYSTEM: User rejected the last action. Please reconsider and suggest an alternative.]"
                    )

                elif msg_type == "action_result":
                    # Desktop agent reporting back execution result
                    await bus.append_audit(session_id, payload)
                    success = payload.get("success", True)
                    if not success:
                        error = payload.get("error", "Unknown error")
                        await gemini_session.send_text(
                            f"[SYSTEM: The last action failed with error: {error}. Please adapt and try a different approach.]"
                        )

                elif msg_type == "heartbeat":
                    await session_manager.heartbeat(session_id)

            except WebSocketDisconnect:
                break
            except json.JSONDecodeError as e:
                logger.warning(f"Invalid JSON from client: {e}")

    except Exception as e:
        logger.error(f"WebSocket error for session {session_id}: {e}")
    finally:
        # Cleanup
        active_connections.pop(session_id, None)
        if session_id in active_gemini_sessions:
            gs = active_gemini_sessions.pop(session_id)
            await gs.stop()
        await session_manager.update_session(session_id, status=SessionStatus.idle)
        logger.info(f"WebSocket disconnected: {session_id}")


async def _wait_for_confirmation(
    session_id: str, bus: RedisBus, timeout: int = 30
) -> bool:
    """Poll Redis for confirmation event up to timeout seconds."""
    for _ in range(timeout * 10):  # check every 100ms
        await asyncio.sleep(0.1)
        pending = await bus.get_pending_confirmation(session_id)
        if pending is None:
            # Cleared — either confirmed (action was pushed to queue) or rejected
            # Check if action is in queue
            actions = await bus.peek_action_queue(session_id)
            return len(actions) > 0
    return False
