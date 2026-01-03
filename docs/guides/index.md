# Guides

Step-by-step instructions for common vibe-check tasks.

---

## Prerequisites

Before using vibe-check, ensure you have:

1. **Python 3.11+** installed
2. **uv** package manager (`pip install uv`)
3. **API keys** for LLM providers (OpenAI, Anthropic, Google)
4. **SQPsychConv dataset** in `data/sqpsychconv/`

---

## Guides

| Guide | Description |
|-------|-------------|
| [Quickstart](quickstart.md) | Get running in 5 minutes |
| [Scoring a Corpus](scoring-corpus.md) | Full production run walkthrough |
| [Running Diagnostics](running-diagnostics.md) | Validate scoring quality |
| [Exporting Labels](exporting-labels.md) | Create public label files |
| [Configuration](configuration.md) | Environment variables and settings |
| [Troubleshooting](troubleshooting.md) | Common errors and fixes |

---

## Workflow Overview

A typical vibe-check workflow:

```
1. Configure API keys (one-time)
        ↓
2. Run scoring (score-corpus command)
        ↓
3. Run diagnostics (validate quality)
        ↓
4. Export labels (public format)
```

---

## Quick Reference

### Dry Run (No API Calls)

```bash
uv run vibe-check score-corpus \
    --input data/sqpsychconv/qwen-2.5 \
    --checkpoint sqlite:///data/outputs/checkpoint.db \
    --output data/outputs \
    --limit 10
```

### Live Run (With API Calls)

```bash
uv run vibe-check score-corpus \
    --input data/sqpsychconv/qwen-2.5 \
    --checkpoint sqlite:///data/outputs/checkpoint.db \
    --output data/outputs \
    --live
```

### Diagnostics

```bash
uv run vibe-check diagnostics \
    --scored data/outputs/scored.jsonl \
    --strict
```

### Export

```bash
uv run vibe-check export \
    --input data/outputs/scored.jsonl \
    --output-dir data/exports \
    --format jsonl,csv
```
