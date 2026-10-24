"""Chat API tests. The orchestrator is replaced with a graph that interrupts."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient
from langchain_core.messages import AIMessage

from src.api.app import create_app
from src.api.chat import ChatService, thread_config
from src.api.errors import public_error
from src.api.serialize import serialize_message, splice_replies
from src.api.sessions import ThreadRegistry


async def _list_files(*, user_id: str, thread_id: str, prefix: str = "/") -> list[str]:
    del user_id, thread_id, prefix
    return ["/artifacts/artifact.yaml", "/scratch/canvas.md"]


async def _read_text(*, path: str, user_id: str, thread_id: str) -> str | None:
    del user_id, thread_id
    if path == "/artifacts/artifact.yaml":
        return "name: payments-api\n"
    if path.startswith("/artifacts/") or path.startswith("/scratch/"):
        return None
    raise ValueError("Path must be below /scratch/ or /artifacts/")


def build_question_graph():
    from langgraph.checkpoint.memory import MemorySaver
    from langgraph.graph import END, START, StateGraph
    from langgraph.types import interrupt

    from src.workflows.state import DICEState

    async def supervisor(_state):
        answer = interrupt(
            {
                "type": "question",
                "input_type": "choice",
                "question": "Continue to discovery?",
                "options": ["yes", "no"],
                "phase": "collection",
            }
        )
        approved = str(answer).strip().lower().startswith("y")
        text = f"You said {answer}"
        return {
            "phase": "discovery" if approved else "complete",
            "ai_response": text,
            "messages": [AIMessage(content=text)],
        }

    graph = StateGraph(DICEState)
    graph.add_node("supervisor", supervisor)
    graph.add_edge(START, "supervisor")
    graph.add_edge("supervisor", END)
    return graph.compile(checkpointer=MemorySaver())


def build_review_graph(sink: dict):
    from langgraph.checkpoint.memory import MemorySaver
    from langgraph.graph import END, START, StateGraph
    from langgraph.types import interrupt

    from src.workflows.state import DICEState

    async def supervisor(_state):
        answer = interrupt(
            {
                "type": "tool_review",
                "input_type": "tool_review",
                "question": "Review this tool call before execution.",
                "tool_name": "call_authenticated_api",
                "allowed_decisions": ["approve", "edit", "reject"],
                "options": ["approve", "edit", "reject"],
                "phase": "discovery",
                "action_request": {
                    "name": "call_authenticated_api",
                    "args": {"url": "https://example.test"},
                },
            }
        )
        sink["answer"] = answer
        return {"phase": "discovery", "messages": [AIMessage(content="reviewed")]}

    graph = StateGraph(DICEState)
    graph.add_node("supervisor", supervisor)
    graph.add_edge(START, "supervisor")
    graph.add_edge("supervisor", END)
    return graph.compile(checkpointer=MemorySaver())


@pytest.fixture
async def api(tmp_path):
    graph = build_question_graph()

    async def getter():
        return graph

    registry = ThreadRegistry(tmp_path / "threads.json")
    chat = ChatService(graph_getter=getter, list_files=_list_files, read_text=_read_text)
    app = create_app(chat=chat, registry=registry)
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"X-Dice-User": "local"},
    ) as client:
        yield client, graph


def test_public_error_redacts_keys():
    text = public_error(RuntimeError("bad sk-abcdefghijklmnopqrstuvwxyz"))
    assert "sk-abcdefghijklmnopqrstuvwxyz" not in text
    assert "sk-…" in text


def test_serialize_tool_call_and_splice():
    message = AIMessage(
        content=[{"type": "text", "text": "Looking"}],
        tool_calls=[{"id": "1", "name": "ask_user", "args": {"question": "AA?"}}],
    )
    payload = serialize_message(message)
    assert payload["content"] == "Looking"
    assert payload["tool_calls"][0]["name"] == "ask_user"
    assert payload["tool_calls"][0]["args"]["question"] == "AA?"

    spliced = splice_replies(
        [
            {"id": "1", "role": "human", "content": "hello"},
            {"id": "2", "role": "ai", "content": "You said yes"},
        ],
        [{"id": "r1", "index": 1, "content": "yes"}],
    )
    assert [item["content"] for item in spliced] == ["hello", "yes", "You said yes"]
    assert spliced[1]["display_only"] is True


@pytest.mark.asyncio
async def test_registry_round_trip(tmp_path):
    path = tmp_path / "threads.json"
    created = await ThreadRegistry(path).create("local")
    again = ThreadRegistry(path)
    listed = await again.list_threads("local")
    assert listed[0]["thread_id"] == created["thread_id"]
    assert await again.list_threads("other") == []


@pytest.mark.asyncio
async def test_tool_review_resume_passes_decision():
    sink: dict = {}
    graph = build_review_graph(sink)

    async def getter():
        return graph

    chat = ChatService(graph_getter=getter)
    thread_id = "a" * 32
    first = await chat.run_turn(user_id="local", thread_id=thread_id, content="check the api")
    assert first.view["status"] == "awaiting_input"
    assert first.resumed is False

    second = await chat.run_turn(
        user_id="local",
        thread_id=thread_id,
        content="approve",
        answer={"type": "approve"},
    )
    assert sink["answer"]["type"] == "approve"
    assert second.view["phase"] == "discovery"
    assert second.resumed is True
    assert [message["role"] for message in second.view["messages"]].count("human") == 1


@pytest.mark.asyncio
async def test_chat_round_trip(api):
    client, graph = api

    health = (await client.get("/api/health")).json()
    assert health["ok"] is True
    page = await client.get("/")
    assert page.status_code == 200
    assert 'id="draft"' in page.text

    created = (await client.post("/api/threads", json={})).json()
    thread_id = created["thread_id"]
    assert created["title"] == "New migration"

    files = (await client.get(f"/api/threads/{thread_id}/files")).json()
    assert files["files"] == ["/artifacts/artifact.yaml", "/scratch/canvas.md"]
    artifact = (
        await client.get(
            f"/api/threads/{thread_id}/files/content",
            params={"path": "/artifacts/artifact.yaml"},
        )
    ).json()
    assert "payments-api" in artifact["content"]
    denied = await client.get(
        f"/api/threads/{thread_id}/files/content",
        params={"path": "/etc/passwd"},
    )
    assert denied.status_code == 400
    missing = await client.get(
        f"/api/threads/{thread_id}/files/content",
        params={"path": "/scratch/missing.md"},
    )
    assert missing.status_code == 404

    async with client.stream(
        "POST",
        f"/api/threads/{thread_id}/turns/stream",
        json={"content": "Migrate payments-api"},
    ) as response:
        assert response.status_code == 200
        body = (await response.aread()).decode()
    assert "event: status" in body
    assert "event: snapshot" in body
    assert "Continue to discovery?" in body
    assert "awaiting_input" in body

    listed = (await client.get("/api/threads")).json()["threads"]
    assert listed[0]["title"] == "Migrate payments-api"
    hidden = await client.get(f"/api/threads/{thread_id}", headers={"X-Dice-User": "other"})
    assert hidden.status_code == 404

    resumed = await client.post(
        f"/api/threads/{thread_id}/turns",
        json={"content": "yes"},
    )
    assert resumed.status_code == 200
    view = resumed.json()
    assert view["phase"] == "discovery"
    assert view["status"] == "idle"
    assert [item["content"] for item in view["messages"]] == [
        "Migrate payments-api",
        "yes",
        "You said yes",
    ]
    assert view["messages"][1]["display_only"] is True

    snapshot = await graph.aget_state(thread_config("local", thread_id))
    humans = [message for message in snapshot.values["messages"] if message.type == "human"]
    assert len(humans) == 1
    assert humans[0].content == "Migrate payments-api"

    again = await client.post(
        f"/api/threads/{thread_id}/turns",
        json={"content": "Check the design notes"},
    )
    assert again.status_code == 200
    assert again.json()["status"] == "awaiting_input"

    finished = await client.post(
        f"/api/threads/{thread_id}/turns",
        json={"content": "no"},
    )
    assert finished.status_code == 200
    assert finished.json()["status"] == "complete"
    assert [item["content"] for item in finished.json()["messages"]] == [
        "Migrate payments-api",
        "yes",
        "You said yes",
        "Check the design notes",
        "no",
        "You said no",
    ]

    rejected = await client.post(
        f"/api/threads/{thread_id}/turns",
        json={"content": "one more thing"},
    )
    assert rejected.status_code == 409

    deleted = await client.delete(f"/api/threads/{thread_id}")
    assert deleted.status_code == 204
    assert (await client.get(f"/api/threads/{thread_id}")).status_code == 404
