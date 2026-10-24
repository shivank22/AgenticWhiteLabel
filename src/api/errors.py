"""Errors safe to show in the workflow chat UI."""

from __future__ import annotations

import re

_SECRET = re.compile(r"sk-[A-Za-z0-9_\-]{8,}")


class ChatError(Exception):
    """A workflow turn failed in a way the client can show."""

    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def public_error(exc: BaseException) -> str:
    """Return a short, single-line message with credential-shaped text removed."""
    text = " ".join(str(exc).split())
    text = _SECRET.sub("sk-…", text)
    if not text:
        text = exc.__class__.__name__
    if len(text) > 500:
        text = text[:499].rstrip() + "…"
    return text
