from __future__ import annotations

from typing import Any

from src.io.thread_files import (
    read_file_for_user_thread as io_read_file_for_user_thread,
    write_text_for_user_thread as io_write_text_for_user_thread,
)


async def read_file_for_user_thread(
    *,
    path: str,
    user_id: str,
    thread_id: str,
) -> dict[str, Any] | None:
    return await io_read_file_for_user_thread(
        path=path,
        user_id=user_id,
        thread_id=thread_id,
    )


async def write_file_for_user_thread(
    *,
    path: str,
    content: str,
    user_id: str,
    thread_id: str,
    content_type: str = "text/plain",
    metadata: dict[str, Any] | None = None,
) -> str:
    return await io_write_text_for_user_thread(
        path=path,
        content=content,
        user_id=user_id,
        thread_id=thread_id,
        content_type=content_type,
        metadata=metadata,
    )
