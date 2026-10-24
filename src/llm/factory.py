"""LLM factory — thin wrapper so agents stay provider-agnostic."""

from __future__ import annotations

import os
from typing import Any

from src.config.settings import get_settings

_llm: Any | None = None


def resolve_openai_api_key() -> str | None:
    """Return the OpenAI key from settings, the process env, or `.env`.

    Settings only bind `DICE_OPENAI_API_KEY`. The sample env file uses
    `OPENAI_API_KEY`, which pydantic-settings does not copy into the process
    environment, so read that name explicitly.
    """
    settings = get_settings()
    configured = (settings.openai_api_key or "").strip()
    if configured:
        return configured
    env_key = (os.getenv("OPENAI_API_KEY") or "").strip()
    if env_key:
        return env_key
    try:
        from dotenv import dotenv_values

        file_key = dotenv_values(".env").get("OPENAI_API_KEY")
    except Exception:
        return None
    if isinstance(file_key, str) and file_key.strip():
        return file_key.strip()
    return None


def get_llm() -> Any:
    """Return a cached chat model instance.

    Prefers langchain-openai when installed; falls back to a stub that raises
    on invoke so the graph can still be imported without credentials.
    """
    global _llm
    if _llm is not None:
        return _llm

    settings = get_settings()
    try:
        from langchain_openai import ChatOpenAI  # type: ignore[import]

        api_key = resolve_openai_api_key()
        if not api_key:
            raise RuntimeError(
                "OPENAI_API_KEY is not set. Add it to .env and restart the server."
            )
        _llm = ChatOpenAI(model=settings.llm_model, api_key=api_key)
        return _llm
    except ImportError:
        pass

    class _StubLLM:
        def invoke(self, *_args: Any, **_kwargs: Any) -> Any:
            raise RuntimeError(
                'No LLM backend configured. Install the web extras with '
                'pip install -e ".[web]" and set OPENAI_API_KEY in .env.'
            )

        async def ainvoke(self, *_args: Any, **_kwargs: Any) -> Any:
            return self.invoke(*_args, **_kwargs)

    _llm = _StubLLM()
    return _llm


def reset_llm() -> None:
    global _llm
    _llm = None
