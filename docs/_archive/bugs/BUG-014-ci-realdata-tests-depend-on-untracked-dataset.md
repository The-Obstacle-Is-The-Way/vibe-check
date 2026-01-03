# BUG-005: CI depends on untracked SQPsychConv dataset on disk

**Severity**: P0 (blocks clean CI from a fresh clone)
**Status**: RESOLVED
**Date**: 2026-01-03

---

## Summary

Several integration tests hardcode `data/sqpsychconv/qwen-2.5` and assert full-corpus properties (e.g. `len(corpus) == 2090`). The repo explicitly does **not** version `data/sqpsychconv/` (see `.gitignore`), so a fresh clone in GitHub Actions will not have this directory.

Result: `pytest` fails in CI with `FileNotFoundError: data/sqpsychconv/qwen-2.5`.

---

## Affected Areas

- `tests/integration/test_data_pipeline.py`
- `tests/integration/test_batch_runner.py`
- Any local commands that assume the dataset exists on disk without an explicit download step.

---

## Repro (Fresh Clone)

```bash
rm -rf data/sqpsychconv
uv run pytest
```

Expected: test suite passes from a clean checkout.
Actual: integration tests raise `FileNotFoundError`.

---

## Root Cause

- The project correctly avoids committing the dataset (license unclear + size).
- Tests are written as if the dataset is always present on disk at a fixed path.
- CI does not download/cache the dataset prior to running tests.

---

## Fix Plan (Preferred)

1. Make CI-fast tests self-contained:
   - Create a tiny HuggingFace `DatasetDict` in tests, `save_to_disk(tmp_path)`, and run the integration slice against that directory.
2. Keep optional “real dataset” validation tests:
   - If `data/sqpsychconv/qwen-2.5` exists locally, run additional assertions (counts/distribution).
   - Otherwise skip with a clear message.

This preserves the “no mocks” principle while keeping CI deterministic and not dependent on external downloads.

---

## Verification

- `uv run pytest` passes with `data/sqpsychconv/` absent.
- Optional real-data tests run (and pass) when the dataset is present locally.
