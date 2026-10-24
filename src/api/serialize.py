"""Turn LangGraph snapshots into JSON the chat UI can render."""

from __future__ import annotations

from typing import Any

from src.workflows.interrupts import extract_interrupt_payloads

_TOOL_LIMIT = 8_000
_TEXT_LIMIT = 20_000


def json_safe(value: Any) -> Any:
    """Recursively convert a value into JSON-compatible data."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    return str(value)


def message_text(content: Any) -> str:
    """Flatten a LangChain message content value to plain text."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
                continue
            text = block.get("text") if isinstance(block, dict) else getattr(block, "text", None)
            if text:
                parts.append(str(text))
        return "\n".join(part for part in parts if part)
    return str(content)


def _clip(text: str, limit: int) -> tuple[str, bool]:
    if len(text) <= limit:
        return text, False
    return text[:limit], True


def _tool_call(call: Any) -> dict[str, Any]:
    if isinstance(call, dict):
        name = call.get("name")
        args = call.get("args")
        call_id = call.get("id")
    else:
        name = getattr(call, "name", "")
        args = getattr(call, "args", {})
        call_id = getattr(call, "id", None)
    return {
        "id": None if call_id is None else str(call_id),
        "name": str(name or ""),
        "args": json_safe(args or {}),
    }


def serialize_message(message: Any) -> dict[str, Any]:
    """Serialize one chat message for the browser."""
    role = str(getattr(message, "type", "") or "unknown")
    text = message_text(getattr(message, "content", ""))
    limit = _TOOL_LIMIT if role == "tool" else _TEXT_LIMIT
    clipped, truncated = _clip(text, limit)
    tool_calls = [_tool_call(call) for call in (getattr(message, "tool_calls", None) or [])]
    message_id = getattr(message, "id", None)
    tool_call_id = getattr(message, "tool_call_id", None)
    name = getattr(message, "name", None)
    return {
        "id": None if message_id is None else str(message_id),
        "role": role,
        "content": clipped,
        "name": str(name) if name else None,
        "tool_calls": tool_calls,
        "tool_call_id": None if tool_call_id is None else str(tool_call_id),
        "truncated": truncated,
        "display_only": False,
    }


def splice_replies(messages: list[dict[str, Any]], replies: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Insert display-only user replies into a checkpoint transcript.

    Reply indexes refer to the checkpoint message list, not the spliced view.
    A reply stored at index N is shown just before the checkpoint message that
    was appended by that resume.
    """
    grouped: dict[int, list[dict[str, Any]]] = {}
    for reply in replies:
        try:
            index = int(reply.get("index", len(messages)))
        except (TypeError, ValueError):
            index = len(messages)
        grouped.setdefault(index, []).append(reply)

    output: list[dict[str, Any]] = []
    for index, message in enumerate(messages):
        output.extend(_reply_row(item) for item in grouped.pop(index, []))
        output.append(message)
    for index in sorted(grouped):
        output.extend(_reply_row(item) for item in grouped[index])
    return output


def _reply_row(reply: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(reply.get("id") or ""),
        "role": "human",
        "content": str(reply.get("content") or ""),
        "name": None,
        "tool_calls": [],
        "tool_call_id": None,
        "truncated": False,
        "display_only": True,
    }


def present_thread(view: dict[str, Any], record: dict[str, Any] | None) -> dict[str, Any]:
    """Add the registry title and display-only replies to a graph view."""
    presented = dict(view)
    replies = list((record or {}).get("replies") or [])
    presented["messages"] = splice_replies(list(view.get("messages") or []), replies)
    if record is not None:
        presented["title"] = record.get("title") or view.get("title") or "New migration"
    return presented


def build_thread_view(
    *,
    thread_id: str,
    user_id: str,
    snapshot: Any,
) -> dict[str, Any]:
    """Build the JSON view for one thread from a LangGraph state snapshot."""
    values = dict(getattr(snapshot, "values", None) or {})
    interrupts = extract_interrupt_payloads(snapshot) if snapshot is not None else []
    raw_phase = str(values.get("phase") or "").strip().lower()
    if raw_phase == "completed":
        raw_phase = "complete"

    if interrupts:
        status = "awaiting_input"
    elif raw_phase == "complete":
        status = "complete"
    else:
        status = "idle"

    raw_messages = values.get("messages") or []
    if not isinstance(raw_messages, list):
        raw_messages = list(raw_messages)
    messages: list[dict[str, Any]] = []
    for message in raw_messages:
        try:
            messages.append(serialize_message(message))
        except Exception:
            continue

    raw_errors = values.get("errors") or []
    if not isinstance(raw_errors, list):
        raw_errors = [raw_errors]
    errors = [str(item) for item in raw_errors if str(item).strip()]

    todos = values.get("todos")
    if not isinstance(todos, list):
        todos = []

    return {
        "thread_id": thread_id,
        "user_id": user_id,
        "title": "",
        "status": status,
        "phase": raw_phase or "collection",
        "ai_response": str(values.get("ai_response") or ""),
        "messages": messages,
        "interrupts": [json_safe(payload) for payload in interrupts],
        "todos": json_safe(todos),
        "errors": errors,
        "application_id": values.get("application_id"),
        "artifact_id": values.get("artifact_id"),
        "discovery_status": values.get("discovery_status"),
    }
