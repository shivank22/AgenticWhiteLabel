from __future__ import annotations

import json
import logging
from typing import Any

try:
    from langchain.tools import ToolRuntime  # type: ignore[import]
except ImportError:  # pragma: no cover
    from langgraph.prebuilt.tool_node import ToolRuntime  # type: ignore[import]

from src.workflows.tools.filesystem_io import write_file_for_user_thread

logger = logging.getLogger(__name__)


async def persist_successful_api_result(
    *,
    runtime: ToolRuntime[Any],
    api_name: str,
    path: str,
    response: dict[str, Any],
) -> dict[str, Any]:
    if "error" in response:
        return response
    try:
        user_id = str(
            getattr(getattr(runtime, "context", None), "user_id", "") or ""
        ).strip()
        thread_id = str(
            getattr(getattr(runtime, "execution_info", None), "thread_id", "")
            or ""
        ).strip()
        if not user_id or not thread_id:
            raise RuntimeError("runtime context missing user_id/thread_id")

        saved_path = await write_file_for_user_thread(
            path=path,
            content=json.dumps(response, ensure_ascii=False, default=str, indent=2),
            user_id=user_id,
            thread_id=thread_id,
            content_type="application/json",
            metadata={"source": "api", "api_name": api_name},
        )
    except Exception as exc:
        logger.exception("%s succeeded, but response persistence failed", api_name)
        return {
            **response,
            "persist_error": str(exc),
        }

    return {
        **response,
        "persisted_path": saved_path,
    }
