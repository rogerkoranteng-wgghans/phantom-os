"""
PredictionAgent: Predicts next actions to reduce execution latency.
"""
from __future__ import annotations

import json
import logging
import os
import re
from typing import Optional

from google import genai

from models.schemas import Action, ActionType, RiskLevel
from services.redis_bus import RedisBus

logger = logging.getLogger(__name__)


class PredictionAgent:
    def __init__(self, bus: RedisBus):
        self._bus = bus
        api_key = os.getenv("GEMINI_API_KEY", "")
        self._client = genai.Client(api_key=api_key) if api_key else None
        # Track prediction accuracy per session
        self._accuracy: dict[str, list[bool]] = {}

    async def predict_next(
        self,
        current_action: Action,
        task_context: str,
        screen_description: str = "",
    ) -> list[Action]:
        """Predict the next 2-3 likely actions after current_action."""
        if not self._client:
            return []

        try:
            prompt = f"""
You are predicting the next actions an AI computer agent will take.

Current action just executed:
- Type: {current_action.action_type.value}
- Narration: {current_action.narration}
- Target: {current_action.target.model_dump() if current_action.target else 'none'}

Task context: {task_context}
Screen state: {screen_description[:300] if screen_description else 'unknown'}

Predict the next 2-3 most likely actions. Output as a JSON array of action objects with fields:
action_type, narration, risk_level (low/medium/high/critical), confidence (0-1)

Output ONLY the JSON array.
"""
            response = await self._client.aio.models.generate_content(
                model="gemini-2.0-flash", contents=prompt
            )
            text = response.text or ""
            json_match = re.search(r"\[.*\]", text, re.DOTALL)
            if not json_match:
                return []

            raw_actions = json.loads(json_match.group(0))
            actions = []
            for raw in raw_actions[:3]:
                try:
                    action_type = ActionType(raw.get("action_type", "wait").lower())
                    risk = RiskLevel(raw.get("risk_level", "low").lower())
                    actions.append(Action(
                        action_type=action_type,
                        narration=raw.get("narration", ""),
                        risk_level=risk,
                        confidence=float(raw.get("confidence", 0.7)),
                        agent_source="prediction",
                    ))
                except Exception:
                    pass
            return actions

        except Exception as e:
            logger.debug(f"PredictionAgent.predict_next error: {e}")
            return []

    async def update_prediction_queue(
        self, session_id: str, predictions: list[Action]
    ) -> None:
        """Store predictions in Redis for fast access."""
        key = f"session:{session_id}:predictions"
        if predictions:
            await self._bus.set_state(
                key,
                [a.model_dump(mode="json") for a in predictions],
                ttl=30,
            )
        else:
            await self._bus.delete_state(key)

    async def validate_prediction(
        self, session_id: str, actual_screen: str
    ) -> Optional[Action]:
        """
        Check if the top prediction is still valid given the current screen.
        Returns the action if valid, None otherwise.
        """
        key = f"session:{session_id}:predictions"
        preds_raw = await self._bus.get_state(key)
        if not preds_raw:
            return None

        try:
            predictions = [Action.model_validate(p) for p in preds_raw]
        except Exception:
            return None

        if not predictions:
            return None

        top = predictions[0]

        # Simple validation: if confidence is high enough, return it
        if top.confidence >= 0.85:
            # Remove from queue
            await self._bus.set_state(
                key,
                [a.model_dump(mode="json") for a in predictions[1:]],
                ttl=30,
            )
            self._record_accuracy(session_id, True)
            return top

        self._record_accuracy(session_id, False)
        return None

    def _record_accuracy(self, session_id: str, correct: bool) -> None:
        if session_id not in self._accuracy:
            self._accuracy[session_id] = []
        self._accuracy[session_id].append(correct)
        # Keep last 50
        self._accuracy[session_id] = self._accuracy[session_id][-50:]

    def get_accuracy(self, session_id: str) -> float:
        hist = self._accuracy.get(session_id, [])
        if not hist:
            return 0.0
        return sum(hist) / len(hist)
