# CLI Reference

Complete reference for vibe-check command-line interface.

---

## Usage

```bash
vibe-check <command> [options]
```

---

## Commands

### score-corpus

Score a SQPsychConv corpus and write outputs.

```bash
vibe-check score-corpus \
    --input <path> \
    --checkpoint <path> \
    --output <path> \
    [options]
```

#### Required Arguments

| Argument | Description |
|----------|-------------|
| `--input` | Path to HuggingFace dataset directory or CSV file |
| `--checkpoint` | SQLite checkpoint database path (e.g., `sqlite:///path/to/db`) |
| `--output` | Output directory for scored.jsonl and manifest |

#### Optional Arguments

| Argument | Default | Description |
|----------|---------|-------------|
| `--live` | False | Use real LLM APIs (costs money) |
| `--limit` | None | Limit number of dialogues (for debugging) |
| `--prompt-version` | `v2.0.0-clinical` | Prompt version label embedded in outputs |
| `--dialogue-view` | `client_qa` | View to use: `client_qa` or `client_only` |
| `--max-concurrency` | 50 | Max concurrent dialogue processing |
| `--force` | False | Reset existing run if config differs (see below) |

**Note**: `--live` runs require `--prompt-version` starting with `v2` (NA-aware schema).

#### Config Mismatch Protection

When resuming a run, vibe-check validates that the current configuration matches the original run (via SHA256 fingerprint stored in `ledger.sqlite`). If configurations differ, the run fails with:

```
ValueError: run configuration mismatch (use a new --output/--checkpoint or pass --force to reset)
```

**Options:**
- Use a different `--output` and `--checkpoint` path for the new config
- Pass `--force` to reset the existing run directory and start fresh

#### Examples

```bash
# Dry run with fake jurors
vibe-check score-corpus \
    --input data/sqpsychconv/qwen-2.5 \
    --checkpoint sqlite:///data/outputs/checkpoint.db \
    --output data/outputs \
    --limit 10

# Production run with real APIs
vibe-check score-corpus \
    --input data/sqpsychconv/qwen-2.5 \
    --checkpoint sqlite:///data/outputs/checkpoint.db \
    --output data/outputs \
    --live \
    --prompt-version v2.0.0-clinical
```

#### Output Files

| File | Description |
|------|-------------|
| `scored.jsonl` | One AggregatedPHQ8 per line (final output) |
| `run_manifest.json` | Run metadata, counts, and token usage totals |
| `ledger.sqlite` | Processing ledger tracking job statuses |
| `rows/` | Individual row JSON files (intermediate outputs) |
| `checkpoint.db` | LangGraph checkpoints (at checkpoint path) |

---

### diagnostics

Compute run diagnostics from scored.jsonl.

```bash
vibe-check diagnostics \
    --scored <path> \
    --output <path> \
    [options]
```

#### Required Arguments

| Argument | Description |
|----------|-------------|
| `--scored` | Path to scored.jsonl file |
| `--output` | Path to write diagnostic report |

#### Optional Arguments

| Argument | Default | Description |
|----------|---------|-------------|
| `--format` | `json` | Output format: `json` or `markdown` |
| `--strict` | False | Exit non-zero if any quality gate fails |

#### Examples

```bash
# JSON output
vibe-check diagnostics \
    --scored data/outputs/scored.jsonl \
    --output data/outputs/diagnostics.json

# Markdown with strict mode
vibe-check diagnostics \
    --scored data/outputs/scored.jsonl \
    --output data/outputs/diagnostics.md \
    --format markdown \
    --strict
```

#### Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success (all gates pass) |
| 2 | Gate failure (with `--strict`) |

---

### export

Export public label files from scored.jsonl.

```bash
vibe-check export \
    --input <path> \
    --output-dir <path> \
    [options]
```

#### Required Arguments

| Argument | Description |
|----------|-------------|
| `--input` | Path to internal scored.jsonl |
| `--output-dir` | Directory to write export files |

#### Optional Arguments

| Argument | Default | Description |
|----------|---------|-------------|
| `--format` | `jsonl,csv` | Comma-separated formats: `jsonl`, `csv` |

#### Examples

```bash
# Both formats
vibe-check export \
    --input data/outputs/scored.jsonl \
    --output-dir data/exports

# JSONL only
vibe-check export \
    --input data/outputs/scored.jsonl \
    --output-dir data/exports \
    --format jsonl
```

#### Output Files

| File | Description |
|------|-------------|
| `vibe_check_labels.jsonl` | JSONL export (always written) |
| `vibe_check_labels.csv` | CSV export (if format includes csv) |

---

### validate-export

Validate a public export JSONL file.

```bash
vibe-check validate-export --input <path>
```

#### Required Arguments

| Argument | Description |
|----------|-------------|
| `--input` | Path to vibe_check_labels.jsonl |

#### Examples

```bash
vibe-check validate-export \
    --input data/exports/vibe_check_labels.jsonl
```

#### Output Files

| File | Description |
|------|-------------|
| `validation_report.json` | Validation results (written next to input) |

#### Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Validation passed |
| 2 | Validation failed |

---

### calibration

Human-in-the-loop calibration utilities (optional; see SPEC-09).

#### calibration sample

Sample dialogue IDs from a completed run for manual annotation.

```bash
vibe-check calibration sample \
    --scored <path> \
    --n <int> \
    --seed <int> \
    --output <path>
```

| Argument | Description |
|----------|-------------|
| `--scored` | Path to `scored.jsonl` |
| `--n` | Number of dialogues to sample |
| `--seed` | Deterministic sampling seed |
| `--output` | Path to write the CSV template |

#### calibration evaluate

Compute agreement metrics between system outputs and a filled human CSV.

```bash
vibe-check calibration evaluate \
    --system <path> \
    --human <path> \
    --output <path>
```

| Argument | Description |
|----------|-------------|
| `--system` | Path to system `scored.jsonl` |
| `--human` | Path to filled `golden_set.csv` |
| `--output` | Path to write `calibration_report.json` |

**Exit Codes**

| Code | Meaning |
|------|---------|
| 0 | Success |
| 2 | Safety gate failure (e.g., self-harm recall < 1.0 when evaluable) |

---

## Global Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | General error |
| 2 | Validation/gate failure |

---

## Environment Variables

The CLI respects environment variables from `.env`:

```bash
# API keys
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GOOGLE_API_KEY=...

# Settings override
MAX_CONCURRENT_DIALOGUES=50
```

See [Settings](settings.md) for all environment variables.
