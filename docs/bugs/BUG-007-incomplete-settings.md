---
severity: P3
status: open
---

# BUG-007: Settings configuration is incomplete

## Summary
`src/vibe_check/settings.py` only includes API keys. It misses the extensive configuration defined in `SPEC-vibe-check.md` Section 11.2, including model IDs, concurrency limits, and retry policies.

## Evidence
- `src/vibe_check/settings.py`: Only `*_api_key` fields exist.
- `docs/research/SPEC-vibe-check.md`: Section 11.2 lists `juror_gpt_model`, `runs_per_model`, `disagreement_range_threshold`, etc.

## Impact
- Hardcoded defaults (if they exist) or missing functionality when we switch to real agents.
- Inability to control costs or model versions via environment variables.

## Fix Plan
1. Update `Settings` class to match the spec (Model IDs, limits, thresholds).
2. Ensure defaults match the "January 2026 Frontier Models" table.
