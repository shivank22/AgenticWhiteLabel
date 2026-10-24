"""Async SQLAlchemy session helpers (used by runtime_notify)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from src.config.settings import get_settings

_engine: Any | None = None


def _get_engine() -> Any:
    global _engine
    if _engine is not None:
        return _engine

    from sqlalchemy.ext.asyncio import create_async_engine

    settings = get_settings()
    url = settings.app_database_url or settings.database_url
    if not url:
        raise RuntimeError(
            "No database URL configured (DICE_DATABASE_URL / DICE_APP_DATABASE_URL)."
        )
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    _engine = create_async_engine(url, pool_pre_ping=True)
    return _engine


@asynccontextmanager
async def session_context() -> AsyncIterator[Any]:
    from sqlalchemy.ext.asyncio import AsyncSession

    engine = _get_engine()
    async with AsyncSession(engine) as session:
        yield session
