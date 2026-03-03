"""
MemoryAgent: Three-tier memory system using Firestore.
- Episodic: past events with context
- Semantic: user preferences and patterns
- Workflow: saved multi-step workflows
"""
from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import Optional
from uuid import uuid4

from google import genai
from google.cloud import firestore

from models.schemas import MemoryEntry, MemoryType, Workflow, WorkflowStep
from services.redis_bus import RedisBus

logger = logging.getLogger(__name__)


class MemoryAgent:
    def __init__(self, bus: RedisBus):
        self._bus = bus
        api_key = os.getenv("GEMINI_API_KEY", "")
        self._client = genai.Client(api_key=api_key) if api_key else None

        project = os.getenv("GOOGLE_CLOUD_PROJECT")
        try:
            self._db = firestore.AsyncClient(project=project)
            self._memory_col = os.getenv("FIRESTORE_COLLECTION_MEMORY", "phantom_memory")
            self._workflow_col = os.getenv("FIRESTORE_COLLECTION_WORKFLOWS", "phantom_workflows")
            logger.info("MemoryAgent: Firestore connected")
        except Exception as e:
            logger.warning(f"MemoryAgent: Firestore unavailable ({e}), using in-memory fallback")
            self._db = None
            self._memory_col = "phantom_memory"
            self._workflow_col = "phantom_workflows"
            # In-memory fallback
            self._mem_store: dict[str, MemoryEntry] = {}
            self._wf_store: dict[str, Workflow] = {}

    # ─── Memory CRUD ──────────────────────────────────────────────────────────

    async def store(
        self,
        content: str,
        memory_type: str,
        tags: list[str] = [],
        metadata: dict = {},
        session_id: Optional[str] = None,
    ) -> str:
        entry = MemoryEntry(
            id=str(uuid4()),
            session_id=session_id,
            memory_type=MemoryType(memory_type),
            content=content,
            tags=tags,
            metadata=metadata,
        )
        if self._db:
            try:
                doc_ref = self._db.collection(self._memory_col).document(entry.id)
                await doc_ref.set(entry.model_dump(mode="json"))
            except Exception as e:
                logger.error(f"MemoryAgent.store Firestore error: {e}")
        else:
            self._mem_store[entry.id] = entry
        logger.info(f"Memory stored [{memory_type}]: {content[:60]}...")
        return entry.id

    async def recall(
        self,
        query: str,
        memory_type: Optional[str] = None,
        limit: int = 10,
    ) -> list[MemoryEntry]:
        if self._db:
            try:
                col = self._db.collection(self._memory_col)
                q = col
                if memory_type:
                    q = q.where("memory_type", "==", memory_type)
                q = q.order_by("created_at", direction=firestore.Query.DESCENDING).limit(limit * 3)
                docs = await q.get()
                entries = []
                for doc in docs:
                    try:
                        entries.append(MemoryEntry.model_validate(doc.to_dict()))
                    except Exception:
                        pass
                # Simple text filter if query provided
                if query:
                    q_lower = query.lower()
                    entries = [e for e in entries if q_lower in e.content.lower()]
                return entries[:limit]
            except Exception as e:
                logger.error(f"MemoryAgent.recall Firestore error: {e}")
                return []
        else:
            entries = list(self._mem_store.values())
            if memory_type:
                entries = [e for e in entries if e.memory_type.value == memory_type]
            if query:
                q_lower = query.lower()
                entries = [e for e in entries if q_lower in e.content.lower()]
            entries.sort(key=lambda e: e.created_at, reverse=True)
            return entries[:limit]

    async def update(self, memory_id: str, **kwargs) -> None:
        if self._db:
            doc_ref = self._db.collection(self._memory_col).document(memory_id)
            await doc_ref.update(kwargs)
        elif memory_id in self._mem_store:
            entry = self._mem_store[memory_id]
            for k, v in kwargs.items():
                if hasattr(entry, k):
                    setattr(entry, k, v)

    async def delete(self, memory_id: str) -> None:
        if self._db:
            await self._db.collection(self._memory_col).document(memory_id).delete()
        else:
            self._mem_store.pop(memory_id, None)

    # ─── Context Builder ──────────────────────────────────────────────────────

    async def get_user_context(self, session_id: str) -> dict:
        """Build a context dict with relevant memories for prompting."""
        episodic = await self.recall(query="", memory_type="episodic", limit=5)
        semantic = await self.recall(query="", memory_type="semantic", limit=10)

        return {
            "recent_events": [e.content for e in episodic],
            "user_preferences": [e.content for e in semantic],
            "tags": list({tag for e in episodic + semantic for tag in e.tags}),
        }

    # ─── Session Learning ─────────────────────────────────────────────────────

    async def learn_from_session(
        self, session_id: str, actions: list
    ) -> None:
        """Extract patterns from session actions and store as semantic memories."""
        if not self._client or not actions:
            return
        try:
            action_summary = "\n".join(
                f"- {a.action_type.value}: {a.narration}" for a in actions[:30]
            )
            prompt = f"""
Analyze these actions the user performed in a session and extract 2-4 concise preference/pattern statements.
Format each as a single sentence starting with "User".

Actions:
{action_summary}

Output ONLY the statements, one per line.
"""
            response = await self._client.aio.models.generate_content(
                model="gemini-2.0-flash", contents=prompt
            )
            lines = [l.strip() for l in response.text.strip().split("\n") if l.strip()]
            for line in lines[:4]:
                await self.store(
                    content=line,
                    memory_type="semantic",
                    tags=["auto_learned", session_id],
                    metadata={"source": "session_learning"},
                )
            logger.info(f"Learned {len(lines)} preferences from session {session_id}")
        except Exception as e:
            logger.error(f"learn_from_session error: {e}")
