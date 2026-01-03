# BUG-012: Fake jury model IDs don't match Settings defaults

**Severity**: P4 (consistency / debugging)
**Status**: RESOLVED
**Date**: 2026-01-03

---

## Summary

`build_fake_jury()` in `factory.py` uses hardcoded model IDs that don't match the Settings defaults, causing confusion when comparing fake runs to real runs.

---

## Affected Areas

- `src/vibe_check/run/factory.py:39`

---

## Current vs Expected

| Provider | Settings Default | Fake Jury Default |
|----------|------------------|-------------------|
| GPT | `gpt-5.2` | `gpt-5.2` |
| Claude | `claude-sonnet-4-5-20250929` | `claude-sonnet` |
| Gemini | `gemini-3-pro-preview` | `gemini-pro` |

---

## Fix Plan

Update `build_fake_jury()` defaults to match Settings:

```python
def build_fake_jury(
    models: list[str] | None = None,
    runs_per_model: int = 2,
) -> Sequence[Juror]:
    if models is None:
        models = ["gpt-5.2", "claude-sonnet-4-5-20250929", "gemini-3-pro-preview"]
    ...
```

Or better: read from Settings if available.

---

## Verification

- Fake run outputs have `model_id` values matching Settings defaults
- Easier to compare/debug fake vs real runs
