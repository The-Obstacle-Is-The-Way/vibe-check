# BUG-052: Live Run Breaks With NA-Aware Schema (Judge + Prompt Defaults)

| Field | Value |
|-------|-------|
| **Severity** | P0 (Critical) |
| **Status** | resolved |
| **Date** | 2026-01-07 |
| **Component** | `run/factory.py`, `judge/agent.py`, `cli.py`, `settings.py` |
| **Impact** | Live runs crash or produce invalid outputs; judge cannot represent `not_mentioned` |

---

## Summary

The NA-aware schema (SPEC-13 / SSOT §12.1) introduced `score=null` (`assertion="not_mentioned"`) and assertion semantics for both jurors and judge. However, the live pipeline still used legacy (v1) judge wiring and legacy default prompt versions, creating two critical failure modes:

1. **Runtime crash in live arbitration**: the live judge input builder attempted `int(item_score.score)` and crashes when `score=None`.
2. **Invalid live scoring by default**: CLI + Settings defaults were `--prompt-version v1.0.0`, which routes to legacy prompts that do not instruct the NA-aware JSON schema (missing `discussed`, `assertion`, and `score:null` semantics).

---

## Root Cause

- `src/vibe_check/run/factory.py` (live judge) still used:
  - v1 judge agent output schema (`JudgeItemResolution`) which cannot express `final_score=null`
  - v1 judge item prompt builder (no NA votes / assertions)
  - `int(item_score.score)` (crashes for NA votes)
- CLI and Settings defaults still pointed to `v1.0.0`, allowing `--live` runs to proceed with legacy prompts that are schema-incompatible with SPEC-13.

---

## Fix

- Added NA-aware judge agent builder:
  - `src/vibe_check/judge/agent.py`: `build_judge_agent_v2()` (output type `JudgeItemResolutionNA`, v2 system prompt)
- Hardened live factories to be NA-aware and v2-only:
  - `src/vibe_check/run/factory.py`: `build_real_jury()` and `build_real_judge_item()` now require `prompt_version.startswith("v2")`
  - `src/vibe_check/run/factory.py`: live judge now uses v2 judge prompts + NA schema and handles `score=None`
- Made safe defaults and prevented accidental live v1 runs:
  - `src/vibe_check/cli.py`: default `--prompt-version` set to `v2.0.0-clinical`
  - `src/vibe_check/cli.py`: `--live` explicitly rejects non-`v2.*` prompt versions
  - `src/vibe_check/settings.py`: default `prompt_version` set to `v2.0.0-clinical`
- Added regression tests:
  - `tests/unit/test_factory.py`: v2-only guards for live jurors/judge
  - `tests/unit/test_judge.py`: v2 judge agent accepts `not_mentioned` / `final_score=null`

---

## Prevention

- Keep live-only invariants enforced at the factory/CLI boundary (fail fast).
- Add at least one NA-path integration test whenever schema introduces `None` states on previously-int-only fields.
