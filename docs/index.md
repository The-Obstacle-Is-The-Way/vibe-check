# vibe-check Documentation

Multi-agent PHQ-8 scoring for synthetic therapy dialogues.

---

## What is vibe-check?

vibe-check is a Python library that uses a jury of LLM agents to score synthetic therapy dialogues on the PHQ-8 depression screening scale. It's designed for researchers working with the SQPsychConv dataset.

**Key Features**:
- 6 independent jurors (3 models × 2 runs) score each dialogue
- Bayesian aggregation combines votes into probability distributions
- Judge arbitration resolves disagreements on contested items
- Quality gates validate scoring reliability and consistency

---

## Quick Start

```bash
# Install
pip install vibe-check

# Configure
cp .env.example .env
# Edit .env with your API keys

# Dry run (fake jurors)
vibe-check score-corpus \
    --input data/sqpsychconv/qwen-2.5 \
    --checkpoint sqlite:///data/outputs/checkpoint.db \
    --output data/outputs \
    --limit 10

# Production run (real APIs)
vibe-check score-corpus \
    --input data/sqpsychconv/qwen-2.5 \
    --checkpoint sqlite:///data/outputs/checkpoint.db \
    --output data/outputs \
    --live
```

See [Quickstart Guide](guides/quickstart.md) for complete setup instructions.

---

## Documentation

### Scoring

The core scoring pipeline: jurors, aggregation, and arbitration.

| Document | Description |
|----------|-------------|
| [Overview](scoring/index.md) | Scoring pipeline overview |
| [Jury Consensus](scoring/jury-consensus.md) | How 6 jurors vote independently |
| [Bayesian Aggregation](scoring/bayesian-aggregation.md) | Combining votes into distributions |
| [Arbitration](scoring/arbitration.md) | When and why the judge intervenes |

### Preprocessing

How raw dialogues become scoring text.

| Document | Description |
|----------|-------------|
| [Overview](preprocessing/index.md) | Preprocessing pipeline overview |
| [Dialogue Views](preprocessing/dialogue-views.md) | client_qa, client_only, and artifact removal |

### Reliability

Quality assurance and API resilience.

| Document | Description |
|----------|-------------|
| [Overview](reliability/index.md) | Reliability overview |
| [Quality Gates](reliability/quality-gates.md) | Validating scoring runs |
| [Resilience](reliability/resilience.md) | Three-layer retry strategy |

### Guides

Step-by-step instructions for common tasks.

| Guide | Description |
|-------|-------------|
| [Quickstart](guides/quickstart.md) | Get running in 5 minutes |
| [Scoring a Corpus](guides/scoring-corpus.md) | Full production run |
| [Running Diagnostics](guides/running-diagnostics.md) | Quality gate checks |
| [Exporting Labels](guides/exporting-labels.md) | Public label export |
| [Configuration](guides/configuration.md) | Environment variables |
| [Troubleshooting](guides/troubleshooting.md) | Common errors and fixes |

### Architecture

System design and data flow.

| Document | Description |
|----------|-------------|
| [System Overview](architecture/system-overview.md) | High-level pipeline |
| [Data Flow](architecture/data-flow.md) | Input to output schemas |
| [LangGraph Workflow](architecture/langgraph-workflow.md) | Single-dialogue graph |
| [Resilience](architecture/resilience.md) | Three-layer implementation details |

### Agents

The LLM agents that power scoring.

| Document | Description |
|----------|-------------|
| [Overview](agents/index.md) | Agent system overview |
| [Juror Agent](agents/juror.md) | PHQ-8 scoring agent |
| [Judge Agent](agents/judge.md) | Arbitration agent |

### Reference

Technical specifications and lookup tables.

| Document | Description |
|----------|-------------|
| [CLI Reference](reference/cli.md) | All commands and flags |
| [Schemas](reference/schemas.md) | Pydantic data models |
| [Settings](reference/settings.md) | Configuration fields |
| [Thresholds](reference/thresholds.md) | Numeric thresholds |

---

## Pipeline Overview

```
┌─────────────┐     ┌─────────────────┐     ┌─────────────┐
│  SQPsychConv│────▶│  Preprocessing  │────▶│   6 Jurors  │
│   Corpus    │     │  (DialogueViews)│     │ (sequential)│
└─────────────┘     └─────────────────┘     └──────┬──────┘
                                                   │
                                                   ▼
┌─────────────┐     ┌─────────────────┐     ┌─────────────┐
│   Export    │◀────│   Diagnostics   │◀────│ Aggregation │
│ labels.jsonl│     │  Quality Gates  │     │  + Judge    │
└─────────────┘     └─────────────────┘     └─────────────┘
```

1. **Input**: SQPsychConv dialogue corpus
2. **Preprocessing**: Extract client_qa or client_only views
3. **Jury Phase**: 6 jurors score each dialogue independently
4. **Aggregation**: Bayesian combination of votes
5. **Arbitration**: Judge resolves contested items
6. **Diagnostics**: Quality gate validation
7. **Export**: Public label files

---

## Key Schemas

| Schema | Purpose | Location |
|--------|---------|----------|
| `SQPsychConvDialogue` | Input corpus record | `schemas/input.py` |
| `DialogueViews` | Preprocessed views | `schemas/views.py` |
| `PHQ8Report` | Single juror output | `schemas/scoring.py` |
| `AggregatedPHQ8` | Final aggregated output | `schemas/output.py` |
| `ScoredDialogueExport` | Public export format | `export/schemas.py` |

---

## Configuration

Essential environment variables:

```bash
# API Keys (required for --live)
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GOOGLE_API_KEY=AIza...  # or GEMINI_API_KEY=AIza...

# Models
JUROR_GPT_MODEL=gpt-5.2
JUDGE_MODEL=claude-opus-4-5-20251101

# Thresholds
ARBITRATION_ENTROPY_THRESHOLD=1.2
DIRICHLET_ALPHA=0.5
```

See [Settings Reference](reference/settings.md) for all options.

---

## Quality Gates

A scoring run must pass:

| Gate | Threshold | Measures |
|------|-----------|----------|
| Reliability | Krippendorff α ≥ 0.67 | Inter-rater agreement |
| Consistency | Cronbach α ≥ 0.70 | Internal consistency |
| Separation | MDD > control, p<0.01, d≥0.5 | Clinical validity |
| Arbitration | Rate < 30% | Juror consensus |

See [Quality Gates](reliability/quality-gates.md) for details.

---

## Additional Resources

- [Dataset: SQPsychConv](data/dataset-sqpsychconv-all-variants.md)
- [SPEC-09: Human Alignment](_specs/spec-09-human-alignment.md)
