"""Tests for store-backed thread filesystem helpers."""

from __future__ import annotations

import pytest

from src.io.filesystem import filesystem_namespace
from src.io.thread_files import (
    normalize_file_path,
    read_text_for_user_thread,
    write_text_for_user_thread,
)
from src.memory.store import reset_store
from src.workflows.tools.hitl import is_approval, review_tool_call


def test_normalize_file_path():
    assert normalize_file_path("scratch/a.json") == "/scratch/a.json"
    assert normalize_file_path("/artifacts/x.yaml") == "/artifacts/x.yaml"
    with pytest.raises(ValueError, match="Parent path"):
        normalize_file_path("/scratch/../etc/passwd")
    with pytest.raises(ValueError, match="below"):
        normalize_file_path("/tmp/x")


def test_filesystem_namespace_from_runtime():
    class Ctx:
        user_id = "u1"

    class Exec:
        thread_id = "t1"

    class RT:
        context = Ctx()
        execution_info = Exec()

    assert filesystem_namespace(RT()) == (
        "users",
        "u1",
        "threads",
        "t1",
        "filesystem",
    )


def test_filesystem_namespace_from_configurable():
    assert filesystem_namespace(
        {"configurable": {"user_id": "u2", "thread_id": "t2"}}
    ) == ("users", "u2", "threads", "t2", "filesystem")


@pytest.mark.asyncio
async def test_write_and_read_user_thread_file():
    await reset_store()
    path = await write_text_for_user_thread(
        path="/scratch/discovery/pace-servers.json",
        content='{"ok": true}',
        user_id="user-a",
        thread_id="thread-a",
        content_type="application/json",
        metadata={"source": "api"},
    )
    assert path == "/scratch/discovery/pace-servers.json"
    text = await read_text_for_user_thread(
        path=path,
        user_id="user-a",
        thread_id="thread-a",
    )
    assert text == '{"ok": true}'


def test_review_tool_call_reask_then_reject():
    calls = {"n": 0}

    def fake_request(**_kwargs):
        calls["n"] += 1
        return "not-a-decision"

    decision = review_tool_call(
        action={"name": "call_authenticated_api", "args": {}},
        reason="Approve?",
        tool_name="call_authenticated_api",
        max_reasks=1,
        request_fn=fake_request,
    )
    assert calls["n"] == 2
    assert decision["type"] == "reject"


def test_is_approval():
    assert is_approval("yes")
    assert not is_approval("deny")
