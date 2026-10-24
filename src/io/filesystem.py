"""LangGraph Store namespace helpers for thread-scoped filesystem data."""

from __future__ import annotations

from typing import Any


def filesystem_namespace(runtime: Any) -> tuple[str, ...]:
    """Return ``("users", user_id, "threads", thread_id, "filesystem")``.

    Accepts:
    - ToolRuntime-style objects with ``context.user_id`` / ``execution_info.thread_id``
    - config / configurable mappings used by deepagents ``StoreBackend``
    """
    user_id = ""
    thread_id = ""

    context = getattr(runtime, "context", None)
    execution_info = getattr(runtime, "execution_info", None)
    if context is not None or execution_info is not None:
        user_id = str(getattr(context, "user_id", "") or "").strip()
        thread_id = str(getattr(execution_info, "thread_id", "") or "").strip()
    else:
        configurable: dict[str, Any] = {}
        if isinstance(runtime, dict):
            configurable = dict(runtime.get("configurable") or {})
            if not configurable and "user_id" in runtime:
                configurable = runtime
        else:
            configurable = dict(getattr(runtime, "configurable", None) or {})
            if not configurable:
                config = getattr(runtime, "config", None)
                if isinstance(config, dict):
                    configurable = dict(config.get("configurable") or {})

        user_id = str(configurable.get("user_id") or "").strip()
        thread_id = str(configurable.get("thread_id") or "").strip()

    if not user_id:
        raise RuntimeError("user_id is required in runtime context")

    if not thread_id:
        raise RuntimeError("thread_id is required in execution info")

    return (
        "users",
        user_id,
        "threads",
        thread_id,
        "filesystem",
    )
