---
severity: P3
status: fixed
fixed_date: 2026-01-02
---

# BUG-007: Settings configuration is incomplete

## Summary
`src/vibe_check/settings.py` only includes API keys. It misses the extensive configuration defined in `SPEC-vibe-check.md` Section 11.2, including model IDs, concurrency limits, and retry policies.

## Evidence
- `src/vibe_check/settings.py`: Only `*_api_key` fields exist.
- `docs/research/SPEC-vibe-check.md`: Section 11.2 lists `juror_gpt_model`, `runs_per_model`, `disagreement_range_threshold`, etc.

## Impact
- Hardcoded defaults (if they exist) or missing functionality when we switch to real agents.
- Inability to control costs or model versions via environment variables.

## Fix Plan
1. Update `Settings` class to match the spec (Model IDs, limits, thresholds).
2. Ensure defaults match the "January 2026 Frontier Models" table.

## Resolution (2026-01-02)

Updated `src/vibe_check/settings.py` to include full SSOT configuration:

```python
class Settings(BaseSettings):
    # API Keys
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None
    google_api_key: str | None = None

    # Juror Models (January 2026 frontier models)
    juror_gpt_model: str = "gpt-5.2"
    juror_claude_model: str = "claude-sonnet-4-5-20250929"
    juror_gemini_model: str = "gemini-3-pro-preview"

    # Judge Model
    judge_model: str = "claude-opus-4-5-20251101"

    # Scoring Configuration
    runs_per_model: int = 2
    disagreement_range_threshold: int = 2
    arbitration_total_std_threshold: float = 2.0
    dirichlet_alpha: float = 0.5

    # Concurrency and Rate Limiting
    max_concurrent_dialogues: int = 50
    openai_rpm: int = 100
    anthropic_rpm: int = 60
    google_rpm: int = 100
```
