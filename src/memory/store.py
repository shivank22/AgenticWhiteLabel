"""Optional LangGraph Store for semantic / filesystem-backed agent memory."""

from __future__ import annotations

import asyncio
from collections.abc import Coroutine
from typing import Any, TypeVar

_store: Any | None = None
_T = TypeVar("_T")


async def get_store() -> Any:
    """Return a shared store (Postgres when configured, else in-memory)."""
    global _store
    if _store is not None:
        return _store

    from src.config.settings import get_settings

    settings = get_settings()
    dsn = settings.app_database_url or settings.database_url

    if dsn:
        try:
            from langgraph.store.postgres.aio import (  # type: ignore[import]
                AsyncPostgresStore,
            )

            pg_dsn = dsn.replace("postgresql+asyncpg://", "postgresql://", 1)
            store = AsyncPostgresStore.from_conn_string(pg_dsn)
            await store.setup()
            _store = store
            return _store
        except Exception:
            pass

    from langgraph.store.memory import InMemoryStore  # type: ignore[import]

    _store = InMemoryStore()
    return _store


async def reset_store() -> None:
    global _store
    if _store is not None and hasattr(_store, "aclose"):
        try:
            await _store.aclose()
        except Exception:
            pass
    _store = None


def run_store_coro(coro: Coroutine[Any, Any, _T]) -> _T:
    """Run an async store helper from sync tool/code paths.

    Uses the running loop when present (via a dedicated thread), otherwise
    ``asyncio.run``.
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    import concurrent.futures

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coro).result()
