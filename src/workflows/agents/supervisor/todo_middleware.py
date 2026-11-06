"""Supervisor todo list: one delegation record, with the design gate."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, Literal

from langchain.agents.middleware import TodoListMiddleware
from langchain.tools import ToolRuntime
from langchain_core.messages import ToolMessage
from langchain_core.tools import StructuredTool
from langgraph.types import Command
from pydantic import BaseModel, Field

_STATUSES = frozenset({"pending", "in_progress", "completed"})
_PHASE_NODES = {
    "discovery-agent": "discovery",
    "design-agent": "design",
}
_DESIGN_BLOCKED = "Design is blocked until discovery is completed."

SUPERVISOR_TODO_SYSTEM_PROMPT = """## `write_todos`

`write_todos` is the only task list. Call it once before any delegation and include:
- id `intake`, agent `supervisor`, status `pending`
- id `discovery`, agent `discovery-agent`, status `pending`
- id `design`, agent `design-agent`, status `pending`, depends_on [`discovery`]

Each item has `id`, `content`, `status`, `agent`, `parent_id`, and `depends_on`.
`status` is `pending`, `in_progress`, or `completed`.
The call replaces the whole list. Call it at most once per turn.
When you call `task` for `discovery-agent` or `design-agent`, the runtime sets that item's status. Design is refused until discovery is `completed`.
"""

SUPERVISOR_TODO_TOOL_DESCRIPTION = """Replace the supervisor delegation list.

Call once before delegating. Include intake, discovery, and design.
discovery uses agent discovery-agent. design uses agent design-agent and depends_on discovery.
status is pending, in_progress, or completed.
"""


class SupervisorTodo(BaseModel):
    """One row in the supervisor delegation list."""

    id: str
    content: str
    status: Literal["pending", "in_progress", "completed"] = "pending"
    agent: str = ""
    parent_id: str | None = None
    depends_on: list[str] = Field(default_factory=list)


class WriteSupervisorTodosInput(BaseModel):
    """Input schema for the supervisor `write_todos` tool."""

    todos: list[SupervisorTodo]


def _normalize(raw: Any) -> dict[str, Any]:
    data = raw.model_dump() if hasattr(raw, "model_dump") else dict(raw)
    node_id = str(data.get("id") or "").strip()
    if not node_id:
        raise ValueError("todo id is required")
    status = str(data.get("status") or "pending").strip()
    if status not in _STATUSES:
        raise ValueError(f"status must be one of: {', '.join(sorted(_STATUSES))}")
    content = str(data.get("content") or node_id).strip() or node_id
    parent = data.get("parent_id")
    return {
        "id": node_id,
        "content": content,
        "status": status,
        "agent": str(data.get("agent") or "").strip(),
        "parent_id": str(parent).strip() if parent else None,
        "depends_on": [str(item) for item in (data.get("depends_on") or [])],
    }


def _write_supervisor_todos(runtime: ToolRuntime, todos: list[SupervisorTodo]) -> Command:
    """Replace the supervisor delegation list."""
    normalized = [_normalize(item) for item in todos]
    return Command(
        update={
            "todos": normalized,
            "messages": [
                ToolMessage(
                    f"Updated todo list to {normalized}",
                    tool_call_id=runtime.tool_call_id,
                )
            ],
        }
    )


async def _awrite_supervisor_todos(
    runtime: ToolRuntime, todos: list[SupervisorTodo]
) -> Command:
    return _write_supervisor_todos(runtime, todos)


def _tool_name(request: Any) -> str:
    return str((getattr(request, "tool_call", None) or {}).get("name") or "")


def _subagent_type(request: Any) -> str:
    args = (getattr(request, "tool_call", None) or {}).get("args") or {}
    if not isinstance(args, dict):
        return ""
    return str(args.get("subagent_type") or "")


def _call_id(request: Any) -> str:
    return str((getattr(request, "tool_call", None) or {}).get("id") or "")


def _todos(request: Any) -> list[dict[str, Any]]:
    state = getattr(request, "state", None) or {}
    raw = state.get("todos") if isinstance(state, dict) else None
    return [dict(item) for item in (raw or [])]


def _find(todos: list[dict[str, Any]], node_id: str) -> int | None:
    for index, item in enumerate(todos):
        if item.get("id") == node_id:
            return index
    return None


def _is_completed(todos: list[dict[str, Any]], node_id: str) -> bool:
    index = _find(todos, node_id)
    if index is None:
        return False
    return todos[index].get("status") == "completed"


def _mark(
    todos: list[dict[str, Any]],
    node_id: str,
    status: str,
    agent: str,
) -> list[dict[str, Any]]:
    items = [dict(item) for item in todos]
    index = _find(items, node_id)
    if index is None:
        items.append(
            {
                "id": node_id,
                "content": node_id,
                "status": status,
                "agent": agent,
                "parent_id": None,
                "depends_on": ["discovery"] if node_id == "design" else [],
            }
        )
        return items
    items[index]["status"] = status
    if not items[index].get("agent"):
        items[index]["agent"] = agent
    return items


def _failed(result: Any, update: dict[str, Any] | None) -> bool:
    if isinstance(result, ToolMessage):
        return result.status == "error"
    messages = (update or {}).get("messages") or []
    return any(getattr(message, "status", None) == "error" for message in messages)


def _before(request: Any) -> tuple[str, Any]:
    if _tool_name(request) != "task":
        return ("pass", None)
    subagent = _subagent_type(request)
    node_id = _PHASE_NODES.get(subagent)
    if node_id is None:
        return ("pass", None)
    todos = _todos(request)
    if subagent == "design-agent" and not _is_completed(todos, "discovery"):
        return (
            "block",
            ToolMessage(
                content=_DESIGN_BLOCKED,
                tool_call_id=_call_id(request),
                name="task",
                status="error",
            ),
        )
    return ("track", (node_id, subagent, _mark(todos, node_id, "in_progress", subagent)))


def _after(node_id: str, agent: str, todos: list[dict[str, Any]], result: Any) -> Any:
    update = result.update if isinstance(result, Command) and isinstance(result.update, dict) else None
    if _failed(result, update):
        return result
    payload = dict(update or {})
    payload.pop("todos", None)
    payload["todos"] = _mark(todos, node_id, "completed", agent)
    if isinstance(result, ToolMessage):
        payload["messages"] = [result]
    return Command(update=payload)


class SupervisorTodoMiddleware(TodoListMiddleware):
    """`write_todos` for the supervisor, plus the discovery-before-design gate."""

    def __init__(self) -> None:
        super().__init__(
            system_prompt=SUPERVISOR_TODO_SYSTEM_PROMPT,
            tool_description=SUPERVISOR_TODO_TOOL_DESCRIPTION,
        )
        self.tools = [
            StructuredTool.from_function(
                name="write_todos",
                description=self.tool_description,
                func=_write_supervisor_todos,
                coroutine=_awrite_supervisor_todos,
                args_schema=WriteSupervisorTodosInput,
                infer_schema=False,
            )
        ]

    def wrap_tool_call(
        self,
        request: Any,
        handler: Callable[[Any], Any],
    ) -> Any:
        action, payload = _before(request)
        if action == "pass":
            return handler(request)
        if action == "block":
            return payload
        node_id, agent, todos = payload
        return _after(node_id, agent, todos, handler(request))

    async def awrap_tool_call(
        self,
        request: Any,
        handler: Callable[[Any], Awaitable[Any]],
    ) -> Any:
        action, payload = _before(request)
        if action == "pass":
            return await handler(request)
        if action == "block":
            return payload
        node_id, agent, todos = payload
        return _after(node_id, agent, todos, await handler(request))
