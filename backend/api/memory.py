"""
REST API endpoints for memory CRUD.
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from models.schemas import MemoryEntry, MemoryType

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/memory", tags=["memory"])


class CreateMemoryRequest(BaseModel):
    content: str
    memory_type: MemoryType
    tags: list[str] = []
    metadata: dict = {}
    session_id: Optional[str] = None


class UpdateMemoryRequest(BaseModel):
    content: Optional[str] = None
    tags: Optional[list[str]] = None
    metadata: Optional[dict] = None


def get_memory_agent(request):
    return request.app.state.memory_agent


@router.get("", response_model=list[MemoryEntry])
async def list_memories(
    request,
    memory_type: Optional[MemoryType] = None,
    tag: Optional[str] = None,
    limit: int = 50,
):
    agent = get_memory_agent(request)
    entries = await agent.recall(
        query="",
        memory_type=memory_type.value if memory_type else None,
        limit=limit,
    )
    if tag:
        entries = [e for e in entries if tag in e.tags]
    return entries


@router.get("/search")
async def search_memories(request, q: str, limit: int = 20):
    agent = get_memory_agent(request)
    entries = await agent.recall(query=q, limit=limit)
    return {"query": q, "results": entries, "count": len(entries)}


@router.post("", response_model=MemoryEntry)
async def create_memory(body: CreateMemoryRequest, request):
    agent = get_memory_agent(request)
    memory_id = await agent.store(
        content=body.content,
        memory_type=body.memory_type.value,
        tags=body.tags,
        metadata=body.metadata,
    )
    entries = await agent.recall(query=body.content[:50], limit=5)
    for entry in entries:
        if entry.id == memory_id:
            return entry
    raise HTTPException(status_code=500, detail="Memory created but could not be retrieved")


@router.put("/{memory_id}")
async def update_memory(memory_id: str, body: UpdateMemoryRequest, request):
    agent = get_memory_agent(request)
    try:
        await agent.update(memory_id=memory_id, **body.model_dump(exclude_none=True))
        return {"status": "updated", "id": memory_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{memory_id}")
async def delete_memory(memory_id: str, request):
    agent = get_memory_agent(request)
    try:
        await agent.delete(memory_id=memory_id)
        return {"status": "deleted", "id": memory_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
