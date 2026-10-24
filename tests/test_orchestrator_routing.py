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
from src.workflows.agents.discovery.agent import build_discovery_agent
from src.workflows.agents.prompt_blocks import (
    build_default_middleware,
    compose_system_prompt,
)
from src.workflows.agents.supervisor.agent import build_supervisor_agent
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
    assert "/scratch/canvas.md" in prompt
    assert "/skills/" in prompt
    assert "/templates/" in prompt
    assert "UK8S-Discovery-Baseline.md" not in prompt

    subagents = build_design_subagents()
    assert [spec["name"] for spec in subagents] == ["general-purpose"]
    assert "Follow those instructions exactly" in subagents[0]["system_prompt"]
    assert "ask_user" in subagents[0]["system_prompt"]
    assert "ask_user_interrupt" in subagents[0]["system_prompt"]
    assert "UK8S" not in subagents[0]["system_prompt"]
    assert {tool.name for tool in subagents[0]["tools"]} == {
        "ask_user",
        "ask_user_interrupt",
    }
    assert "ask_user_interrupt" in prompt


def test_any_artifact_path_is_non_empty_validated():
    assert has_validator("artifacts/design/future-platform.md")
    assert validate_artifact("artifacts/design/future-platform.md", "ok").ok
    assert not validate_artifact("artifacts/design/future-platform.md", "  ").ok
    assert not has_validator("scratch/canvas.md")
