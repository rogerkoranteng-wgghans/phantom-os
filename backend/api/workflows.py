"""
REST API endpoints for workflow CRUD.
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from models.schemas import Workflow

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/workflows", tags=["workflows"])


class CreateWorkflowRequest(BaseModel):
    name: str
    description: str = ""
    steps: list[dict] = []
    tags: list[str] = []


class ExecuteWorkflowRequest(BaseModel):
    session_id: str
    parameters: dict = {}


def get_workflow_agent(request):
    return request.app.state.workflow_agent


def get_bus(request):
    return request.app.state.bus


@router.get("", response_model=list[Workflow])
async def list_workflows(request):
    agent = get_workflow_agent(request)
    return await agent.list_workflows()


@router.get("/{workflow_id}", response_model=Workflow)
async def get_workflow(workflow_id: str, request):
    agent = get_workflow_agent(request)
    wf = await agent.get_workflow_by_id(workflow_id)
    if not wf:
        raise HTTPException(status_code=404, detail=f"Workflow {workflow_id} not found")
    return wf


@router.post("", response_model=Workflow)
async def create_workflow(body: CreateWorkflowRequest, request):
    from models.schemas import WorkflowStep, Action, ActionType
    agent = get_workflow_agent(request)
    # Convert raw steps dicts to WorkflowStep objects
    steps = []
    for s in body.steps:
        if "action" in s:
            try:
                action = Action.model_validate(s["action"])
                steps.append(WorkflowStep(action=action, delay_ms=s.get("delay_ms", 500)))
            except Exception:
                pass
    wf = await agent.save_workflow_direct(
        name=body.name,
        description=body.description,
        steps=steps,
    )
    return wf


@router.delete("/{workflow_id}")
async def delete_workflow(workflow_id: str, request):
    agent = get_workflow_agent(request)
    await agent.delete_workflow(workflow_id)
    return {"status": "deleted", "id": workflow_id}


@router.post("/{workflow_id}/execute")
async def execute_workflow(workflow_id: str, body: ExecuteWorkflowRequest, request):
    agent = get_workflow_agent(request)
    bus = get_bus(request)

    wf = await agent.get_workflow_by_id(workflow_id)
    if not wf:
        raise HTTPException(status_code=404, detail=f"Workflow {workflow_id} not found")

    actions = await agent.replay(wf, parameters=body.parameters)
    # Push all actions to session queue
    for action in actions:
        await bus.push_action(body.session_id, action)

    # Increment use count
    await agent.increment_use_count(workflow_id)

    return {
        "status": "queued",
        "workflow_id": workflow_id,
        "session_id": body.session_id,
        "action_count": len(actions),
    }
