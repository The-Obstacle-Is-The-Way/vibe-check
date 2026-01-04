"""Runtime settings (API keys, model IDs, thresholds) loaded from environment."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from pydantic import AliasChoices, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

if TYPE_CHECKING:
    from pydantic_ai.settings import ModelSettings


class Settings(BaseSettings):
    """Environment-based configuration (SSOT Section 11.2)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore", populate_by_name=True)

    # API Keys
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None
    google_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("GOOGLE_API_KEY", "GEMINI_API_KEY"),
    )

    # Model Selection (January 2026 Frontier)
    juror_gpt_model: str = "gpt-5.2"
    juror_claude_model: str = "claude-sonnet-4-5-20250929"
    juror_gemini_model: str = "gemini-3-pro-preview"
    judge_model: str = "claude-opus-4-5-20251101"

    # LLM Inference Settings (research reproducibility)
    llm_temperature: float = Field(default=0.0, ge=0.0, le=2.0)
    llm_top_p: float = Field(default=1.0, ge=0.0, le=1.0)
    llm_max_tokens: int = Field(default=2000, ge=1)
    llm_timeout: float = Field(default=60.0, gt=0.0)
    llm_seed: int | None = Field(default=None, ge=0)

    # Scoring Configuration
    runs_per_model: int = Field(default=2, ge=1, le=2)
    disagreement_range_threshold: int = 2
    arbitration_total_std_threshold: float = 2.0
    arbitration_max_prob_threshold: float = 0.60
    arbitration_entropy_threshold: float = 1.2
    clinical_ambiguity_band_low: float = Field(default=0.4, ge=0.0, le=1.0)
    clinical_ambiguity_band_high: float = Field(default=0.6, ge=0.0, le=1.0)
    insufficient_evidence_threshold: int = Field(default=2, ge=0)
    dirichlet_alpha: float = 0.5

    # Preprocessing
    scoring_dialogue_view: Literal["client_qa", "client_only"] = "client_qa"

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

    # LangGraph Execution
    graph_recursion_limit: int = Field(default=25, ge=1)

    # Checkpointing
    checkpoint_db: str = "sqlite:///data/checkpoints/vibe_check.db"

    # Output
    output_dir: str = "./data/outputs"
    prompt_version: str = "v1.0.0"

    def pydantic_ai_model_settings(self) -> ModelSettings:
        """Return PydanticAI ModelSettings for all LLM calls."""
        model_settings: ModelSettings = {
            "temperature": float(self.llm_temperature),
            "top_p": float(self.llm_top_p),
            "max_tokens": int(self.llm_max_tokens),
            "timeout": float(self.llm_timeout),
        }
        if self.llm_seed is not None:
            model_settings["seed"] = int(self.llm_seed)
        return model_settings

    @model_validator(mode="after")
    def _validate_clinical_ambiguity_band(self) -> Settings:
        if self.clinical_ambiguity_band_low > self.clinical_ambiguity_band_high:
            raise ValueError("clinical_ambiguity_band_low must be <= clinical_ambiguity_band_high")
        return self
