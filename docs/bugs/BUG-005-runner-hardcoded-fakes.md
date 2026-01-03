---
severity: P0
status: open
---

# BUG-005: Batch runner is hardcoded to use fake jurors

## Summary
The batch runner implementation (`src/vibe_check/run/runner.py`) explicitly initializes and uses `_default_fake_jury()` in `score_corpus`. There is no logic to initialize real PydanticAI agents or inject them into the graph.

## Evidence
- `src/vibe_check/run/runner.py:75`: `jurors = _default_fake_jury()` is hardcoded.
- `src/vibe_check/cli.py`: No arguments to switch to real mode or configure models.
- `src/vibe_check/run/runner.py:30`: `DeterministicFakeJuror` is defined inline and used as the only implementation.

## Impact
The system cannot perform its primary function (scoring with LLMs). It is currently a mock-only system masquerading as a production runner. This blocks SPEC-06 deliverables.

## Fix Plan
1. Update `score_corpus` to accept a `jurors: Sequence[Juror]` argument (or a factory/config to build them).
2. Implement a `build_real_jury(settings)` factory that creates `Agent` instances for GPT/Claude/Gemini.
3. Update CLI to toggle between `--dry-run` (fakes) and production (real agents).
