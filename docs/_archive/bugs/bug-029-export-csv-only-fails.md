---
severity: P2
status: resolved
opened_date: 2026-01-03
resolved_date: 2026-01-03
---

# BUG-029: `vibe-check export --format csv` fails (JSONL validation runs unconditionally)

## Summary
`write_label_exports(...)` supports selecting output formats (e.g. `csv` only), but it always calls `validate_label_export(jsonl_path)` even when `jsonl` was not requested and the JSONL file was never written. This causes a `FileNotFoundError` for `--format csv`.

## Evidence
- `src/vibe_check/export/writer.py`
  - Only writes `vibe_check_labels.jsonl` when `"jsonl" in formats`
  - Always runs `validation = validate_label_export(jsonl_path)` afterward
- `src/vibe_check/cli.py`
  - Exposes `vibe-check export --format` as a comma-separated list (implying `csv`-only should work)

## Impact
- CLI contract violation: `--format csv` is accepted but crashes.
- Downstream automation cannot rely on `csv`-only exports.

## Repro
```bash
vibe-check export --input path/to/scored.jsonl --output-dir out --format csv
```
Expected: `vibe_check_labels.csv` is written.
Actual: `FileNotFoundError` for `out/vibe_check_labels.jsonl`.

## Fix Plan
Resolved by:
- Always writing `vibe_check_labels.jsonl` (canonical contract) and validating it.
- Treating `csv` as an optional additional output.
- Adding an integration test for `--format csv` to prevent regressions.
