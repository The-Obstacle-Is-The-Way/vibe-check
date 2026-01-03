"""Runtime settings (API keys, model IDs, thresholds) loaded from environment."""

from __future__ import annotations

from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-based configuration (SSOT Section 11.2)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # API Keys
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None
    google_api_key: str | None = None

    # Model Selection (January 2026 Frontier)
    juror_gpt_model: str = "gpt-5.2"
    juror_claude_model: str = "claude-sonnet-4-5-20250929"
    juror_gemini_model: str = "gemini-3-pro-preview"
    judge_model: str = "claude-opus-4-5-20251101"

    # Scoring Configuration
    runs_per_model: int = 2
    disagreement_range_threshold: int = 2
    arbitration_total_std_threshold: float = 2.0
    arbitration_max_prob_threshold: float = 0.60
    arbitration_entropy_threshold: float = 1.2
    dirichlet_alpha: float = 0.5

    # Preprocessing
    scoring_dialogue_view: Literal["client_qa", "client_only"] = "client_qa"
    embedding_dialogue_view: Literal["client_qa", "client_contextualized", "client_only"] = (
        "client_qa"
    )

    # Concurrency
    max_concurrent_dialogues: int = 50

    # Rate Limiting (RPM)
    openai_rpm: int = 100
    anthropic_rpm: int = 60
    google_rpm: int = 100

    # Retry Configuration (ADR-001)
    max_retries: int = 5
    retry_initial_wait: float = 1.0
    retry_max_wait: float = 60.0
    retry_jitter: float = 5.0
    validation_retries: int = 2

    # Checkpointing
    checkpoint_db: str = "sqlite:///data/checkpoints/vibe_check.db"

    # Output
    output_dir: str = "./data/outputs"
    prompt_version: str = "v1.0.0"
