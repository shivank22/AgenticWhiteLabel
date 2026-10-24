"""Local registry of chat threads.

Graph checkpoints live in the LangGraph saver. This file only remembers which
threads the UI created, plus display-only replies that must not be written
into the message channel (a human message inserted mid tool-call would break
the model transcript).
"""

from __future__ import annotations

import copy
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

logger = logging.getLogger(__name__)

NEW_THREAD_TITLE = "New migration"


def title_from_message(text: str) -> str:
    """Use the first line of a message as a short thread title."""
    line = " ".join(text.strip().split())
    if not line:
        return NEW_THREAD_TITLE
    if len(line) <= 52:
        return line
    return line[:51].rstrip() + "…"


def public_thread(record: dict[str, Any]) -> dict[str, Any]:
    """Return the sidebar shape for a thread, without stored replies."""
    return {
        "thread_id": record["thread_id"],
        "title": record.get("title") or NEW_THREAD_TITLE,
        "phase": record.get("phase") or "collection",
        "status": record.get("status") or "idle",
        "created_at": record.get("created_at"),
        "updated_at": record.get("updated_at"),
    }


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ThreadRegistry:
    """JSON-backed list of threads for one server process."""

    def __init__(self, path: Path | None = None) -> None:
        self._path = path if path is not None else Path("data/chat_threads.json")
        self._threads: dict[str, dict[str, Any]] = {}
        self._loaded = False
        self._lock: Any = None

    def _guard(self) -> Any:
        import asyncio

        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock

    async def _ensure(self) -> None:
        if self._loaded:
            return
        self._loaded = True
        if self._path is None or not self._path.is_file():
            return
        try:
            payload = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            logger.warning("Could not read the thread registry at %s", self._path)
            return
        threads = payload.get("threads") if isinstance(payload, dict) else None
        if not isinstance(threads, list):
            return
        for record in threads:
            thread_id = str(record.get("thread_id") or "") if isinstance(record, dict) else ""
            if thread_id:
                self._threads[thread_id] = record

    def _save(self) -> None:
        if self._path is None:
            return
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"threads": list(self._threads.values())}
        temporary = self._path.with_suffix(".tmp")
        temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        temporary.replace(self._path)

    async def list_threads(self, user_id: str) -> list[dict[str, Any]]:
        async with self._guard():
            await self._ensure()
            records = [
                copy.deepcopy(record)
                for record in self._threads.values()
                if record.get("user_id") == user_id
            ]
        records.sort(key=lambda record: record.get("updated_at") or "", reverse=True)
        return records

    async def create(self, user_id: str, title: str | None = None) -> dict[str, Any]:
        async with self._guard():
            await self._ensure()
            now = _now()
            record = {
                "thread_id": uuid4().hex,
                "user_id": user_id,
                "title": (title or "").strip() or NEW_THREAD_TITLE,
                "phase": "collection",
                "status": "idle",
                "replies": [],
                "created_at": now,
                "updated_at": now,
            }
            self._threads[record["thread_id"]] = record
            self._save()
            return copy.deepcopy(record)

    async def get(self, thread_id: str) -> dict[str, Any] | None:
        async with self._guard():
            await self._ensure()
            record = self._threads.get(thread_id)
            return copy.deepcopy(record) if record is not None else None

    async def delete(self, thread_id: str) -> bool:
        async with self._guard():
            await self._ensure()
            if thread_id not in self._threads:
                return False
            del self._threads[thread_id]
            self._save()
            return True

    async def add_reply(self, thread_id: str, *, index: int, content: str) -> dict[str, Any] | None:
        async with self._guard():
            await self._ensure()
            record = self._threads.get(thread_id)
            if record is None:
                return None
            reply = {
                "id": f"reply-{uuid4().hex[:10]}",
                "index": index,
                "content": content.strip(),
            }
            replies = list(record.get("replies") or [])
            replies.append(reply)
            record["replies"] = replies[-200:]
            record["updated_at"] = _now()
            self._save()
            return dict(reply)

    async def touch(
        self,
        thread_id: str,
        *,
        title: str | None = None,
        phase: str | None = None,
        status: str | None = None,
        bump: bool = True,
    ) -> dict[str, Any] | None:
        async with self._guard():
            await self._ensure()
            record = self._threads.get(thread_id)
            if record is None:
                return None
            changed = False
            if title and record.get("title") != title:
                record["title"] = title
                changed = True
            if phase and record.get("phase") != phase:
                record["phase"] = phase
                changed = True
            if status and record.get("status") != status:
                record["status"] = status
                changed = True
            if bump:
                record["updated_at"] = _now()
                changed = True
            if changed:
                self._save()
            return copy.deepcopy(record)
