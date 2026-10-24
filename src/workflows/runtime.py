"""Compiled graph singleton.

All routes that need the discovery graph obtain it via `get_compiled_graph()`.
This ensures the checkpointer and store are initialised exactly once per process.

Architecture note (doc 09 K1): the compiled graph is the ONLY writer of checkpoints.
"""

from __future__ import annotations

import asyncio
from typing import Any

_compiled_graph: Any | None = None
_rebuild_lock = asyncio.Lock()


async def get_compiled_graph() -> Any:
    """Return (and cache) the compiled top-level StateGraph.

    Initialises the checkpointer and store on first call.

    Note: The top-level graph is the orchestrator graph. It may invoke discovery
    as a deep agent.
    """
    global _compiled_graph
    if _compiled_graph is not None:
        return _compiled_graph

    from src.memory.checkpointer import get_checkpointer
    from src.memory.store import get_store
    from src.workflows.graphs.orchestrator_graph import build_orchestrator_graph

    checkpointer = await get_checkpointer()
    store = await get_store()

    _compiled_graph = await build_orchestrator_graph(
        checkpointer=checkpointer,
        store=store,
    )
    return _compiled_graph


async def rebuild_compiled_graph() -> Any:
    """Close shared database resources and build a fresh compiled graph."""
    from src.memory.checkpointer import reset_checkpointer
    from src.memory.store import reset_store

    reset_compiled_graph()
    await reset_checkpointer()
    await reset_store()
    return await get_compiled_graph()


def is_closed_connection_error(error: BaseException) -> bool:
    """Return whether an error indicates a stale database connection."""
    return "connection is closed" in str(error).lower()


async def get_graph_state(
    config: dict[str, Any], graph: Any | None = None
) -> tuple[Any, Any]:
    """Read graph state, rebuilding the shared graph once if its connection died."""
    graph = graph or await get_compiled_graph()
    try:
        return graph, await graph.aget_state(config)
    except Exception as error:
        if not is_closed_connection_error(error):
            raise
        async with _rebuild_lock:
            current_graph = _compiled_graph
            if current_graph is graph:
                graph = await rebuild_compiled_graph()
            else:
                graph = current_graph or await rebuild_compiled_graph()
        return graph, await graph.aget_state(config)


def reset_compiled_graph() -> None:
    """Reset the cached instance (test helper only)."""
    global _compiled_graph
    _compiled_graph = None
