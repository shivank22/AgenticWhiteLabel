"""Run one workflow turn against the compiled orchestrator graph."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any

from langchain_core.messages import HumanMessage
from langgraph.types import Command

from src.api.errors import ChatError, public_error
from src.api.serialize import build_thread_view, message_text
from src.io.thread_files import list_files_for_user_thread, read_text_for_user_thread
from src.workflows.interrupts import extract_interrupt_payloads
from src.workflows.resume import resolve_resume_map

logger = logging.getLogger(__name__)

# LangGraph treats a resume dict as an interrupt-id map only when every key
# is a 32-character hex digest. Anything else is the resume value itself.
_INTERRUPT_KEY = re.compile(r"^[0-9a-f]{32}$")

try:
    from langgraph.errors import GraphInterrupt
except ImportError:  # pragma: no cover
    class GraphInterrupt(Exception):
        """Fallback if this LangGraph build does not export GraphInterrupt."""


@dataclass
class TurnOutcome:
    """Result of a finished turn, before display-only replies are spliced in."""

    view: dict[str, Any]
    reply: dict[str, Any] | None = None
    resumed: bool = False
    content: str | None = None


def thread_config(user_id: str, thread_id: str) -> dict[str, Any]:
    """Checkpoint config for one user thread.

    Deep-agent turns (supervisor plus subagents) exceed LangGraph's default of 25.
    """
    return {
        "configurable": {
            "thread_id": thread_id,
            "user_id": user_id,
        },
        "recursion_limit": 250,
    }


def _resume_value(resume_map: dict[str, Any]) -> Any:
    if len(resume_map) == 1 and not _INTERRUPT_KEY.fullmatch(next(iter(resume_map))):
        return next(iter(resume_map.values()))
    return resume_map


def _visible_text(content: str | None, answer: Any) -> str:
    if isinstance(content, str) and content.strip():
        return content.strip()
    if isinstance(answer, str):
        return answer.strip()
    if isinstance(answer, bool):
        return "approve" if answer else "reject"
    if isinstance(answer, dict):
        for key in ("response", "answer", "text", "value"):
            value = answer.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        decision = answer.get("type") or answer.get("decision")
        if isinstance(decision, str) and decision.strip():
            return decision.strip()
    if answer is None:
        return ""
    return str(answer).strip()


def _unpack_stream(item: Any) -> tuple[str, Any] | None:
    if not isinstance(item, tuple):
        return None
    if len(item) == 3 and isinstance(item[1], str):
        return item[1], item[2]
    if len(item) == 2 and isinstance(item[0], str):
        return item[0], item[1]
    return None


def token_from_stream(item: Any) -> str | None:
    """Return a model token from a graph stream item, if this item is one."""
    unpacked = _unpack_stream(item)
    if unpacked is None or unpacked[0] != "messages":
        return None
    data = unpacked[1]
    message = data[0] if isinstance(data, (tuple, list)) and data else data
    if "Chunk" not in type(message).__name__:
        return None
    kind = str(getattr(message, "type", "") or "").lower()
    if kind not in {"ai", "aimessagechunk"}:
        return None
    text = message_text(getattr(message, "content", ""))
    return text or None


def activity_from_stream(item: Any) -> str | None:
    """Return the latest node name from an updates stream item."""
    unpacked = _unpack_stream(item)
    if unpacked is None or unpacked[0] != "updates" or not isinstance(unpacked[1], dict):
        return None
    names = [
        key
        for key in unpacked[1]
        if isinstance(key, str) and key and not key.startswith("__")
    ]
    if not names:
        return None
    return names[-1]


class ChatService:
    """Invoke the orchestrator and read its checkpoint."""

    def __init__(
        self,
        *,
        graph_getter: Any = None,
        list_files: Any = None,
        read_text: Any = None,
    ) -> None:
        self._graph_getter = graph_getter
        self._owns_runtime = graph_getter is None
        self._list_files = list_files or list_files_for_user_thread
        self._read_text = read_text or read_text_for_user_thread
        self._locks: dict[str, Any] = {}
        self._locks_guard: Any = None

    def _guard(self) -> Any:
        import asyncio

        if self._locks_guard is None:
            self._locks_guard = asyncio.Lock()
        return self._locks_guard

    async def _lock_for(self, thread_id: str) -> Any:
        import asyncio

        async with self._guard():
            lock = self._locks.get(thread_id)
            if lock is None:
                lock = asyncio.Lock()
                self._locks[thread_id] = lock
            return lock

    async def _graph(self) -> Any:
        try:
            if self._graph_getter is not None:
                return await self._graph_getter()
            from src.workflows.runtime import get_compiled_graph

            return await get_compiled_graph()
        except ChatError:
            raise
        except Exception as exc:
            logger.exception("workflow graph failed to start")
            raise ChatError(
                f"Could not start the workflow. {public_error(exc)}",
                502,
            ) from exc

    async def snapshot(self, *, user_id: str, thread_id: str) -> dict[str, Any]:
        graph = await self._graph()
        try:
            state = await graph.aget_state(thread_config(user_id, thread_id))
        except Exception as exc:
            logger.exception("workflow state read failed")
            raise ChatError(public_error(exc), 502) from exc
        return build_thread_view(thread_id=thread_id, user_id=user_id, snapshot=state)

    async def _prepare(
        self,
        graph: Any,
        config: dict[str, Any],
        *,
        user_id: str,
        thread_id: str,
        content: str | None,
        answer: Any,
    ) -> tuple[Any, dict[str, Any] | None, bool, str | None]:
        snapshot = await graph.aget_state(config)
        interrupts = extract_interrupt_payloads(snapshot)
        values = dict(getattr(snapshot, "values", None) or {})
        if interrupts:
            payload = answer if answer is not None else content
            if payload is None or (isinstance(payload, str) and not str(payload).strip()):
                raise ChatError("Reply to the open question before continuing.", 400)
            resume_map = resolve_resume_map(snapshot=snapshot, answer=payload)
            if not resume_map:
                raise ChatError("No open question matched that reply.", 409)
            visible = _visible_text(content if isinstance(content, str) else None, payload)
            if len(resume_map) == 1:
                resolved = next(iter(resume_map.values()))
                if isinstance(resolved, str) and resolved.strip():
                    visible = resolved.strip()
            update: dict[str, Any] = {"user_id": user_id, "thread_id": thread_id}
            if visible:
                update["user_input"] = visible
                update["resume_message"] = visible
            prior = len(
                build_thread_view(
                    thread_id=thread_id,
                    user_id=user_id,
                    snapshot=snapshot,
                )["messages"]
            )
            reply = {"index": prior, "content": visible} if visible else None
            # The answer stays out of graph messages. Inserting a human message
            # while a tool call is open splits the tool-call sequence.
            return (
                Command(resume=_resume_value(resume_map), update=update),
                reply,
                True,
                visible or None,
            )

        text = content.strip() if isinstance(content, str) else ""
        if not text:
            raise ChatError("A message is required.", 400)
        phase = str(values.get("phase") or "").strip().lower()
        if phase == "completed":
            phase = "complete"
        if phase == "complete":
            raise ChatError(
                "This workflow is complete. Start a new migration to continue.",
                409,
            )
        graph_input = {
            "messages": [HumanMessage(content=text)],
            "user_input": text,
            "resume_message": text,
            "user_id": user_id,
            "thread_id": thread_id,
        }
        return graph_input, None, False, text

    async def _finish(
        self,
        graph: Any,
        config: dict[str, Any],
        *,
        user_id: str,
        thread_id: str,
        reply: dict[str, Any] | None,
        resumed: bool,
        content: str | None,
    ) -> TurnOutcome:
        state = await graph.aget_state(config)
        view = build_thread_view(thread_id=thread_id, user_id=user_id, snapshot=state)
        return TurnOutcome(view=view, reply=reply, resumed=resumed, content=content)

    async def _invoke(self, graph: Any, graph_input: Any, config: dict[str, Any]) -> Any:
        try:
            await graph.ainvoke(graph_input, config)
            return graph
        except GraphInterrupt:
            return graph
        except Exception as exc:
            if self._owns_runtime:
                from src.workflows.runtime import (
                    is_closed_connection_error,
                    rebuild_compiled_graph,
                )

                if is_closed_connection_error(exc):
                    logger.warning("workflow database connection closed; retrying once")
                    graph = await rebuild_compiled_graph()
                    await graph.ainvoke(graph_input, config)
                    return graph
            raise

    async def run_turn(
        self,
        *,
        user_id: str,
        thread_id: str,
        content: str | None = None,
        answer: Any = None,
    ) -> TurnOutcome:
        lock = await self._lock_for(thread_id)
        async with lock:
            graph = await self._graph()
            config = thread_config(user_id, thread_id)
            graph_input, reply, resumed, visible = await self._prepare(
                graph,
                config,
                user_id=user_id,
                thread_id=thread_id,
                content=content,
                answer=answer,
            )
            logger.info("workflow turn thread=%s resumed=%s", thread_id, resumed)
            try:
                graph = await self._invoke(graph, graph_input, config)
            except ChatError:
                raise
            except Exception as exc:
                logger.exception("workflow turn failed")
                raise ChatError(public_error(exc), 502) from exc
            return await self._finish(
                graph,
                config,
                user_id=user_id,
                thread_id=thread_id,
                reply=reply,
                resumed=resumed,
                content=visible,
            )

    async def iter_turn_events(
        self,
        *,
        user_id: str,
        thread_id: str,
        content: str | None = None,
        answer: Any = None,
    ) -> Any:
        """Yield status, token, activity, and a final snapshot event."""
        lock = await self._lock_for(thread_id)
        async with lock:
            yield {"event": "status", "data": {"status": "running"}}
            graph = await self._graph()
            config = thread_config(user_id, thread_id)
            graph_input, reply, resumed, visible = await self._prepare(
                graph,
                config,
                user_id=user_id,
                thread_id=thread_id,
                content=content,
                answer=answer,
            )
            logger.info("workflow stream thread=%s resumed=%s", thread_id, resumed)
            try:
                async for item in graph.astream(
                    graph_input,
                    config,
                    stream_mode=["messages", "updates"],
                    subgraphs=True,
                ):
                    token = token_from_stream(item)
                    if token:
                        yield {"event": "token", "data": {"text": token}}
                    activity = activity_from_stream(item)
                    if activity:
                        yield {"event": "activity", "data": {"node": activity}}
            except GraphInterrupt:
                pass
            except ChatError:
                raise
            except Exception as exc:
                logger.exception("workflow stream failed")
                raise ChatError(public_error(exc), 502) from exc
            outcome = await self._finish(
                graph,
                config,
                user_id=user_id,
                thread_id=thread_id,
                reply=reply,
                resumed=resumed,
                content=visible,
            )
            yield {
                "event": "snapshot",
                "data": {
                    "view": outcome.view,
                    "reply": outcome.reply,
                    "resumed": outcome.resumed,
                    "content": outcome.content,
                },
            }

    async def list_workspace(
        self,
        *,
        user_id: str,
        thread_id: str,
        prefix: str = "/",
    ) -> list[str]:
        try:
            files = await self._list_files(
                user_id=user_id,
                thread_id=thread_id,
                prefix=prefix,
            )
        except Exception as exc:
            raise ChatError(public_error(exc), 502) from exc
        return [str(path) for path in files]

    async def read_workspace(self, *, user_id: str, thread_id: str, path: str) -> str:
        try:
            content = await self._read_text(
                path=path,
                user_id=user_id,
                thread_id=thread_id,
            )
        except ValueError as exc:
            raise ChatError(str(exc), 400) from exc
        except Exception as exc:
            raise ChatError(public_error(exc), 502) from exc
        if content is None:
            raise ChatError("File not found.", 404)
        return content
