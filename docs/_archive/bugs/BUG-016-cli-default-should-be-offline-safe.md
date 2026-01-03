# BUG-007: CLI default mode is not offline-safe (risk of accidental paid API calls)

**Severity**: P1 (safety/cost footgun)
**Status**: RESOLVED
**Date**: 2026-01-03

---

## Summary

The CLI previously defaulted to using real provider-backed jurors/judge unless an explicit dry-run flag was passed. This is a cost/safety footgun:

- A user can run the example command from specs and accidentally trigger paid API calls.
- In environments with keys set, this can silently spend money.
- In environments without keys, it fails in a confusing way.

SPEC-06 states the reference implementation should default to deterministic fakes so CI and local runs are offline by default.

---

## Affected Areas

- `src/vibe_check/cli.py`
- `docs/specs/SPEC-06-batch-runner-and-export.md` (examples imply offline defaults)

---

## Fix Plan

- Replace the dry-run toggle with an explicit opt-in flag (`--live`).
- Default behavior (no flag) uses deterministic fake jury/judge (offline).
- Update docs/tests accordingly.

---

## Verification

- Running `vibe-check score-corpus ...` without flags performs an offline fake run.
- Running with `--live` requires keys and uses real providers.
