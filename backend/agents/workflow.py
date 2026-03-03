"""
WorkflowAgent: Record, store, and replay complex multi-step workflows.
"""
from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime
from typing import Optional
from uuid import uuid4

from google import genai
from google.cloud import firestore

from models.schemas import Action, Workflow, WorkflowStep
from services.redis_bus import RedisBus
from agents.memory import MemoryAgent

logger = logging.getLogger(__name__)


class WorkflowAgent:
    def __init__(self, bus: RedisBus, memory_agent: MemoryAgent):
        self._bus = bus
        self._memory = memory_agent
        api_key = os.getenv("GEMINI_API_KEY", "")
        self._client = genai.Client(api_key=api_key) if api_key else None

        project = os.getenv("GOOGLE_CLOUD_PROJECT")
        try:
            self._db = firestore.AsyncClient(project=project)
            self._col = os.getenv("FIRESTORE_COLLECTION_WORKFLOWS", "phantom_workflows")
        except Exception as e:
            logger.warning(f"WorkflowAgent Firestore unavailable: {e}")
            self._db = None
            self._col = "phantom_workflows"
            self._store: dict[str, Workflow] = {}

    # ─── Recording ────────────────────────────────────────────────────────────

    async def start_recording(self, session_id: str) -> None:
        await self._bus.set_state(f"workflow:recording:{session_id}", [], ttl=7200)
        logger.info(f"Workflow recording started for session {session_id}")

    async def record_action(self, session_id: str, action: Action) -> None:
        key = f"workflow:recording:{session_id}"
        existing = await self._bus.get_state(key) or []
        existing.append(action.model_dump(mode="json"))
        await self._bus.set_state(key, existing, ttl=7200)

    async def stop_and_save(
        self, session_id: str, name: str, description: str = ""
    ) -> Workflow:
        key = f"workflow:recording:{session_id}"
        raw_actions = await self._bus.get_state(key) or []
        await self._bus.delete_state(key)

        steps = []
        for raw in raw_actions:
            try:
                action = Action.model_validate(raw)
                steps.append(WorkflowStep(action=action, delay_ms=500))
            except Exception:
                pass

        return await self.save_workflow_direct(name=name, description=description, steps=steps)

    # ─── CRUD ─────────────────────────────────────────────────────────────────

    async def save_workflow_direct(
        self, name: str, description: str, steps: list[WorkflowStep]
    ) -> Workflow:
        wf = Workflow(
            id=str(uuid4()),
            name=name,
            description=description,
            steps=steps,
            created_at=datetime.utcnow(),
        )
        if self._db:
            try:
                doc_ref = self._db.collection(self._col).document(wf.id)
                await doc_ref.set(wf.model_dump(mode="json"))
            except Exception as e:
                logger.error(f"WorkflowAgent.save Firestore error: {e}")
        else:
            self._store[wf.id] = wf

        # Store reference in memory
        await self._memory.store(
            content=f"Workflow '{name}': {description}",
            memory_type="workflow",
            tags=["workflow", name],
            metadata={"workflow_id": wf.id},
        )
        logger.info(f"Workflow saved: {name} ({len(steps)} steps)")
        return wf

    async def get_workflow(self, name: str) -> Optional[Workflow]:
        """Fuzzy name match."""
        workflows = await self.list_workflows()
        name_lower = name.lower()
        # Exact match first
        for wf in workflows:
            if wf.name.lower() == name_lower:
                return wf
        # Partial match
        for wf in workflows:
            if name_lower in wf.name.lower() or wf.name.lower() in name_lower:
                return wf
        return None

    async def get_workflow_by_id(self, workflow_id: str) -> Optional[Workflow]:
        if self._db:
            try:
                doc = await self._db.collection(self._col).document(workflow_id).get()
                if doc.exists:
                    return Workflow.model_validate(doc.to_dict())
            except Exception as e:
                logger.error(f"get_workflow_by_id error: {e}")
            return None
        return self._store.get(workflow_id)

    async def list_workflows(self) -> list[Workflow]:
        if self._db:
            try:
                docs = await self._db.collection(self._col).get()
                workflows = []
                for doc in docs:
                    try:
                        workflows.append(Workflow.model_validate(doc.to_dict()))
                    except Exception:
                        pass
                return sorted(workflows, key=lambda w: w.created_at, reverse=True)
            except Exception as e:
                logger.error(f"list_workflows error: {e}")
                return []
        return sorted(self._store.values(), key=lambda w: w.created_at, reverse=True)

    async def delete_workflow(self, workflow_id: str) -> None:
        if self._db:
            await self._db.collection(self._col).document(workflow_id).delete()
        else:
            self._store.pop(workflow_id, None)

    async def increment_use_count(self, workflow_id: str) -> None:
        if self._db:
            try:
                doc_ref = self._db.collection(self._col).document(workflow_id)
                await doc_ref.update({"use_count": firestore.Increment(1)})
            except Exception:
                pass
        elif workflow_id in self._store:
            self._store[workflow_id].use_count += 1

    # ─── Replay ───────────────────────────────────────────────────────────────

    async def replay(
        self, workflow: Workflow, parameters: dict = {}
    ) -> list[Action]:
        """
        Return workflow actions with parameter substitution.
        Parameters like {date}, {recipient} are replaced with actual values.
        """
        actions = []
        for step in workflow.steps:
            action = step.action.model_copy(deep=True)
            if parameters:
                # Substitute in narration
                for key, value in parameters.items():
                    action.narration = action.narration.replace(f"{{{key}}}", str(value))
                # Substitute in parameters dict
                for param_key, param_val in action.parameters.items():
                    if isinstance(param_val, str):
                        for slot_key, slot_val in parameters.items():
                            action.parameters[param_key] = param_val.replace(
                                f"{{{slot_key}}}", str(slot_val)
                            )
            actions.append(action)
        return actions

    # ─── Pattern Detection ────────────────────────────────────────────────────

    async def detect_patterns(self, session_id: str) -> list[dict]:
        """Analyze session actions for repeating patterns."""
        if not self._client:
            return []

        audit_log = await self._bus.get_audit_log(session_id, limit=100)
        if len(audit_log) < 5:
            return []

        action_summary = "\n".join(
            f"- {entry.get('action', {}).get('action_type', '?')}: "
            f"{entry.get('action', {}).get('narration', '')}"
            for entry in audit_log[:50]
        )

        try:
            prompt = f"""
Analyze these actions and identify any repeating sequences or patterns.
For each pattern found, provide:
- pattern: description of the sequence
- frequency: how many times it appears
- suggested_name: a short workflow name

Actions:
{action_summary}

Output as JSON array. If no patterns found, output [].
"""
            response = await self._client.aio.models.generate_content(
                model="gemini-2.0-flash", contents=prompt
            )
            json_match = re.search(r"\[.*\]", response.text or "", re.DOTALL)
            if json_match:
                return json.loads(json_match.group(0))
        except Exception as e:
            logger.error(f"detect_patterns error: {e}")
        return []

    async def suggest_automation(self, session_id: str) -> Optional[str]:
        """If patterns detected with 3+ frequency, return suggestion message."""
        patterns = await self.detect_patterns(session_id)
        for p in patterns:
            if p.get("frequency", 0) >= 3:
                return (
                    f"I noticed you do '{p['pattern']}' repeatedly. "
                    f"Want me to save this as the '{p['suggested_name']}' workflow?"
                )
        return None
