# Settings Reference

Complete reference for all vibe-check configuration fields.

---

## Overview

Settings are loaded via Pydantic from environment variables and `.env` files:

```python
from vibe_check.settings import Settings

settings = Settings()  # Loads from .env and environment
```

**File**: `src/vibe_check/settings.py`

---

## API Keys

Required for `--live` mode (real LLM API calls).

| Field | Env Variable | Type | Default | Description |
|-------|--------------|------|---------|-------------|
| `openai_api_key` | `OPENAI_API_KEY` | `str \| None` | `None` | OpenAI API key |
| `anthropic_api_key` | `ANTHROPIC_API_KEY` | `str \| None` | `None` | Anthropic API key |
| `google_api_key` | `GOOGLE_API_KEY` or `GEMINI_API_KEY` | `str \| None` | `None` | Google AI API key (accepts both aliases) |

**Example**:

```bash
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GOOGLE_API_KEY=AIza...
```

---

## Model Selection

Which LLM models to use for jurors and judge.

| Field | Env Variable | Type | Default | Description |
|-------|--------------|------|---------|-------------|
| `juror_gpt_model` | `JUROR_GPT_MODEL` | `str` | `gpt-5.2` | OpenAI juror model |
| `juror_claude_model` | `JUROR_CLAUDE_MODEL` | `str` | `claude-sonnet-4-5-20250929` | Anthropic juror model |
| `juror_gemini_model` | `JUROR_GEMINI_MODEL` | `str` | `gemini-3-pro-preview` | Google juror model |
| `judge_model` | `JUDGE_MODEL` | `str` | `claude-opus-4-5-20251101` | Arbitration judge model |

**Notes**:
- Default models are January 2026 frontier models
- Judge uses Claude Opus for highest reasoning capability
- Each juror model runs twice (6 total jurors)

**Example**:

```bash
JUROR_GPT_MODEL=gpt-4o
JUDGE_MODEL=claude-opus-4-5-20251101
```

---

## Scoring Configuration

Controls juror behavior and aggregation.

| Field | Env Variable | Type | Default | Description |
|-------|--------------|------|---------|-------------|
| `runs_per_model` | `RUNS_PER_MODEL` | `int` | `2` | How many times each model scores (range: 1–2) |
| `disagreement_range_threshold` | `DISAGREEMENT_RANGE_THRESHOLD` | `int` | `2` | Vote range that triggers arbitration |
| `arbitration_total_std_threshold` | `ARBITRATION_TOTAL_STD_THRESHOLD` | `float` | `2.0` | Max juror total std before arbitration |
| `arbitration_max_prob_threshold` | `ARBITRATION_MAX_PROB_THRESHOLD` | `float` | `0.60` | Min posterior max probability for consensus |
| `arbitration_entropy_threshold` | `ARBITRATION_ENTROPY_THRESHOLD` | `float` | `1.2` | Max entropy before arbitration |
| `clinical_ambiguity_band_low` | `CLINICAL_AMBIGUITY_BAND_LOW` | `float` | `0.4` | Lower bound for clinical ambiguity trigger (`P(score ≥ 2)`) |
| `clinical_ambiguity_band_high` | `CLINICAL_AMBIGUITY_BAND_HIGH` | `float` | `0.6` | Upper bound for clinical ambiguity trigger (`P(score ≥ 2)`) |
| `insufficient_evidence_threshold` | `INSUFFICIENT_EVIDENCE_THRESHOLD` | `int` | `2` | Min juror count flagged as insufficient evidence to trigger arbitration |
| `dirichlet_alpha` | `DIRICHLET_ALPHA` | `float` | `0.5` | Bayesian smoothing parameter |

**See**: [Thresholds Reference](thresholds.md) for detailed explanations.

---

## Preprocessing

How dialogues are prepared for scoring.

| Field | Env Variable | Type | Default | Description |
|-------|--------------|------|---------|-------------|
| `scoring_dialogue_view` | `SCORING_DIALOGUE_VIEW` | `Literal["client_qa", "client_only"]` | `client_qa` | View for PHQ-8 scoring |

**Options**:

| View | Description |
|------|-------------|
| `client_qa` | Client text + therapist questions (recommended) |
| `client_only` | Client text only |

---

## Concurrency

Parallel processing limits.

| Field | Env Variable | Type | Default | Description |
|-------|--------------|------|---------|-------------|
| `max_concurrent_dialogues` | `MAX_CONCURRENT_DIALOGUES` | `int` | `50` | Max dialogues processed in parallel |

**Tuning**:
- Increase for faster processing (if rate limits allow)
- Decrease if hitting memory limits or rate limits

---

## Rate Limiting

Proactive rate limiting per provider (requests per minute).

| Field | Env Variable | Type | Default | Description |
|-------|--------------|------|---------|-------------|
| `openai_rpm` | `OPENAI_RPM` | `int` | `100` | OpenAI requests per minute |
| `anthropic_rpm` | `ANTHROPIC_RPM` | `int` | `60` | Anthropic requests per minute |
| `google_rpm` | `GOOGLE_RPM` | `int` | `100` | Google requests per minute |

