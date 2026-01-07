# Configuration

All vibe-check settings and environment variables.

---

## Quick Setup

Create a `.env` file in the project root:

```bash
# Required for --live mode
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GOOGLE_API_KEY=...
```

---

## Environment Variables

### API Keys

| Variable | Required | Description |
|----------|----------|-------------|
| `OPENAI_API_KEY` | For `--live` | OpenAI API key |
| `ANTHROPIC_API_KEY` | For `--live` | Anthropic API key |
| `GOOGLE_API_KEY` | For `--live` | Google AI API key (or use `GEMINI_API_KEY`) |

### Model Selection

| Variable | Default | Description |
|----------|---------|-------------|
| `JUROR_GPT_MODEL` | `gpt-5.2` | OpenAI juror model |
| `JUROR_CLAUDE_MODEL` | `claude-sonnet-4-5-20250929` | Anthropic juror model |
| `JUROR_GEMINI_MODEL` | `gemini-3-pro-preview` | Google juror model |
| `JUDGE_MODEL` | `claude-opus-4-5-20251101` | Arbitration model |

### Scoring Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `RUNS_PER_MODEL` | `2` | Juror runs per model |
| `DIRICHLET_ALPHA` | `0.5` | Bayesian smoothing parameter |
| `SCORING_DIALOGUE_VIEW` | `client_qa` | Dialogue view for scoring |

### Arbitration Thresholds

| Variable | Default | Description |
|----------|---------|-------------|
| `ARBITRATION_MAX_PROB_THRESHOLD` | `0.60` | Min probability for consensus |
| `ARBITRATION_ENTROPY_THRESHOLD` | `1.2` | Max entropy before arbitration |
| `ARBITRATION_TOTAL_STD_THRESHOLD` | `2.0` | Max juror total std |
| `DISAGREEMENT_RANGE_THRESHOLD` | `2` | Vote range trigger |
| `CLINICAL_AMBIGUITY_BAND_LOW` | `0.4` | Lower bound for clinical ambiguity trigger (`P(score ≥ 2)`) |
| `CLINICAL_AMBIGUITY_BAND_HIGH` | `0.6` | Upper bound for clinical ambiguity trigger (`P(score ≥ 2)`) |
| `INSUFFICIENT_EVIDENCE_THRESHOLD` | `2` | Min juror count flagged insufficient evidence to trigger arbitration |

### Rate Limiting

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENAI_RPM` | `100` | OpenAI requests per minute |
| `ANTHROPIC_RPM` | `60` | Anthropic requests per minute |
| `GOOGLE_RPM` | `100` | Google requests per minute |

### Retry Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `MAX_RETRIES` | `5` | Transient retry attempts |
| `RETRY_INITIAL_WAIT` | `1.0` | Initial backoff (seconds) |
| `RETRY_MAX_WAIT` | `60.0` | Max backoff (seconds) |
| `RETRY_JITTER` | `5.0` | Random jitter (seconds) |
| `VALIDATION_RETRIES` | `2` | PydanticAI validation retries |

### Concurrency

| Variable | Default | Description |
|----------|---------|-------------|
| `MAX_CONCURRENT_DIALOGUES` | `50` | Parallel dialogue processing |

### Output

| Variable | Default | Description |
|----------|---------|-------------|
| `OUTPUT_DIR` | `./data/outputs` | Default output directory |
| `CHECKPOINT_DB` | `sqlite:///data/checkpoints/vibe_check.db` | Checkpoint database |
| `PROMPT_VERSION` | `v2.0.0-clinical` | Prompt version label |

---

## Example .env File

```bash
# API Keys (required for --live)
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GOOGLE_API_KEY=...

# Model Override (optional)
JUROR_GPT_MODEL=gpt-5.2
JUDGE_MODEL=claude-opus-4-5-20251101

# Performance Tuning (optional)
MAX_CONCURRENT_DIALOGUES=25
OPENAI_RPM=50
ANTHROPIC_RPM=30

# Retry Tuning (optional)
MAX_RETRIES=10
RETRY_INITIAL_WAIT=2.0

# Arbitration Tuning (optional)
ARBITRATION_ENTROPY_THRESHOLD=1.5
DIRICHLET_ALPHA=1.0
CLINICAL_AMBIGUITY_BAND_LOW=0.35
CLINICAL_AMBIGUITY_BAND_HIGH=0.65
INSUFFICIENT_EVIDENCE_THRESHOLD=3
```

---

## Settings Class

Settings are loaded via Pydantic:

```python
from vibe_check.settings import Settings

settings = Settings()  # Loads from .env and environment

print(settings.juror_gpt_model)     # "gpt-5.2"
print(settings.max_retries)         # 5
print(settings.openai_api_key)      # "sk-..."
```

---

## CLI Overrides

Some runtime behavior can be configured via CLI flags:

| Flag | Setting | CLI Command |
|------|---------|-------------|
| `--limit` | N/A (debug only) | `score-corpus` |
| `--live` | Use real APIs | `score-corpus` |
| `--max-concurrency` | `max_concurrent_dialogues` | `score-corpus` |
| `--dialogue-view` | `dialogue_view` (scoring text selection) | `score-corpus` |
| `--prompt-version` | `prompt_version` label (output/state) | `score-corpus` |
| `--strict` | N/A (exit code) | `diagnostics` |

---

## Threshold Tuning

### When to Increase Arbitration Thresholds

Increase thresholds if:
- Arbitration rate is too high (> 30%)
- Judge costs are too expensive
- Jurors generally agree

```bash
# More lenient (less arbitration)
ARBITRATION_MAX_PROB_THRESHOLD=0.50
ARBITRATION_ENTROPY_THRESHOLD=1.5
```

### When to Decrease Arbitration Thresholds

Decrease thresholds if:
- Quality gates are failing
- Juror disagreement is high
- Clinical accuracy is critical

```bash
# More strict (more arbitration)
ARBITRATION_MAX_PROB_THRESHOLD=0.70
ARBITRATION_ENTROPY_THRESHOLD=1.0
```

---

## Rate Limit Tuning

If you're hitting rate limits:

```bash
# Conservative rate limits
OPENAI_RPM=30
ANTHROPIC_RPM=20
GOOGLE_RPM=30
MAX_CONCURRENT_DIALOGUES=10
```

If you have higher limits:

```bash
# Aggressive (with tier 4+ access)
OPENAI_RPM=500
ANTHROPIC_RPM=200
GOOGLE_RPM=300
MAX_CONCURRENT_DIALOGUES=100
```

---

## Model Selection

### Available Models (January 2026)

| Provider | Model ID | Notes |
|----------|----------|-------|
| OpenAI | `gpt-5.2` | Default juror |
| OpenAI | `gpt-4o` | Alternative |
| Anthropic | `claude-sonnet-4-5-20250929` | Default juror |
| Anthropic | `claude-opus-4-5-20251101` | Default judge |
| Google | `gemini-3-pro-preview` | Default juror |

### Changing Models

```bash
# Use different juror models
JUROR_GPT_MODEL=gpt-4o
JUROR_CLAUDE_MODEL=claude-3-opus-20240229
```

---

## Troubleshooting

### Settings Not Loading

Ensure `.env` is in the project root:

```bash
ls -la .env
# Should exist and be readable
```

### API Keys Not Working

Check they're exported:

```bash
python -c "from vibe_check.settings import Settings; s = Settings(); print(bool(s.openai_api_key))"
# Should print: True
```

### Model Not Found

Verify model ID is correct for the provider. Check provider documentation for current model names.
