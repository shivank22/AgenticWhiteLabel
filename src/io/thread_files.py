from __future__ import annotations

import json
from typing import Any, Mapping

try:
    from langchain.tools import ToolRuntime  # type: ignore[import]
except ImportError:  # pragma: no cover
    from langgraph.prebuilt.tool_node import ToolRuntime  # type: ignore[import]

from src.io.filesystem import filesystem_namespace
from src.memory.store import get_store, run_store_coro

_ALLOWED_ROOTS = (
    "/scratch/",
    "/artifacts/",
)


def normalize_file_path(path: str) -> str:
    normalized = "/" + path.strip().lstrip("/")
    if normalized == "/":
        raise ValueError("A file path is required")
    if ".." in normalized.split("/"):
        raise ValueError("Parent path traversal is not allowed")
    if not normalized.startswith(_ALLOWED_ROOTS):
        raise ValueError("Path must be below /scratch/ or /artifacts/")
    return normalized


def resolve_namespace(runtime: ToolRuntime[Any]) -> tuple[str, ...]:
    if runtime is None:
        raise RuntimeError("ToolRuntime was not injected")
    if runtime.store is None:
        raise RuntimeError("No LangGraph Store is configured for this execution")
    return filesystem_namespace(runtime)


class _Context:
    def __init__(self, user_id: str) -> None:
        self.user_id = user_id


class _ExecutionInfo:
    def __init__(self, thread_id: str) -> None:
        self.thread_id = thread_id


class _Runtime:
    def __init__(self, user_id: str, thread_id: str, store: Any) -> None:
        self.context = _Context(user_id)
        self.execution_info = _ExecutionInfo(thread_id)
        self.store = store


def _runtime_from_identity(*, user_id: str, thread_id: str, store: Any) -> _Runtime:
    return _Runtime(user_id=user_id, thread_id=thread_id, store=store)


async def _runtime_for_user_thread(*, user_id: str, thread_id: str) -> _Runtime:
    store = await get_store()
    if store is None:
        raise RuntimeError("No LangGraph Store is configured for this execution")
    return _runtime_from_identity(user_id=user_id, thread_id=thread_id, store=store)


async def write_text_file(
    *,
    runtime: ToolRuntime[Any],
    path: str,
    content: str,
    content_type: str = "text/plain",
    metadata: Mapping[str, Any] | None = None,
) -> str:
    namespace = resolve_namespace(runtime)
    normalized_path = normalize_file_path(path)
    value: dict[str, Any] = {
        "content": content,
        "content_type": content_type,
    }
    if metadata:
        value["metadata"] = dict(metadata)
    await runtime.store.aput(namespace, normalized_path, value)
    written = await runtime.store.aget(namespace, normalized_path)
    if written is None:
        raise RuntimeError(
            "File was not readable after write: "
            f"namespace={namespace!r}, path={normalized_path!r}"
        )
    return normalized_path


async def write_content_file(
    *,
    runtime: ToolRuntime[Any],
    path: str,
    content: str,
    content_type: str,
    metadata: Mapping[str, Any] | None = None,
) -> str:
    return await write_text_file(
        runtime=runtime,
        path=path,
        content=content,
        content_type=content_type,
        metadata=metadata,
    )


async def write_json_file(
    *,
    runtime: ToolRuntime[Any],
    path: str,
    payload: Any,
    metadata: Mapping[str, Any] | None = None,
) -> str:
    content = json.dumps(payload, ensure_ascii=False, default=str, indent=2)
    return await write_text_file(
        runtime=runtime,
        path=path,
        content=content,
        content_type="application/json",
        metadata=metadata,
    )


async def read_file(
    *,
    runtime: ToolRuntime[Any],
    path: str,
) -> dict[str, Any] | None:
    namespace = resolve_namespace(runtime)
    normalized_path = normalize_file_path(path)
    item = await runtime.store.aget(namespace, normalized_path)
    if item is None:
        return None
    value = getattr(item, "value", None)
    return value if isinstance(value, dict) else None


async def read_json_file(
    *,
    runtime: ToolRuntime[Any],
    path: str,
) -> dict[str, Any] | list[Any] | None:
    value = await read_file(runtime=runtime, path=path)
    if value is None:
        return None
    content = value.get("content")
    if isinstance(content, bytes):
        content = content.decode("utf-8")
    if not isinstance(content, str) or not content.strip():
        return None
    try:
        parsed = json.loads(content)
    except (ValueError, TypeError):
        return None
    if isinstance(parsed, (dict, list)):
        return parsed
    return None


