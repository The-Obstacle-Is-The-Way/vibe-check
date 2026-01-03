# Architecture

This section documents vibe-check's system architecture, data flow, and key design decisions.

---

## Overview

vibe-check is a multi-agent PHQ-8 scoring system built on:

- **LangGraph**: Workflow orchestration and checkpointing
- **PydanticAI**: LLM agents with structured outputs
- **NumPy/SciPy**: Bayesian aggregation math

---

## Documentation

| Document | Description |
|----------|-------------|
| [System Overview](system-overview.md) | High-level pipeline diagram |
| [Data Flow](data-flow.md) | Input → Processing → Output journey |
| [LangGraph Workflow](langgraph-workflow.md) | Single-dialogue graph and checkpointing |
| [Resilience](resilience.md) | Three-layer retry and rate-limiting strategy |

---

## Key Design Decisions

### 1. Multi-Agent Jury + Judge

Instead of single-model scoring, vibe-check uses 6 jurors (3 models × 2 runs) plus a judge for arbitration. This provides:
- Cross-model validation
- Uncertainty quantification
- Higher reliability than single-model approaches

### 2. Bayesian Aggregation

Juror votes are aggregated using Dirichlet posteriors and convolution, preserving:
- Full probability distributions
- Uncertainty metrics (entropy, credible intervals)
- Clinical probability estimates

### 3. Checkpoint-Based Processing

LangGraph with SQLite checkpointing enables:
- Resume-from-failure for long batch runs
- Per-dialogue state persistence
- Safe interruption without data loss

### 4. Three-Layer Resilience

API failures are handled by three complementary mechanisms:
- PydanticAI validation retries (malformed JSON)
- Tenacity transient retry (429, 5xx, network errors)
- Aiolimiter rate limiting (proactive throttling)

See [Resilience](resilience.md) for implementation wiring details.

---

## Module Map

```
src/vibe_check/
├── cli.py              # CLI entry point
├── settings.py         # Configuration
├── resilience.py       # Rate limiting, retry logic
├── constants.py        # PHQ-8 items, severity buckets
│
├── data/               # Corpus loading
├── preprocessing/      # Dialogue view extraction
├── schemas/            # Pydantic models
│
├── scoring/            # Juror agents
├── judge/              # Judge agent
├── aggregation/        # Bayesian math
│
├── graph/              # LangGraph workflow
├── run/                # Batch runner, checkpointing
├── diagnostics/        # Quality gates
└── export/             # Label export
```

---

## Technology Stack

| Component | Technology | Version |
|-----------|------------|---------|
| LLM Framework | PydanticAI | 1.0.0+ |
| Workflow | LangGraph | 1.0.5+ |
| Retry | Tenacity | 9.1.2+ |
| Rate Limiting | aiolimiter | 1.2.1+ |
| Math | NumPy, SciPy | 2.0.0+ / 1.14.0+ |
| Schemas | Pydantic | 2.10.0+ |
