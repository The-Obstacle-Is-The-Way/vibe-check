"""Runtime settings (API keys, model IDs) loaded from environment."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-based configuration.

    This project keeps provider SDKs optional and expects API keys to be supplied
    via environment variables or a local `.env` file (never committed).
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    openai_api_key: str | None = None
    anthropic_api_key: str | None = None
    google_api_key: str | None = None
