from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class ActionType(str, Enum):
    click = "click"
    type = "type"
    scroll = "scroll"
    navigate = "navigate"
    open_app = "open_app"
    key_combo = "key_combo"
    drag = "drag"
    screenshot = "screenshot"
    search_web = "search_web"
    read_clipboard = "read_clipboard"
    write_clipboard = "write_clipboard"
    wait = "wait"


class RiskLevel(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class SessionStatus(str, Enum):
    idle = "idle"
    listening = "listening"
    thinking = "thinking"
    executing = "executing"
    waiting_confirmation = "waiting_confirmation"


class MemoryType(str, Enum):
    episodic = "episodic"
    semantic = "semantic"
    workflow = "workflow"


class ActionTarget(BaseModel):
    type: str  # button, input, link, dropdown, text, coordinate
    label: Optional[str] = None
    selector: Optional[str] = None
    x: Optional[int] = None
    y: Optional[int] = None
    width: Optional[int] = None
    height: Optional[int] = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class Action(BaseModel):
    action_id: str = Field(default_factory=lambda: str(uuid4()))
    action_type: ActionType
    target: Optional[ActionTarget] = None
    parameters: dict[str, Any] = Field(default_factory=dict)
    risk_level: RiskLevel = RiskLevel.low
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    narration: str = ""
    requires_confirmation: bool = False
    undo_strategy: Optional[str] = None
    agent_source: str = "phantom_core"
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ActionResult(BaseModel):
    action_id: str
    success: bool
    error: Optional[str] = None
    screenshot_before: Optional[str] = None  # base64 JPEG
    screenshot_after: Optional[str] = None   # base64 JPEG
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class AuditEntry(BaseModel):
    action: Action
    result: ActionResult


class AgentStatus(BaseModel):
    name: str
    status: str = "idle"  # idle, running, error
    last_activity: Optional[str] = None
    current_task: Optional[str] = None


class SessionState(BaseModel):
    session_id: str
    client_id: str
    status: SessionStatus = SessionStatus.idle
    current_task: Optional[str] = None
    agent_statuses: dict[str, AgentStatus] = Field(default_factory=dict)
    action_queue: list[Action] = Field(default_factory=list)
    emotion_context: Optional[dict[str, float]] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_heartbeat: datetime = Field(default_factory=datetime.utcnow)


class EmotionContext(BaseModel):
    frustration: float = Field(default=0.0, ge=0.0, le=1.0)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    urgency: float = Field(default=0.0, ge=0.0, le=1.0)
    engagement: float = Field(default=0.5, ge=0.0, le=1.0)


class MemoryEntry(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    session_id: Optional[str] = None
    memory_type: MemoryType
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    tags: list[str] = Field(default_factory=list)


class WorkflowStep(BaseModel):
    action: Action
    delay_ms: int = 500


class Workflow(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    description: str = ""
    steps: list[WorkflowStep] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    use_count: int = 0
    tags: list[str] = Field(default_factory=list)


class ConfirmationRequest(BaseModel):
    action: Action
    session_id: str
    timeout_seconds: int = 30
    preview_screenshot: Optional[str] = None


class WebSocketMessage(BaseModel):
    type: str
    payload: dict[str, Any] = Field(default_factory=dict)


# --- Inbound WS message payloads ---

class FramePayload(BaseModel):
    data: str  # base64 JPEG

class AudioPayload(BaseModel):
    data: str  # base64 PCM

class EmotionPayload(BaseModel):
    frustration: float = 0.0
    confidence: float = 0.5
    urgency: float = 0.0
    engagement: float = 0.5

class ConfirmPayload(BaseModel):
    action_id: str

class RejectPayload(BaseModel):
    action_id: str
