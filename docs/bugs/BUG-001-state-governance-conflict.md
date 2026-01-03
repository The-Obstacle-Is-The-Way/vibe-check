---
severity: P0
status: fixed
---

# BUG-001: ScoringState violates checkpoint privacy rules

## Summary

The SSOT previously defined LangGraph `ScoringState` with raw `dialogue` / `scoring_text` strings while also prohibiting raw transcript text in the checkpoint DB. LangGraph checkpointers persist the entire state, so this was a direct privacy/governance violation.

## Evidence

- Governance rule: `docs/research/SPEC-vibe-check.md:145` (checkpoint DB must not contain raw transcript text)
- Conflicting state definition (historical): `docs/research/SPEC-vibe-check.md:263` (previously included `dialogue` and `scoring_text`)
- Batch map-reduce example (historical): `docs/research/SPEC-vibe-check.md:403` (previously fanned out `{file_id, dialogue}`)

## Impact

- Any implementation of SPEC-05 as written would have persisted raw transcripts into SQLite/Postgres checkpoints, violating the project’s data governance mandate.
- Increased blast radius if checkpoints are copied, logged, or shared.

## Fix

- Remove all raw dialogue/view text from checkpointed state by construction.
- Nodes must load dialogue views **ephemerally** via `file_id` from a non-persisted store (disk or in-memory cache).

## Resolution

Fixed by updating SSOT and SPEC-05 to:

- Remove `dialogue` / `scoring_text` from `ScoringState`
- Fan-out by `file_id` only in batch examples
- Explicitly document that LangGraph persists full state and state must exclude transcript strings
