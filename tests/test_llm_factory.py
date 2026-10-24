"""OpenAI key resolution used by the chat UI."""

import pytest

from src.config.settings import get_settings
from src.llm.factory import get_llm, reset_llm, resolve_openai_api_key


def test_resolve_openai_api_key_from_dotenv(monkeypatch, tmp_path):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("DICE_OPENAI_API_KEY", raising=False)
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text("OPENAI_API_KEY=sk-test-value\n", encoding="utf-8")
    get_settings.cache_clear()
    try:
        assert resolve_openai_api_key() == "sk-test-value"
    finally:
        get_settings.cache_clear()


def test_get_llm_requires_api_key(monkeypatch, tmp_path):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("DICE_OPENAI_API_KEY", raising=False)
    monkeypatch.chdir(tmp_path)
    get_settings.cache_clear()
    reset_llm()
    try:
        with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
            get_llm()
    finally:
        reset_llm()
        get_settings.cache_clear()
