"""LangGraph checkpointer — Postgres when configured, MemorySaver otherwise."""

from __future__ import annotations

from typing import Any

_checkpointer: Any | None = None


async def get_checkpointer() -> Any:
    global _checkpointer
    if _checkpointer is not None:
        return _checkpointer

    from src.config.settings import get_settings

    settings = get_settings()
    dsn = settings.app_database_url or settings.database_url

    if dsn:
        try:
            from langgraph.checkpoint.postgres.aio import (  # type: ignore[import]
                AsyncPostgresSaver,
            )

            # Accept both SQLAlchemy-style and plain postgres URLs.
            pg_dsn = dsn.replace("postgresql+asyncpg://", "postgresql://", 1)
            saver = AsyncPostgresSaver.from_conn_string(pg_dsn)
            await saver.setup()
            _checkpointer = saver
            return _checkpointer
        except Exception:
            # Fall through to in-memory if Postgres wiring is unavailable.
            pass

    from langgraph.checkpoint.memory import MemorySaver  # type: ignore[import]

    _checkpointer = MemorySaver()
    return _checkpointer


async def reset_checkpointer() -> None:
    global _checkpointer
    if _checkpointer is not None and hasattr(_checkpointer, "aclose"):
        try:
            await _checkpointer.aclose()
        except Exception:
            pass
    _checkpointer = None
