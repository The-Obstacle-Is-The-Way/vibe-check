---
severity: P0
status: fixed
fixed_date: 2026-01-02
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

## Resolution (2026-01-02)

Fixed via dependency injection:

1. **`src/vibe_check/run/runner.py`**: Added `dry_run`, `jurors`, and `judge_item` parameters to `score_corpus()`. When `dry_run=False` (default), builds real jurors from Settings.

2. **`src/vibe_check/run/factory.py`** (new): Factory functions:
   - `build_real_jury(settings, prompt_version)` → Creates 6 `JurorScorer` instances
   - `build_real_judge_item(settings, prompt_version)` → Creates judge function
   - `build_fake_jury()` → Returns deterministic fakes for CI
   - `build_fake_judge_item()` → Returns deterministic fake judge

3. **`src/vibe_check/settings.py`**: Added full SSOT config (model IDs, thresholds, rate limits).

4. **`src/vibe_check/cli.py`**: Added `--dry-run` flag.

5. **`src/vibe_check/judge/agent.py`** (new): `build_judge_agent()` for real judge.

Usage:
```bash
# Real scoring (requires API keys in .env)
uv run python -m vibe_check.cli score-corpus --input data/sqpsychconv/qwq --output data/outputs/run --checkpoint sqlite:///data/checkpoints/run.db

# Dry-run (deterministic fakes, no API calls)
uv run python -m vibe_check.cli score-corpus --input data/sqpsychconv/qwq --output data/outputs/run --checkpoint sqlite:///data/checkpoints/run.db --dry-run
```
