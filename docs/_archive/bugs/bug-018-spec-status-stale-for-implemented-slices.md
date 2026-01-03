# BUG-009: SPEC-04/05/06 are implemented but still marked DRAFT

**Severity**: P4 (documentation consistency)
**Status**: RESOLVED
**Date**: 2026-01-03

---

## Summary

Implementation and tests for SPEC-04/05/06 exist and `make ci` passes, but the spec headers still say `**Status**: DRAFT`.

This confuses reviewers and future contributors about what is already shipped.

---

## Fix Plan

- Update:
  - `docs/specs/spec-04-juror-scoring-agent.md`
  - `docs/specs/spec-05-consensus-orchestration.md`
  - `docs/specs/spec-06-batch-runner-and-export.md`

to:

- `**Status**: IMPLEMENTED (YYYY-MM-DD)`
- Add any “small deviations from spec” notes if needed (e.g., naming differences like `jury_results` in state vs `juror_reports` in outputs).

---

## Verification

- Specs reflect the current implementation and test suite.
