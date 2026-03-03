"""
OrchestratorAgent: Master coordinator that decomposes complex tasks into sub-tasks
and assigns them to specialist agents.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from dataclasses import dataclass, field
from typing import Any, Optional

from google import genai
from google.genai import types

from agents.memory import MemoryAgent
from agents.research import ResearchAgent
from agents.workflow import WorkflowAgent
from services.redis_bus import RedisBus

logger = logging.getLogger(__name__)


@dataclass
class TaskNode:
    id: str
    description: str
    agent: str  # which agent handles this
    status: str = "pending"  # pending, running, completed, failed
    result: Any = None
    depends_on: list[str] = field(default_factory=list)


@dataclass
class TaskDAG:
    session_id: str
    goal: str
    nodes: list[TaskNode] = field(default_factory=list)
    completed: list[str] = field(default_factory=list)

    def get_ready_nodes(self) -> list[TaskNode]:
        """Return nodes whose dependencies are all completed."""
        return [
            n for n in self.nodes
            if n.status == "pending"
            and all(dep in self.completed for dep in n.depends_on)
        ]


class OrchestratorAgent:
    def __init__(
        self,
        bus: RedisBus,
        memory_agent: MemoryAgent,
        research_agent: ResearchAgent,
        workflow_agent: WorkflowAgent,
    ):
        self._bus = bus
        self._memory = memory_agent
        self._research = research_agent
        self._workflow = workflow_agent

        api_key = os.getenv("GEMINI_API_KEY", "")
        self._client = genai.Client(api_key=api_key) if api_key else None

    async def process(self, task: str, context: dict = {}) -> dict[str, Any]:
        """
        Main entry point: decompose task, execute via agents, return enriched context.
        """
        if not self._client:
            return {"error": "Gemini client not available", "task": task}

        # Get user context from memory
        user_ctx = await self._memory.get_user_context(context.get("session_id", ""))

        # Check if this matches a known workflow
        wf = await self._workflow.get_workflow(task)
        if wf:
            logger.info(f"Found matching workflow: {wf.name}")
            actions = await self._workflow.replay(wf, parameters=context)
            return {
                "type": "workflow_replay",
                "workflow": wf.name,
                "actions": [a.model_dump(mode="json") for a in actions],
                "user_context": user_ctx,
            }

        # Decompose complex task
        dag = await self._decompose_task(task, user_ctx)
        result = await self._execute_dag(dag)

        return {
            "type": "orchestrated",
            "task": task,
            "subtask_results": result,
            "user_context": user_ctx,
        }

    async def _decompose_task(self, task: str, user_context: dict) -> TaskDAG:
        """Ask Gemini to break down the task into sub-tasks."""
        try:
            prompt = f"""
You are an AI task decomposer for a computer automation agent.
Break down this task into concrete sub-tasks that specialist agents can handle.

Task: {task}
User preferences: {json.dumps(user_context.get('user_preferences', [])[:3])}

Available agents:
- research: web search and information gathering
- memory: recall user preferences and past context
- workflow: check saved workflows

Output a JSON array of sub-tasks:
[
  {{"id": "1", "description": "...", "agent": "research", "depends_on": []}},
  {{"id": "2", "description": "...", "agent": "memory", "depends_on": []}}
]

Only include sub-tasks for research, memory, workflow agents.
Keep it simple (2-4 sub-tasks max). Output ONLY the JSON array.
"""
            response = await self._client.aio.models.generate_content(
                model="gemini-2.0-flash", contents=prompt
            )
            text = response.text or ""
            json_match = re.search(r"\[.*\]", text, re.DOTALL)
            if json_match:
                raw_nodes = json.loads(json_match.group(0))
                nodes = [
                    TaskNode(
                        id=n["id"],
                        description=n["description"],
                        agent=n.get("agent", "research"),
                        depends_on=n.get("depends_on", []),
                    )
                    for n in raw_nodes
                ]
                return TaskDAG(session_id="", goal=task, nodes=nodes)
        except Exception as e:
            logger.warning(f"Task decomposition failed: {e}")

        # Fallback: single research task
        return TaskDAG(
            session_id="",
            goal=task,
            nodes=[TaskNode(id="1", description=task, agent="research")],
        )

    async def _execute_dag(self, dag: TaskDAG) -> list[dict]:
        """Execute task DAG, parallelizing independent nodes."""
        results = []
        max_iterations = 20

        for _ in range(max_iterations):
            ready = dag.get_ready_nodes()
            if not ready:
                break

            # Execute ready nodes in parallel
            tasks = [self._execute_node(node, dag) for node in ready]
            node_results = await asyncio.gather(*tasks, return_exceptions=True)

            for node, result in zip(ready, node_results):
                if isinstance(result, Exception):
                    node.status = "failed"
                    node.result = {"error": str(result)}
                    logger.error(f"Node {node.id} failed: {result}")
                else:
                    node.status = "completed"
                    node.result = result
                    dag.completed.append(node.id)
                results.append({"node_id": node.id, "agent": node.agent, "result": node.result})

        return results

    async def _execute_node(self, node: TaskNode, dag: TaskDAG) -> Any:
        """Execute a single task node using the appropriate agent."""
        node.status = "running"
        logger.info(f"Executing node {node.id} [{node.agent}]: {node.description[:60]}")

        if node.agent == "research":
            return await self._research.search(node.description)

        elif node.agent == "memory":
            entries = await self._memory.recall(node.description, limit=5)
            return {"memories": [e.content for e in entries]}

        elif node.agent == "workflow":
            wf = await self._workflow.get_workflow(node.description)
            if wf:
                return {"workflow_found": wf.name, "steps": len(wf.steps)}
            return {"workflow_found": None}

        else:
            return {"status": "no_agent", "description": node.description}
