---
severity: P2
status: open
opened_date: 2026-01-03
---

# BUG-030: `RUNS_PER_MODEL` > 2 breaks scoring (`PHQ8Report.run_number` is capped at 2)

## Summary
`Settings.runs_per_model` is configurable via environment, but the `PHQ8Report` schema enforces `run_number <= 2`. If a user sets `RUNS_PER_MODEL=3` (or higher), `build_real_jury(...)` will construct jurors with `run_number=3+`, and `JurorScorer` will raise a Pydantic `ValidationError` when building `PHQ8Report`.

## Evidence
- `src/vibe_check/settings.py`
  - `runs_per_model: int = 2` (no upper bound)
- `src/vibe_check/run/factory.py`
  - `for run_no in range(1, settings.runs_per_model + 1): ...`
- `src/vibe_check/schemas/scoring.py`
  - `PHQ8Report.run_number: int = Field(ge=1, le=2, description="Run 1 or 2")`

## Impact
- A documented/configurable knob can hard-crash live scoring and mark every dialogue as failed.
- Prevents experimentation with more than 2 runs per model (even though settings imply it’s supported).

## Repro
```bash
export RUNS_PER_MODEL=3
vibe-check score-corpus ...   # fake or live
```
Expected: 3 runs per model.
Actual: Pydantic `ValidationError` on `PHQ8Report.run_number`.

## Fix Plan
- Decide SSOT:
  - If “2 runs per model” is a hard invariant: enforce it in `Settings` (validation) and in docs; remove configurability.
  - If configurable runs are intended: remove `le=2` constraint from `PHQ8Report.run_number` (keep `ge=1`) and update docs/tests accordingly.
- Add a unit test that sets `RUNS_PER_MODEL=3` and asserts the chosen behavior (reject early vs support).
