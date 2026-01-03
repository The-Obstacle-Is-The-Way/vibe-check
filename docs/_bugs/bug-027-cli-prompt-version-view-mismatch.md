---
severity: P1
status: resolved
opened_date: 2026-01-03
resolved_date: 2026-01-03
---

# BUG-027: CLI `--prompt-version` / `--dialogue-view` can desync from live agent prompts

## Summary
In `--live` runs, the CLI exposes `--prompt-version` and `--dialogue-view`, but the **live juror/judge agents** were built using `Settings.prompt_version` and `Settings.scoring_dialogue_view`. This produced runs where:

- The **scored outputs** recorded `prompt_version` and `dialogue_view` from CLI args
- The **actual LLM system prompts** embedded different `prompt_version` / `view_name` values (from environment-backed `Settings`)

This was a reproducibility and correctness footgun.

## Evidence
- `src/vibe_check/cli.py`
  - Defines `--prompt-version` and `--dialogue-view` flags for `score-corpus`
  - Passes `prompt_version=args.prompt_version` and `dialogue_view=args.dialogue_view` into `score_corpus(...)`
- `src/vibe_check/run/runner.py`
  - Uses `dialogue_view` to select `scoring_text` (`client_qa` vs `client_only`)
  - Persists `row[\"dialogue_view\"] = dialogue_view` and `row[\"scoring_text\"] = scoring_text`
- `src/vibe_check/run/factory.py`
  - Builds real juror agents with `prompt_version=settings.prompt_version` and `view_name=settings.scoring_dialogue_view`
  - Builds the judge agent with `prompt_version=settings.prompt_version`
- `src/vibe_check/graph/single_dialogue.py`
  - Passes `state[\"prompt_version\"]` into `judge_item(...)`, but the real judge implementation ignores its `prompt_version` argument

## Impact
- **Reproducibility**: `AggregatedPHQ8.prompt_version` can differ from the prompt version actually used to score/judge.
- **Prompt correctness**: A juror prompt can state it is scoring view `client_qa` while receiving `client_only` text (or vice versa).
- **Auditability**: Run artifacts become ambiguous about which prompt template/view was truly used.

## Resolution

**Fixed via Option 1**: Propagate CLI flags into live agent construction.

### Changes Made:
1. **`src/vibe_check/run/factory.py`**:
   - `build_real_jury(settings)` → `build_real_jury(settings, *, prompt_version: str, dialogue_view: str)`
   - `build_real_judge_item(settings)` → `build_real_judge_item(settings, *, prompt_version: str)`
   - Both now use the passed params instead of `settings.prompt_version` / `settings.scoring_dialogue_view`

2. **`src/vibe_check/cli.py`**:
   - Updated to pass `args.prompt_version` and `args.dialogue_view` to factory functions

3. **`tests/unit/test_factory.py`**:
   - Added tests to verify CLI args flow through to agent construction
   - Added tests to verify params are required (no silent fallback to Settings)

### Verification:
- All 95 unit tests pass
- All 12 integration tests pass
- Linting passes
