# vibe-check
Multi-agent PHQ-8 scoring for synthetic therapeutic dialogues.

[![CI](https://github.com/The-Obstacle-Is-The-Way/vibe-check/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/The-Obstacle-Is-The-Way/vibe-check/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/The-Obstacle-Is-The-Way/vibe-check/branch/main/graph/badge.svg)](https://codecov.io/gh/The-Obstacle-Is-The-Way/vibe-check)
[![License: Apache-2.0](https://img.shields.io/github/license/The-Obstacle-Is-The-Way/vibe-check)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12-blue)](pyproject.toml)

## What It Does

vibe-check takes a corpus of synthetic therapy dialogues and produces:

- A **jury** of LLM jurors scoring PHQ-8 items independently (default: 3 models × 2 runs = 6 jurors)
- **Bayesian aggregation** of juror votes (Dirichlet posteriors + convolution for total-score distribution)
- Optional **judge arbitration** for contested items
- Run artifacts (`scored.jsonl`, `rows/`, `ledger.sqlite`, `run_manifest.json`) plus public exports (JSONL/CSV)

This project is for research on synthetic data and is **not a clinical tool**.

## Quickstart

Prereqs: Python 3.11+ and `uv`.

```bash
make dev

# Offline-safe run (deterministic fakes; no API keys required)
uv run vibe-check score-corpus \
  --input data/sqpsychconv/qwen-2.5 \
  --checkpoint sqlite:///data/checkpoints/vibe_check.db \
  --output data/outputs/example \
  --limit 5

uv run vibe-check diagnostics \
  --scored data/outputs/example/scored.jsonl \
  --output data/outputs/example/diagnostics.json

uv run vibe-check export \
  --input data/outputs/example/scored.jsonl \
  --output-dir data/outputs/example/exports \
  --format jsonl,csv
```

For live runs (real provider-backed jurors/judge; costs money), set API keys and add `--live`:

```bash
export OPENAI_API_KEY=...
export ANTHROPIC_API_KEY=...
export GOOGLE_API_KEY=...  # or GEMINI_API_KEY=...

uv run vibe-check score-corpus ... --live
```

## Outputs

After `score-corpus`, the `--output` directory contains:

- `rows/{file_id}.json`: per-dialogue structured output (written atomically)
- `scored.jsonl`: materialized JSONL (sorted by `file_id`)
- `ledger.sqlite`: job ledger (done/running/failed) + token totals
- `run_manifest.json`: run metadata, counts, and token usage totals

## Docs

- `docs/index.md` (start here)
- Guides: `docs/guides/index.md`
- Scoring pipeline: `docs/scoring/index.md`
- Architecture: `docs/architecture/index.md`
- Reference (CLI, schemas, settings, thresholds): `docs/reference/index.md`

## Development

Prereqs: Python 3.11+ and `uv`.

- Setup: `make dev`
- Run all local gates: `make ci`
