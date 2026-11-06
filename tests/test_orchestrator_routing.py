"""Routing and hierarchical subagent tests for the orchestrator."""

import pytest
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END
from langgraph.store.memory import InMemoryStore

from langchain.agents.middleware import TodoListMiddleware
from langchain_quickjs import CodeInterpreterMiddleware

from src.validators import has_validator, validate_artifact
from src.workflows.agents.design.subagents import build_design_subagents
from src.workflows.agents.design.agent import build_design_agent
from src.workflows.agents.discovery.agent import (
    build_discovery_agent,
    build_discovery_subagents,
)
from src.workflows.agents.prompt_blocks import (
    build_default_middleware,
    compose_system_prompt,
)
from src.workflows.agents.supervisor.agent import (
    build_supervisor_agent,
    build_supervisor_rework_subagent,
)
from src.workflows.graphs.orchestrator_graph import (
    _route_after_supervisor,
    _route_from_start,
    build_orchestrator_graph,
)


def _fake_llm() -> GenericFakeChatModel:
    return GenericFakeChatModel(messages=iter([AIMessage(content="ok")]))


def test_route_from_start():
    assert _route_from_start({"phase": ""}) == "supervisor"
    assert _route_from_start({"phase": "collection"}) == "supervisor"
    assert _route_from_start({"phase": "discovery"}) == "supervisor"
    assert _route_from_start({"phase": "review"}) == "supervisor"
    assert _route_from_start({"phase": "design"}) == "supervisor"
    assert _route_from_start({"phase": "completed"}) == END
    assert _route_from_start({"phase": "complete"}) == END


def test_route_after_supervisor():
    assert _route_after_supervisor({"phase": "review"}) == END
    assert _route_after_supervisor({"phase": "complete"}) == END


@pytest.mark.asyncio
async def test_agents_compile_with_todo_middleware_and_subagents(monkeypatch):
    llm = _fake_llm()
    store = InMemoryStore()

    discovery = await build_discovery_agent(llm=llm, store=store)
    design = await build_design_agent(llm=llm, store=store)
    supervisor = await build_supervisor_agent(
        llm=llm,
        store=store,
        discovery_agent=discovery,
        design_agent=design,
    )

    assert discovery is not None
    assert design is not None
    assert supervisor is not None

    monkeypatch.setattr("src.llm.factory.get_llm", lambda: llm)
    graph = await build_orchestrator_graph(checkpointer=MemorySaver(), store=store)
    assert "supervisor" in graph.nodes


def test_default_middleware_and_workspace_prompt():
    middleware = build_default_middleware()
    assert isinstance(middleware[0], TodoListMiddleware)
    assert isinstance(middleware[1], CodeInterpreterMiddleware)

    prompt = compose_system_prompt(role="Design", responsibilities="Follow the skill.")
    assert "/artifacts/artifact.yaml" in prompt
    assert "notes.md" not in prompt
    assert "/scratch/design/canvas.md" in prompt
    assert "/scratch/supervisor/canvas.md" in prompt
    assert "/scratch/discovery/canvas.md" in prompt
    assert "/skills/" in prompt
    assert "/templates/" in prompt
    assert "read_file" in prompt
    assert "SKILL.md" in prompt
    assert "limit=1000" in prompt
    assert "skill-router phases" in prompt
    assert "fresh message list" in prompt
    assert "every module" not in prompt
    assert "UK8S" not in prompt

    supervisor_prompt = compose_system_prompt(
        role="Supervisor",
        responsibilities="Coordinate.",
    )
    assert "skill-router phases" not in supervisor_prompt
    assert "limit=1000" in supervisor_prompt

    rework = build_supervisor_rework_subagent()
    assert rework["name"] == "general-purpose"
    assert rework["description"] == (
        "Changes the artifact the user named. "
        "The task states the artifact path and the change."
    )
    assert "`ls`" in rework["system_prompt"]
    assert "`read_file`" in rework["system_prompt"]
    assert "`write_file`" in rework["system_prompt"]
    assert "edit_file" in rework["system_prompt"]
    assert rework["tools"] == []

    subagents = build_design_subagents()
    assert [spec["name"] for spec in subagents] == ["general-purpose"]
    assert [spec["name"] for spec in build_discovery_subagents()] == ["general-purpose"]
    worker_prompt = subagents[0]["system_prompt"]
    assert "Follow those instructions exactly" in worker_prompt
    assert "/scratch/canvas.md" not in worker_prompt
    assert "output path" in worker_prompt
    assert "status" in worker_prompt
    assert "paths written" in worker_prompt
    assert "gaps" in worker_prompt
    assert "ask_user" in worker_prompt
    assert "ask_user_interrupt" in worker_prompt
    assert "UK8S" not in worker_prompt
    assert {tool.name for tool in subagents[0]["tools"]} == {
        "ask_user",
        "ask_user_interrupt",
    }
    assert "ask_user_interrupt" in prompt


