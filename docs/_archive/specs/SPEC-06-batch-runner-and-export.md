# SPEC-06: Batch Runner & Export (Corpus-Scale Labeling)

**Status**: IMPLEMENTED (2026-01-03)
**Slice Type**: Vertical (Full Corpus → Outputs on Disk)
**Dependencies**: SPEC-02 (Data Pipeline), SPEC-05 (Consensus Orchestration)
**Estimated Scope**: ~600 lines of code, ~400 lines of tests

---

## 1. Objective

Implement the corpus-scale runner that:

1. Loads SQPsychConv (2,090 dialogues) via SPEC-02
2. Scores each dialogue via the SPEC-05 graph (jury → aggregate → judge as needed)
3. Writes outputs incrementally to `data/outputs/` (safe to resume)
4. Maintains a job-level ledger (status/attempts/errors) - lightweight, no massive text blobs
5. Produces a run manifest with aggregate diagnostics (arbitration rate, entropy distribution, per-condition summaries)
6. Tracks token usage (incl. reasoning tokens when available) to validate SSOT cost assumptions

### Success Criteria

```bash
# Dry-run a small subset (no network calls when using fake clients)
uv run python -m vibe_check.cli score-corpus \
  --input data/sqpsychconv/qwen-2.5 \
  --limit 5 \
  --checkpoint sqlite:///data/checkpoints/dev.db \
  --output data/outputs/dev_run/

# Outputs exist and are deterministic
test -f data/outputs/dev_run/scored.jsonl
test -f data/outputs/dev_run/run_manifest.json
```

Note: The reference implementation defaults to a deterministic fake jury/judge (offline) so CI and local runs never require API keys. Use `--live` to opt into real providers.

Checkpoint note: accept either a raw SQLite file path or SQLAlchemy-style `sqlite:///...` and normalize internally.
Implementation detail: the batch runner uses LangGraph's async checkpoint interface (`AsyncSqliteSaver`) because the scoring graph runs through async juror calls.

---

## 2. Deliverables

### 2.1 New Source Files

| File | Purpose |
|------|---------|
| `src/vibe_check/cli.py` | CLI entrypoint (score, resume, export) |
| `src/vibe_check/run/config.py` | Runtime config (models, limits, view selection) |
| `src/vibe_check/run/runner.py` | Async batch runner + concurrency controls |
| `src/vibe_check/run/ledger.py` | SQLite job ledger (file_id/status/errors only) |
| `src/vibe_check/run/export.py` | JSONL export + manifest writing |

### 2.2 New Script Entrypoints (Optional)

| File | Purpose |
|------|---------|
| `scripts/score_corpus.py` | Convenience wrapper for CLI |
| `scripts/summarize_run.py` | Summarize outputs without loading transcripts |

### 2.3 pyproject.toml Updates

- Add `[project.scripts] vibe-check = "vibe_check.cli:main"`
- Add runtime deps required by SPEC-05/06 (LangGraph, etc.)

---

## 3. Output Format (SSOT)

### 3.1 scored.jsonl (Internal SSOT)

One JSON object per dialogue, matching the `AggregatedPHQ8` schema (full fidelity). This is the "raw" output used for diagnostics and checkpoints.

Includes:
- `file_id`, `condition`, `computed_split`
- `prompt_version`, `dialogue_view`
- `scoring_text` (exact view text used for scoring; required for SPEC-08 export)
- `juror_reports` (full vote history + evidence)
- `judge_resolution`
- `total_posterior` (distributional data)
- `usage` (per-juror token counts)

> **Note**: This file is the input for SPEC-07 (Diagnostics) and SPEC-08 (Export).

### 3.2 run_manifest.json

Aggregate diagnostics (metrics only), e.g.:

- counts by split and condition
- arbitration rate overall + per item
- distribution summaries (entropy/max-prob, total CI width)
- **Token Usage Totals**: Must account for *all* items in the corpus, even if the run was resumed.
  - *Implementation Detail*: The runner must either persist running totals in the ledger OR re-scan existing rows in `data/outputs/rows/` during initialization to reconstruct the baseline usage count.
- failure counts by error code (rate_limit, parse_error, provider_error)

---

## 4. Concurrency, Retries, and Determinism

See also: **ADR-001** (`docs/architecture/ADR-001-rate-limiting-retries.md`) for full design rationale.

### 4.1 Concurrency

- Concurrency must be configurable and default conservative (`max_concurrent_dialogues=50`)
- Implementation: `score_corpus_async()` uses an `asyncio.TaskGroup` worker pool to score up to `max_concurrency` dialogues concurrently
- Must respect provider rate limits (global and per-provider)
- **Implementation**: `ProviderRateLimiters` in `resilience.py` wraps each provider with `aiolimiter.AsyncLimiter`

### 4.2 Rate Limiting (Layer 3 - Proactive)

Per-provider rate limiters prevent 429 errors before they happen:

```python
# Settings defaults
openai_rpm: int = 100
anthropic_rpm: int = 60
google_rpm: int = 100
```

### 4.3 Retries (Layer 2 - Reactive)

Bounded retries with exponential backoff + jitter (via `tenacity`):

```python
# Settings defaults
max_retries: int = 5
retry_initial_wait: float = 1.0  # seconds
retry_max_wait: float = 60.0     # seconds
retry_jitter: float = 5.0        # seconds
```

Retry conditions:
- HTTP 429 (rate limit)
- HTTP 5xx (server errors)
- Network/connection errors
- Timeouts

**NOT retried**: Validation errors (handled by PydanticAI Layer 1).

### 4.4 Determinism

- Split assignment stays deterministic (SPEC-02 SHA256-based)
- Output ordering is deterministic (sort by `file_id` when exporting)
- Never use Python's `hash()` for anything that impacts persisted results
- Checkpoint state includes full context (dialogue text) for debugging (see SSOT 3.3)

---

## 5. Testing Strategy

### 5.1 Unit Tests

- Ledger CRUD: status transitions are valid and idempotent
- Export writer: deterministic ordering + atomic writes (write temp then rename)
- CLI arg parsing: defaults, required args, and validation

### 5.2 Integration Tests (Deterministic)

Using fake jurors/judge:

- Run scoring on `N=5` real dialogues from `data/sqpsychconv/qwen-2.5`
- Assert output files created and contain N rows
- Assert resume works (run twice; second run does no extra work)

### 5.3 E2E (Optional, Off by Default)

- Run `N=1` with real provider keys
- Assert end-to-end produces a parseable output row

---

## 6. Non-Goals

- Transfer evaluation (happens in `ai-psychiatrist`, NOT vibe-check)
- Embedding generation (happens in `ai-psychiatrist`, NOT vibe-check)

> **CRITICAL: vibe-check NEVER touches real clinical data.** See SPEC-08 for export contract.
