---
severity: P2
status: fixed
---

# BUG-004: Evidence snippets are not bounded by length (cost risk)

## Summary

`PHQ8ItemScore.evidence` and `PHQ8Report.self_harm_evidence` are lists of strings. The schemas cap list lengths, but do not constrain the size of each string. A single “evidence” entry could unintentionally contain large transcript chunks, increasing token usage and cost volatility (token bloat).

## Evidence

- Evidence fields exist in schemas: `src/vibe_check/schemas/scoring.py:14`
- Operational hygiene recommends bounded snippets (not full transcript/views): `docs/research/spec-vibe-check.md:145`

## Impact

- Potential leakage of large transcript text into persisted artifacts (bloat).
- Increased token usage and cost volatility.

## Fix Plan

- Add per-snippet validators:
  - `evidence` / `self_harm_evidence` entries must be short (e.g., ≤50 words and/or ≤400 chars).
  - Cap `self_harm_evidence` list length (e.g., 3) for parity with item evidence.
- Add unit tests for validation limits.

## Resolution

- Enforced snippet bounds and `self_harm_evidence` length cap in `src/vibe_check/schemas/scoring.py:14`.
- Added regression tests in `tests/unit/test_schemas_scoring.py:1`.
