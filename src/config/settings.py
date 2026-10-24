"""Application settings for the DICE backend."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="DICE_",
        extra="ignore",
    )

    skills_base_path: str = "skills"
    database_url: str | None = None
    app_database_url: str | None = None
    llm_provider: str = "openai"
    llm_model: str = "gpt-4o"
    openai_api_key: str | None = None

    # Authenticated API / PACE discovery
    api_bearer_token: str | None = None
    pace_servers_url: str | None = None
    pace_token_url: str | None = None
    pace_client_id: str | None = None
    pace_client_secret: str | None = None
    pace_scope: str | None = None

    web_host: str = "127.0.0.1"
    web_port: int = 8080


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
