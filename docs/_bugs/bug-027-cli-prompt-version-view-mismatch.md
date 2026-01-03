---
severity: P1
status: open
opened_date: 2026-01-03
---

# BUG-027: CLI `--prompt-version` / `--dialogue-view` can desync from live agent prompts

## Summary
In `--live` runs, the CLI exposes `--prompt-version` and `--dialogue-view`, but the **live juror/judge agents** are built using `Settings.prompt_version` and `Settings.scoring_dialogue_view`. This can produce runs where:

- The **scored outputs** record `prompt_version` and `dialogue_view` from CLI args
- The **actual LLM system prompts** embed different `prompt_version` / `view_name` values (from environment-backed `Settings`)

This is a reproducibility and correctness footgun.

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

## Fix Plan
Make `prompt_version` and `dialogue_view` single-source-of-truth in live mode.

Options (choose one):
1. **Propagate CLI flags into live agent construction**
   - Thread `prompt_version` and `dialogue_view` through `build_real_jury(...)` / `build_real_judge_item(...)` and use them when building prompts.
2. **Hard fail on mismatch**
   - If `--dialogue-view != Settings.scoring_dialogue_view` or `--prompt-version != Settings.prompt_version`, raise a clear error.
3. **Remove misleading knobs**
   - If `--prompt-version` is intended as a label only, rename it to `--output-prompt-version` (and persist separate fields).

## Notes
Docs were updated to reflect the current behavior (CLI flags do not override prompt template selection), but the underlying mismatch remains in code.
