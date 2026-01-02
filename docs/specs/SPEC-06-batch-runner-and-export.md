# SPEC-06: Batch Runner & Export (Corpus-Scale Labeling)

**Status**: DRAFT (2026-01-02)
**Slice Type**: Vertical (Full Corpus → Outputs on Disk)
**Dependencies**: SPEC-02 (Data Pipeline), SPEC-05 (Consensus Orchestration)
**Estimated Scope**: ~600 lines of code, ~400 lines of tests

---

## 1. Objective

Implement the corpus-scale runner that:

1. Loads SQPsychConv (2,090 dialogues) via SPEC-02
2. Scores each dialogue via the SPEC-05 graph (jury → aggregate → judge as needed)
3. Writes outputs incrementally to `data/outputs/` (safe to resume)
4. Maintains a job-level ledger (status/attempts/errors) without storing transcript text
5. Produces a run manifest with aggregate diagnostics (arbitration rate, entropy distribution, per-condition summaries)

### Success Criteria

```bash
# Dry-run a small subset (no network calls when using fake clients)
uv run python -m vibe_check.cli score-corpus \
  --input data/sqpsychconv/qwq \
  --limit 5 \
  --checkpoint sqlite:///data/checkpoints/dev.db \
  --output data/outputs/dev_run/

# Outputs exist and are deterministic
test -f data/outputs/dev_run/scored.jsonl
test -f data/outputs/dev_run/run_manifest.json
```

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

### 3.1 scored.jsonl

One JSON object per dialogue, including:

- `file_id`, `condition`, `computed_split`
- `prompt_version`, `dialogue_view` (e.g., `client_qa`)
- Final labels (`final_item_scores`, `final_total_score`, severity bucket)
- Audit fields:
  - arbitration metadata
  - juror model IDs and run numbers
  - judge resolutions (no transcript text)

### 3.2 run_manifest.json

Aggregate diagnostics (no transcript text), e.g.:

- counts by split and condition
- arbitration rate overall + per item
- distribution summaries (entropy/max-prob, total CI width)
- failure counts by error code (rate_limit, parse_error, provider_error)

---

## 4. Concurrency, Retries, and Determinism

### 4.1 Concurrency

- Concurrency must be configurable and default conservative
- Must respect provider rate limits (global and per-provider)

### 4.2 Retries (Bounded)

- Use bounded retries with exponential backoff
- No “retry until it parses” loops
- Persist failures in the ledger with error codes and timestamps

### 4.3 Determinism

- Split assignment stays deterministic (SPEC-02 SHA256-based)
- Output ordering is deterministic (sort by `file_id` when exporting)
- Never use Python’s `hash()` for anything that impacts persisted results

---

## 5. Testing Strategy

### 5.1 Unit Tests

- Ledger CRUD: status transitions are valid and idempotent
- Export writer: deterministic ordering + atomic writes (write temp then rename)
- CLI arg parsing: defaults, required args, and validation

### 5.2 Integration Tests (Deterministic)

Using fake jurors/judge:

- Run scoring on `N=5` real dialogues from `data/sqpsychconv/qwq`
- Assert output files created and contain N rows
- Assert resume works (run twice; second run does no extra work)

### 5.3 E2E (Optional, Off by Default)

- Run `N=1` with real provider keys
- Assert end-to-end produces a parseable output row

---

## 6. Non-Goals

- Transfer evaluation against DAIC-WOZ (future spec; restricted dataset)
- Producing or publishing embeddings until SQPsychConv license is confirmed