async def write_text_for_user_thread(
    *,
    path: str,
    content: str,
    user_id: str,
    thread_id: str,
    content_type: str = "text/plain",
    metadata: Mapping[str, Any] | None = None,
) -> str:
    runtime = await _runtime_for_user_thread(user_id=user_id, thread_id=thread_id)
    return await write_text_file(
        runtime=runtime,
        path=path,
        content=content,
        content_type=content_type,
        metadata=metadata,
    )


async def write_json_for_user_thread(
    *,
    path: str,
    payload: Any,
    user_id: str,
    thread_id: str,
    metadata: Mapping[str, Any] | None = None,
) -> str:
    runtime = await _runtime_for_user_thread(user_id=user_id, thread_id=thread_id)
    return await write_json_file(
        runtime=runtime,
        path=path,
        payload=payload,
        metadata=metadata,
    )


async def read_file_for_user_thread(
    *,
    path: str,
    user_id: str,
    thread_id: str,
) -> dict[str, Any] | None:
    runtime = await _runtime_for_user_thread(user_id=user_id, thread_id=thread_id)
    return await read_file(runtime=runtime, path=path)


async def read_text_for_user_thread(
    *,
    path: str,
    user_id: str,
    thread_id: str,
) -> str | None:
    value = await read_file_for_user_thread(
        path=path,
        user_id=user_id,
        thread_id=thread_id,
    )
    if not isinstance(value, dict):
        return None
    content = value.get("content")
    if isinstance(content, bytes):
        return content.decode("utf-8")
    if isinstance(content, str):
        return content
    return None


async def read_json_for_user_thread(
    *,
    path: str,
    user_id: str,
    thread_id: str,
) -> dict[str, Any] | list[Any] | None:
    runtime = await _runtime_for_user_thread(user_id=user_id, thread_id=thread_id)
    return await read_json_file(runtime=runtime, path=path)


async def list_files_for_user_thread(
    *,
    user_id: str,
    thread_id: str,
    prefix: str = "/",
) -> list[str]:
    runtime = await _runtime_for_user_thread(user_id=user_id, thread_id=thread_id)
    namespace = resolve_namespace(runtime)
    normalized_prefix = "/" + prefix.replace("\\", "/").lstrip("/")
    found = await runtime.store.asearch(namespace)
    keys: list[str] = []
    for item in found:
        key = str(getattr(item, "key", "") or "")
        if key.startswith(normalized_prefix):
            keys.append(key)
    return sorted(keys)


async def delete_file_for_user_thread(
    *,
    path: str,
    user_id: str,
    thread_id: str,
) -> None:
    runtime = await _runtime_for_user_thread(user_id=user_id, thread_id=thread_id)
    namespace = resolve_namespace(runtime)
    normalized_path = normalize_file_path(path)
    if hasattr(runtime.store, "adelete"):
        await runtime.store.adelete(namespace, normalized_path)


def read_file_for_user_thread_sync(
    *,
    path: str,
    user_id: str,
    thread_id: str,
) -> dict[str, Any] | None:
    return run_store_coro(
        read_file_for_user_thread(path=path, user_id=user_id, thread_id=thread_id)
    )


def read_text_for_user_thread_sync(
    *,
    path: str,
    user_id: str,
    thread_id: str,
) -> str | None:
    return run_store_coro(
        read_text_for_user_thread(path=path, user_id=user_id, thread_id=thread_id)
    )


def write_text_for_user_thread_sync(
    *,
    path: str,
    content: str,
    user_id: str,
    thread_id: str,
    content_type: str = "text/plain",
    metadata: Mapping[str, Any] | None = None,
) -> str:
    return run_store_coro(
        write_text_for_user_thread(
            path=path,
            content=content,
            user_id=user_id,
            thread_id=thread_id,
            content_type=content_type,
            metadata=metadata,
        )
    )


def list_files_for_user_thread_sync(
    *,
    user_id: str,
    thread_id: str,
    prefix: str = "/",
) -> list[str]:
    return run_store_coro(
        list_files_for_user_thread(user_id=user_id, thread_id=thread_id, prefix=prefix)
    )


def delete_file_for_user_thread_sync(
    *,
    path: str,
    user_id: str,
    thread_id: str,
) -> None:
    run_store_coro(
        delete_file_for_user_thread(path=path, user_id=user_id, thread_id=thread_id)
    )
