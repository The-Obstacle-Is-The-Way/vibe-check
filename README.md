# vibe-check
Multi-agent PHQ-8 scoring for synthetic therapy dialogues.

[![CI](https://github.com/The-Obstacle-Is-The-Way/vibe-check/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/The-Obstacle-Is-The-Way/vibe-check/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/The-Obstacle-Is-The-Way/vibe-check/branch/main/graph/badge.svg)](https://codecov.io/gh/The-Obstacle-Is-The-Way/vibe-check)
[![License: Apache-2.0](https://img.shields.io/github/license/The-Obstacle-Is-The-Way/vibe-check)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12-blue)](pyproject.toml)

## Why this exists (first principles)

If you want to study or evaluate synthetic “therapy-style” conversations, you need labels you can trust:
consistent, reproducible, and measurable. vibe-check produces PHQ-8 labels from synthetic dialogues using a
multi-agent “jury” (diverse models + multiple runs) and then quantifies whether the run is stable with quality
gates (reliability, consistency, separation, arbitration rate).

This is research tooling. It is **not a clinical tool** and should not be used for real patient data.

## What it does

Given a corpus of dialogues, vibe-check produces:

- A **jury** of LLM jurors scoring PHQ-8 items independently (default: 3 models × 2 runs = 6 jurors)
- **Bayesian aggregation** of juror votes (Dirichlet posteriors + convolution for total-score distribution)
- Optional **judge arbitration** for contested items
- Run artifacts (`scored.jsonl`, `rows/`, `ledger.sqlite`, `run_manifest.json`) plus public exports (JSONL/CSV)

PHQ-8 is used (8 items × 0–3, total 0–24; not PHQ-9). Self-harm is not scored as an item, but the system does
propagate a `mentions_self_harm` flag + evidence snippets for safety auditing.

## Key guarantees

- **Deterministic preprocessing + splits**: each dialogue gets a stable `computed_split` from `sha256(file_id)`.
- **Resumable runs**: LangGraph checkpointing + a SQLite job ledger prevent re-scoring completed dialogues.
- **No silent fallbacks**: strict schema validation, explicit errors for missing required fields, and `--strict`
  diagnostics mode to fail CI when quality gates fail.
- **Cost visibility**: token usage is tracked per dialogue and aggregated in `ledger.sqlite`/`run_manifest.json`.

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

Add `--strict` to `diagnostics` to exit non-zero if any quality gate fails (useful in CI). For meaningful
diagnostics, run on a larger sample with at least 2 dialogues per condition.

For live runs (real provider-backed jurors/judge; costs money), set API keys and add `--live`:

```bash
export OPENAI_API_KEY=...
export ANTHROPIC_API_KEY=...
export GOOGLE_API_KEY=...  # or GEMINI_API_KEY=...

uv run vibe-check score-corpus ... --live
```

## Input format

`score-corpus --input` accepts either:

- A HuggingFace `save_to_disk()` dataset directory (e.g. `data/sqpsychconv/qwen-2.5/`), or
- A CSV file (or a directory containing exactly one `.csv`) with at least:
  - `file_id` (unique string)
  - `condition` (`mdd` or `control`)
  - `dialogue` (raw transcript text)

## Outputs

After `score-corpus`, the `--output` directory contains:

- `rows/{file_id}.json`: per-dialogue structured output (written atomically)
- `scored.jsonl`: materialized JSONL (sorted by `file_id`)
- `ledger.sqlite`: job ledger (done/running/failed) + token totals
- `run_manifest.json`: run metadata, counts, and token usage totals

The `export` command writes `vibe_check_labels.jsonl` (always), optional `vibe_check_labels.csv`, and a
`validation_report.json`. Export requires `dialogue_view=client_qa` (the default scoring view).

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
