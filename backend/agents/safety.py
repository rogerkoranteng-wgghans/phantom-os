"""
SafetyAgent: Pre-execution risk analysis and action verification.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Optional

from google import genai

from models.schemas import Action, ActionResult, ActionType, RiskLevel
from services.action_schema import risk_score
from services.redis_bus import RedisBus

logger = logging.getLogger(__name__)


class SafetyAgent:
    def __init__(self, bus: RedisBus):
        self._bus = bus
        api_key = os.getenv("GEMINI_API_KEY", "")
        self._client = genai.Client(api_key=api_key) if api_key else None

    async def classify(self, action: Action, screen_context: str = "") -> Action:
        """
        Re-evaluate action risk level using rule-based + AI classification.
        Returns the action with potentially upgraded risk_level.
        """
        # Rule-based re-classification first
        rule_risk = risk_score(action)
        if rule_risk.value > action.risk_level.value:
            action.risk_level = rule_risk

        # AI re-classification for complex cases (high/critical boundary)
        if action.risk_level in (RiskLevel.medium, RiskLevel.high) and screen_context and self._client:
            try:
                prompt = f"""
You are a safety classifier for an AI computer agent.

Action: {action.action_type.value}
Target: {action.target.model_dump() if action.target else 'none'}
Parameters: {json.dumps(action.parameters)}
Narration: {action.narration}
Screen context: {screen_context[:500]}

Classify the risk level: low, medium, high, or critical.
Output ONLY the risk level word, nothing else.
"""
                response = await self._client.aio.models.generate_content(
                    model="gemini-2.0-flash",
                    contents=prompt,
                )
                raw = response.text.strip().lower()
                try:
                    ai_risk = RiskLevel(raw)
                    if ai_risk.value > action.risk_level.value:
                        action.risk_level = ai_risk
                        logger.info(f"Safety AI upgraded risk to {ai_risk} for {action.action_type}")
                except ValueError:
                    pass
            except Exception as e:
                logger.warning(f"SafetyAgent AI classify failed: {e}")

        # Auto-set requires_confirmation for high/critical
        if action.risk_level in (RiskLevel.high, RiskLevel.critical):
            action.requires_confirmation = True

        return action

    async def check(self, action: Action) -> tuple[bool, str]:
        """
        Final go/no-go decision before action is queued.
        Returns (proceed: bool, reason: str).
        """
        # Block truly dangerous combos unconditionally
        if action.action_type == ActionType.key_combo:
            keys = set(k.lower() for k in action.parameters.get("keys", []))
            dangerous = {
                frozenset(["ctrl", "shift", "delete"]),
                frozenset(["shift", "delete"]),
            }
            if any(keys >= d for d in dangerous):
                return False, "Permanently destructive keyboard shortcut blocked"

        # All other actions: allow, but high/critical need confirmation (handled upstream)
        return True, "ok"

    async def log_action(
        self, session_id: str, action: Action, result: ActionResult
    ) -> None:
        """Store action + result in audit log."""
        entry = {
            "action": action.model_dump(mode="json"),
            "result": result.model_dump(mode="json"),
        }
        await self._bus.append_audit(session_id, entry)
        logger.debug(f"Audit logged: {action.action_type} → success={result.success}")

    async def get_audit_log(
        self, session_id: str, limit: int = 100
    ) -> list[dict]:
        return await self._bus.get_audit_log(session_id, limit=limit)

    async def plan_undo(self, action: Action) -> Optional[Action]:
        """Generate an undo action for reversible operations."""
        from models.schemas import ActionTarget

        if action.action_type == ActionType.key_combo:
            keys = action.parameters.get("keys", [])
            # Undo for common operations
            if set(k.lower() for k in keys) == {"ctrl", "z"}:
                return None  # Can't undo an undo
            return Action(
                action_type=ActionType.key_combo,
                parameters={"keys": ["ctrl", "z"]},
                risk_level=RiskLevel.low,
                narration="Undoing last action",
                agent_source="safety",
            )

        if action.action_type == ActionType.type:
            text = action.parameters.get("text", "")
            return Action(
                action_type=ActionType.key_combo,
                parameters={"keys": ["ctrl", "z"] * len(text)},
                risk_level=RiskLevel.low,
                narration="Undoing typed text",
                agent_source="safety",
            )

        return None
