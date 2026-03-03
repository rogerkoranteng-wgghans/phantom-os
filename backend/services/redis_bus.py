"""
Redis-based inter-agent message bus and session state store.
"""
from __future__ import annotations

import json
import logging
from typing import Any, AsyncGenerator, Optional

import redis.asyncio as aioredis

from models.schemas import Action, SessionState

logger = logging.getLogger(__name__)

AUDIT_LOG_MAX = 500  # max audit entries per session


class RedisBus:
    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self._url = redis_url
        self._client: aioredis.Redis | None = None

    async def connect(self) -> None:
        if self._url == "embedded":
            try:
                import fakeredis.aioredis as fakeredis_aio
                self._client = fakeredis_aio.FakeRedis(
                    encoding="utf-8", decode_responses=True
                )
                logger.info("RedisBus: using embedded in-memory store (fakeredis)")
                return
            except ImportError:
                logger.warning("fakeredis not installed — falling back to real Redis")
        self._client = await aioredis.from_url(
            self._url,
            encoding="utf-8",
            decode_responses=True,
        )
        await self._client.ping()
        logger.info("RedisBus connected")

    async def disconnect(self) -> None:
        if self._client:
            await self._client.aclose()
            logger.info("RedisBus disconnected")

    @property
    def client(self) -> aioredis.Redis:
        if not self._client:
            raise RuntimeError("RedisBus not connected — call connect() first")
        return self._client

    # ─── Pub/Sub ──────────────────────────────────────────────────────────────

    async def publish(self, channel: str, message: dict[str, Any]) -> None:
        try:
            await self.client.publish(channel, json.dumps(message))
        except Exception as e:
            logger.error(f"RedisBus.publish error on {channel}: {e}")

    async def subscribe(self, channel: str) -> AsyncGenerator[dict[str, Any], None]:
        pubsub = self.client.pubsub()
        await pubsub.subscribe(channel)
        try:
            async for raw in pubsub.listen():
                if raw["type"] == "message":
                    try:
                        yield json.loads(raw["data"])
                    except json.JSONDecodeError:
                        logger.warning(f"Invalid JSON on channel {channel}")
        finally:
            await pubsub.unsubscribe(channel)
            await pubsub.aclose()

    # ─── Key/Value State ─────────────────────────────────────────────────────

    async def set_state(self, key: str, value: Any, ttl: int = 3600) -> None:
        try:
            serialized = json.dumps(value) if not isinstance(value, str) else value
            await self.client.setex(key, ttl, serialized)
        except Exception as e:
            logger.error(f"RedisBus.set_state error for {key}: {e}")

    async def get_state(self, key: str) -> Any:
        try:
            raw = await self.client.get(key)
            if raw is None:
                return None
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                return raw
        except Exception as e:
            logger.error(f"RedisBus.get_state error for {key}: {e}")
            return None

    async def delete_state(self, key: str) -> None:
        await self.client.delete(key)

    # ─── Action Queue ─────────────────────────────────────────────────────────

    async def push_action(self, session_id: str, action: Action) -> None:
        key = f"session:{session_id}:action_queue"
        await self.client.rpush(key, action.model_dump_json())
        await self.client.expire(key, 3600)

    async def pop_action(self, session_id: str) -> Optional[Action]:
        key = f"session:{session_id}:action_queue"
        raw = await self.client.lpop(key)
        if raw:
            try:
                return Action.model_validate_json(raw)
            except Exception as e:
                logger.error(f"Failed to deserialize action: {e}")
        return None

    async def peek_action_queue(self, session_id: str) -> list[Action]:
        key = f"session:{session_id}:action_queue"
        items = await self.client.lrange(key, 0, -1)
        actions = []
        for item in items:
            try:
                actions.append(Action.model_validate_json(item))
            except Exception:
                pass
        return actions

    async def clear_action_queue(self, session_id: str) -> None:
        await self.client.delete(f"session:{session_id}:action_queue")

    # ─── Session State ────────────────────────────────────────────────────────

    async def get_session_state(self, session_id: str) -> Optional[SessionState]:
        raw = await self.get_state(f"session:{session_id}:state")
        if raw:
            try:
                return SessionState.model_validate(raw)
            except Exception as e:
                logger.error(f"Failed to deserialize session state: {e}")
        return None

    async def update_session_state(self, session_id: str, updates: dict[str, Any]) -> None:
        state = await self.get_session_state(session_id)
        if state is None:
            logger.warning(f"Session {session_id} not found for update")
            return
        state_dict = state.model_dump()
        state_dict.update(updates)
        await self.set_state(f"session:{session_id}:state", state_dict, ttl=7200)

    async def save_session_state(self, session_id: str, state: SessionState) -> None:
        await self.set_state(
            f"session:{session_id}:state",
            state.model_dump(mode="json"),
            ttl=7200,
        )

    async def delete_session_state(self, session_id: str) -> None:
        await self.client.delete(f"session:{session_id}:state")
        await self.client.delete(f"session:{session_id}:action_queue")
        await self.client.delete(f"session:{session_id}:audit_log")
        await self.client.delete(f"session:{session_id}:pending_confirmation")

    # ─── Audit Log ────────────────────────────────────────────────────────────

    async def append_audit(self, session_id: str, entry: dict[str, Any]) -> None:
        key = f"session:{session_id}:audit_log"
        await self.client.rpush(key, json.dumps(entry))
        # Trim to max size
        await self.client.ltrim(key, -AUDIT_LOG_MAX, -1)
        await self.client.expire(key, 86400)  # 24h

    async def get_audit_log(self, session_id: str, limit: int = 100) -> list[dict[str, Any]]:
        key = f"session:{session_id}:audit_log"
        items = await self.client.lrange(key, -limit, -1)
        result = []
        for item in items:
            try:
                result.append(json.loads(item))
            except json.JSONDecodeError:
                pass
        return result

    # ─── Pending Confirmation ─────────────────────────────────────────────────

    async def set_pending_confirmation(self, session_id: str, action: Action) -> None:
        key = f"session:{session_id}:pending_confirmation"
        await self.client.setex(key, 60, action.model_dump_json())

    async def get_pending_confirmation(self, session_id: str) -> Optional[Action]:
        key = f"session:{session_id}:pending_confirmation"
        raw = await self.client.get(key)
        if raw:
            try:
                return Action.model_validate_json(raw)
            except Exception:
                pass
        return None

    async def clear_pending_confirmation(self, session_id: str) -> None:
        await self.client.delete(f"session:{session_id}:pending_confirmation")

    # ─── Agent Status ─────────────────────────────────────────────────────────

    async def set_agent_status(
        self, session_id: str, agent_name: str, status: str, task: Optional[str] = None
    ) -> None:
        key = f"session:{session_id}:agent:{agent_name}"
        await self.client.setex(
            key,
            3600,
            json.dumps({"name": agent_name, "status": status, "current_task": task}),
        )
        # Also publish event
        await self.publish(
            f"session:{session_id}:events",
            {"type": "agent_status", "agent": agent_name, "status": status, "task": task},
        )

    async def get_all_agent_statuses(self, session_id: str) -> dict[str, dict]:
        pattern = f"session:{session_id}:agent:*"
        keys = await self.client.keys(pattern)
        result = {}
        for key in keys:
            raw = await self.client.get(key)
            if raw:
                try:
                    data = json.loads(raw)
                    result[data["name"]] = data
                except Exception:
                    pass
        return result


# Singleton
_bus: RedisBus | None = None


def get_bus() -> RedisBus:
    global _bus
    if _bus is None:
        _bus = RedisBus()
    return _bus