def test_artifact_write_replaces_existing_file():
    from deepagents.backends import StoreBackend

    from src.workflows.backends.validating_backend import build_validating_store_backend

    backend = build_validating_store_backend(StoreBackend)(
        store=InMemoryStore(),
        namespace=lambda _runtime: ("test", "filesystem"),
    )
    path = "/artifacts/design/future-platform.md"
    assert backend.write(path, "first").error is None
    assert backend.write(path, "second").error is None
    assert "second" in backend.read(path).file_data["content"]
    assert backend.write(path, "  ").error is not None
    assert "second" in backend.read(path).file_data["content"]


def test_supervisor_todo_middleware_is_the_only_write_todos():
    from langchain.agents.middleware import TodoListMiddleware

    from src.workflows.agents.supervisor.todo_middleware import SupervisorTodoMiddleware

    middleware = SupervisorTodoMiddleware()
    assert isinstance(middleware, TodoListMiddleware)
    assert [tool.name for tool in middleware.tools] == ["write_todos"]


def _task_request(subagent_type: str, todos: list[dict]):
    from types import SimpleNamespace

    return SimpleNamespace(
        tool_call={
            "name": "task",
            "id": "call-1",
            "args": {"subagent_type": subagent_type, "description": "do the phase"},
        },
        state={"todos": todos},
    )


def _phase_todos() -> list[dict]:
    return [
        {
            "id": "intake",
            "content": "Intake",
            "status": "pending",
            "agent": "supervisor",
            "parent_id": None,
            "depends_on": [],
        },
        {
            "id": "discovery",
            "content": "Discovery",
            "status": "pending",
            "agent": "discovery-agent",
            "parent_id": None,
            "depends_on": [],
        },
        {
            "id": "design",
            "content": "Design",
            "status": "pending",
            "agent": "design-agent",
            "parent_id": None,
            "depends_on": ["discovery"],
        },
    ]


def test_supervisor_todos_block_design_until_discovery_completes():
    from langchain_core.messages import ToolMessage

    from src.workflows.agents.supervisor.todo_middleware import SupervisorTodoMiddleware

    called = False

    def handler(_request):
        nonlocal called
        called = True
        return ToolMessage(content="ran", tool_call_id="call-1", name="task")

    result = SupervisorTodoMiddleware().wrap_tool_call(
        _task_request("design-agent", _phase_todos()),
        handler,
    )
    assert called is False
    assert isinstance(result, ToolMessage)
    assert result.status == "error"
    assert "discovery" in result.content


def test_supervisor_todos_mark_discovery_completed():
    from langchain_core.messages import ToolMessage
    from langgraph.types import Command

    from src.workflows.agents.supervisor.todo_middleware import SupervisorTodoMiddleware

    def handler(_request):
        return Command(
            update={
                "todos": [{"id": "from-child", "content": "ignore", "status": "completed"}],
                "messages": [
                    ToolMessage(content="done", tool_call_id="call-1", name="task")
                ],
            }
        )

    result = SupervisorTodoMiddleware().wrap_tool_call(
        _task_request("discovery-agent", _phase_todos()),
        handler,
    )
    assert isinstance(result, Command)
    todos = {item["id"]: item for item in result.update["todos"]}
    assert "from-child" not in todos
    assert todos["discovery"]["status"] == "completed"
    assert todos["design"]["status"] == "pending"
    assert todos["design"]["content"] == "Design"
    assert result.update["messages"][0].content == "done"


def test_supervisor_todos_propagate_interrupt():
    from langgraph.errors import GraphBubbleUp

    from src.workflows.agents.supervisor.todo_middleware import SupervisorTodoMiddleware

    def handler(_request):
        raise GraphBubbleUp()

    with pytest.raises(GraphBubbleUp):
        SupervisorTodoMiddleware().wrap_tool_call(
            _task_request("discovery-agent", _phase_todos()),
            handler,
        )


def test_supervisor_prompt_names_write_todos_and_canvas():
    from src.workflows.agents.supervisor.agent import _SUPERVISOR_SYSTEM_PROMPT

    assert "write_todos" in _SUPERVISOR_SYSTEM_PROMPT
    assert "write_task_tree" not in _SUPERVISOR_SYSTEM_PROMPT
    assert "/scratch/supervisor/canvas.md" in _SUPERVISOR_SYSTEM_PROMPT


def test_any_artifact_path_is_non_empty_validated():
    assert has_validator("artifacts/design/future-platform.md")
    assert validate_artifact("artifacts/design/future-platform.md", "ok").ok
    assert not validate_artifact("artifacts/design/future-platform.md", "  ").ok
    assert not has_validator("scratch/design/canvas.md")
    assert not has_validator("scratch/discovery/canvas.md")
