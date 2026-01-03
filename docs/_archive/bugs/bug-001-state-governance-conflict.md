---
severity: P0
status: reverted
---

# BUG-001: ScoringState violates checkpoint privacy rules

## Summary

The SSOT previously defined LangGraph `ScoringState` with raw `dialogue` / `scoring_text` strings while also prohibiting raw transcript text in the checkpoint DB. LangGraph checkpointers persist the entire state, so this was a direct privacy/governance violation.

## Evidence

- Governance rule: `docs/research/spec-vibe-check.md:145` (checkpoint DB must not contain raw transcript text)
- Conflicting state definition (historical): `docs/research/spec-vibe-check.md:263` (previously included `dialogue` and `scoring_text`)
- Batch map-reduce example (historical): `docs/research/spec-vibe-check.md:403` (previously fanned out `{file_id, dialogue}`)

## Impact

- Any implementation of SPEC-05 as written would have persisted raw transcripts into SQLite/Postgres checkpoints, violating the project’s data governance mandate.
- Increased blast radius if checkpoints are copied, logged, or shared.

## Fix

- Remove all raw dialogue/view text from checkpointed state by construction.
- Nodes must load dialogue views **ephemerally** via `file_id` from a non-persisted store (disk or in-memory cache).

## Resolution

**REVERTED** by `docs/research/spec-revision-synthetic-data-simplification.md`.

SQPsychConv is synthetic data with no PHI. The original constraint was unnecessary "privacy theater". We have restored `dialogue` and `scoring_text` to the `ScoringState` to simplify the architecture (operational hygiene). Checkpointing synthetic text is acceptable.