**Notes**:
- These are enforced proactively via `aiolimiter`
- Set below your actual tier limits to avoid 429 errors
- Per-provider, not per-model

**Example** (conservative):

```bash
OPENAI_RPM=30
ANTHROPIC_RPM=20
GOOGLE_RPM=30
```

---

## Retry Configuration

Transient error retry behavior (ADR-001).

| Field | Env Variable | Type | Default | Description |
|-------|--------------|------|---------|-------------|
| `max_retries` | `MAX_RETRIES` | `int` | `5` | Maximum retry attempts |
| `retry_initial_wait` | `RETRY_INITIAL_WAIT` | `float` | `1.0` | Initial backoff (seconds) |
| `retry_max_wait` | `RETRY_MAX_WAIT` | `float` | `60.0` | Maximum backoff (seconds) |
| `retry_jitter` | `RETRY_JITTER` | `float` | `5.0` | Random jitter range (seconds) |
| `validation_retries` | `VALIDATION_RETRIES` | `int` | `2` | PydanticAI schema retries |

**Retry Strategy**:
- Exponential backoff: `wait = min(initial * 2^attempt, max_wait)`
- Jitter: `±jitter` seconds random
- Retries on: 429, 5xx, network timeouts

---

## Checkpointing

LangGraph state persistence.

| Field | Env Variable | Type | Default | Description |
|-------|--------------|------|---------|-------------|
| `checkpoint_db` | `CHECKPOINT_DB` | `str` | `sqlite:///data/checkpoints/vibe_check.db` | SQLite checkpoint path |

**Format**: SQLAlchemy connection string (must start with `sqlite:///`)

---

## Output

Default output paths and versioning.

| Field | Env Variable | Type | Default | Description |
|-------|--------------|------|---------|-------------|
| `output_dir` | `OUTPUT_DIR` | `str` | `./data/outputs` | Default output directory |
| `prompt_version` | `PROMPT_VERSION` | `str` | `v1.0.0` | Prompt version label |

**Notes**:
- `prompt_version` is embedded in outputs for reproducibility
- Change when prompts are modified

---

## Complete .env Example

```bash
# API Keys (required for --live)
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GOOGLE_API_KEY=AIza...

# Model Selection
JUROR_GPT_MODEL=gpt-5.2
JUROR_CLAUDE_MODEL=claude-sonnet-4-5-20250929
JUROR_GEMINI_MODEL=gemini-3-pro-preview
JUDGE_MODEL=claude-opus-4-5-20251101

# Scoring
RUNS_PER_MODEL=2
DIRICHLET_ALPHA=0.5

# Arbitration Thresholds
ARBITRATION_TOTAL_STD_THRESHOLD=2.0
ARBITRATION_MAX_PROB_THRESHOLD=0.60
ARBITRATION_ENTROPY_THRESHOLD=1.2
DISAGREEMENT_RANGE_THRESHOLD=2
CLINICAL_AMBIGUITY_BAND_LOW=0.4
CLINICAL_AMBIGUITY_BAND_HIGH=0.6
INSUFFICIENT_EVIDENCE_THRESHOLD=2

# Preprocessing
SCORING_DIALOGUE_VIEW=client_qa

# Concurrency
MAX_CONCURRENT_DIALOGUES=50

# Rate Limiting
OPENAI_RPM=100
ANTHROPIC_RPM=60
GOOGLE_RPM=100

# Retry
MAX_RETRIES=5
RETRY_INITIAL_WAIT=1.0
VALIDATION_RETRIES=2

# Output
OUTPUT_DIR=./data/outputs
PROMPT_VERSION=v1.0.0
```

---

## Programmatic Access

```python
from vibe_check.settings import Settings

settings = Settings()

# Check API keys
if settings.openai_api_key:
    print("OpenAI configured")

# Get model names
print(settings.juror_gpt_model)     # "gpt-5.2"
print(settings.judge_model)          # "claude-opus-4-5-20251101"

# Get thresholds
print(settings.arbitration_entropy_threshold)  # 1.2
print(settings.dirichlet_alpha)                # 0.5
print(settings.clinical_ambiguity_band_low)    # 0.4
print(settings.insufficient_evidence_threshold)  # 2
```

---

## CLI Overrides

Some settings can be overridden via CLI flags:

| CLI Flag | Overrides | Command |
|----------|-----------|---------|
| `--max-concurrency` | `max_concurrent_dialogues` | `score-corpus` |
| `--dialogue-view` | `scoring_dialogue_view` (used in agent prompts) | `score-corpus` |
| `--prompt-version` | `prompt_version` (used in agent prompts) | `score-corpus` |

CLI flags take full precedence in `--live` mode. The `--prompt-version` and `--dialogue-view` values are used both:
- In the scoring text selection (runner)
- In the agent system prompts (jurors and judge)

This ensures CLI args always match what agents actually use (BUG-027 fix).
