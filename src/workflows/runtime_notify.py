"""Dedicated Postgres LISTEN/NOTIFY connection for cross-pod chat task coordination."""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from collections.abc import Callable

import asyncpg
from sqlalchemy import text

from src.config.settings import get_settings
from src.db.session import session_context

JOBS_CHANNEL = "dice_chat_jobs"
EVENTS_CHANNEL = "dice_chat_task_events"

logger = logging.getLogger(__name__)

_conn: asyncpg.Connection | None = None
_listener_task: asyncio.Task | None = None
_job_callbacks: list[Callable[[str], None]] = []
_waiters: dict[str, list[asyncio.Queue]] = defaultdict(list)


def _dsn() -> str:
    settings = get_settings()
    url = settings.app_database_url or settings.database_url or ""
    return url.replace("postgresql+asyncpg://", "postgresql://", 1)


def on_job(callback: Callable[[str], None]) -> None:
    _job_callbacks.append(callback)


def register_waiter(task_id: str) -> asyncio.Queue:
    queue: asyncio.Queue = asyncio.Queue()
    _waiters[task_id].append(queue)
    return queue


def unregister_waiter(task_id: str, queue: asyncio.Queue) -> None:
    waiters = _waiters.get(task_id)
    if not waiters:
        return
    if queue in waiters:
        waiters.remove(queue)
    if not waiters:
        _waiters.pop(task_id, None)


def _on_notify(_connection: object, _pid: int, channel: str, payload: str) -> None:
    if channel == JOBS_CHANNEL:
        for callback in _job_callbacks:
            callback(payload)
    elif channel == EVENTS_CHANNEL:
        for queue in _waiters.get(payload, []):
            queue.put_nowait(None)


async def _run_listener() -> None:
    global _conn
    while True:
        try:
            conn = await asyncpg.connect(_dsn())
            await conn.add_listener(JOBS_CHANNEL, _on_notify)
            await conn.add_listener(EVENTS_CHANNEL, _on_notify)
            _conn = conn
            while not conn.is_closed():
                await asyncio.sleep(5)
        except Exception:
            logger.exception("runtime_notify listener lost connection, reconnecting")
            _conn = None
            await asyncio.sleep(2)


async def start() -> None:
    global _listener_task
    _listener_task = asyncio.create_task(_run_listener())


async def stop() -> None:
    global _listener_task, _conn
    if _listener_task is not None:
        _listener_task.cancel()
        _listener_task = None
    if _conn is not None:
        await _conn.close()
        _conn = None


async def notify(channel: str, payload: str) -> None:
    async with session_context() as session:
        await session.execute(
            text("SELECT pg_notify(:channel, :payload)"),
            {"channel": channel, "payload": payload},
        )
        await session.commit()
