# Reliability

This section documents quality assurance mechanisms: quality gates that validate scoring runs, and resilience strategies that handle API failures.

---

## Documents

| Document | Description |
|----------|-------------|
| [Quality Gates](quality-gates.md) | Statistical validation of scoring runs |
| [Resilience](resilience.md) | Three-layer retry and rate-limiting strategy |

---

## Overview

Reliability in vibe-check has two aspects:

### 1. Run Quality (Quality Gates)

After scoring completes, diagnostics validate:

| Gate | Metric | Threshold |
|------|--------|-----------|
| Reliability | Krippendorff α | ≥ 0.67 |
| Consistency | Cronbach α | ≥ 0.70 |
| Separation | Separation validity | MDD > control, p < 0.01, d ≥ 0.5 |
| Arbitration | Rate | < 30% |

All gates must pass before labels are exported.

### 2. API Resilience (Three Layers)

LLM API calls are protected by three layers:

```
┌─────────────────────────────────────────────────────────────┐
│                    RESILIENCE LAYERS                        │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Layer 3: Rate Limiting (aiolimiter)                        │
│    → Prevents 429 errors proactively                        │
│                                                             │
│  Layer 2: Transient Retry (tenacity)                        │
│    → Exponential backoff for 429, 5xx, network errors       │
│                                                             │
│  Layer 1: Validation Retry (PydanticAI)                     │
│    → Re-prompts on malformed JSON output                    │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Why Both?

Quality gates ensure **statistical reliability** of the scoring output. Resilience ensures **operational reliability** during scoring runs.

Together they provide:
- Trustworthy labels (validated by gates)
- Robust execution (protected by resilience)

---

## Related Sections

- [Scoring](../scoring/) - What generates the data being validated
- [Architecture: Resilience](../architecture/resilience.md) - Implementation details
