# BUG-010: Deterministic fakes rely on `# type: ignore[arg-type]` for PHQ score literals

**Severity**: P4 (type hygiene / strictness)
**Status**: RESOLVED
**Date**: 2026-01-03

---

## Summary

`src/vibe_check/scoring/fakes.py` uses `# type: ignore[arg-type]` to pass dynamically computed integers (0–3) into fields typed as `Literal[0, 1, 2, 3]`.

This is safe at runtime (values are clamped/modded), but it weakens “strict everywhere” typing discipline and makes it easier to hide real type errors.

---

## Affected Areas

- `src/vibe_check/scoring/fakes.py`

---

## Fix Plan

- Replace the `type: ignore` uses with explicit narrowing:
  - `cast(Literal[0, 1, 2, 3], score)`
  - `cast(Literal[0, 1, 2, 3], final)`

Optionally centralize as a shared alias (e.g., `PHQ8Score`).

---

## Verification

- `uv run mypy src tests` passes with zero `type: ignore` usage in the repo.
