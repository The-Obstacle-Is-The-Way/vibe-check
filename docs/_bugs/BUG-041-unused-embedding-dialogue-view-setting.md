# BUG-041: Unused `embedding_dialogue_view` Setting (Dead Code)

| Field | Value |
|-------|-------|
| **Severity** | P3 (Low - Dead Code) |
| **Status** | open |
| **Date** | 2026-01-04 |
| **Component** | `settings.py` |
| **Impact** | Code hygiene, confusion for maintainers |

---

## Summary

The `embedding_dialogue_view` setting in `settings.py` is **never used anywhere in the codebase**. It was added despite the master spec (`docs/_archive/research/spec-vibe-check.md`) explicitly marking embeddings as **OUT OF SCOPE**.

This is a classic example of AI-generated code that ignored explicit scope boundaries.

---

## Evidence

### 1. Spec Says OUT OF SCOPE

From `docs/_archive/research/spec-vibe-check.md`:

```markdown
## SCOPE BOUNDARY (2026-01-02)
| Responsibility | Owner | Notes |
| Embedding generation | **ai-psychiatrist** | NOT here |

> This spec was originally drafted with embedding/transfer phases included.
> Those phases have been moved to `ai-psychiatrist`.
> Any references to embeddings... are **OUT OF SCOPE** for vibe-check.
```

And:

```markdown
### 12.3 Phase 2: Generate Embeddings
> **OUT OF SCOPE**: Embedding generation has been moved to `ai-psychiatrist`.
```

### 2. Setting Exists But Is Unused

`settings.py:43-45`:
```python
embedding_dialogue_view: Literal["client_qa", "client_contextualized", "client_only"] = (
    "client_qa"
)
```

**Grep results** for `embedding_dialogue_view` in `src/`:
- ONLY found in `settings.py` (1 occurrence)
- NO usage in any other code file
- Setting is defined but never read

---

## Root Cause

The LLM that generated the initial codebase copied the setting from the spec's configuration section without checking that:
1. The spec explicitly marked embeddings as OUT OF SCOPE
2. No code would actually use this setting

This is textbook "AI slop" - copying without understanding context.

---

## Impact

- **Low severity**: Dead code that doesn't break anything
- **Confusion risk**: Future maintainers may think embeddings are implemented
- **Tech debt**: Accumulates unused configuration surface area

---

## Fix Options

### Option A: Remove the Setting (Recommended)

Delete the unused setting entirely:

```python
# settings.py - REMOVE THESE LINES:
embedding_dialogue_view: Literal["client_qa", "client_contextualized", "client_only"] = (
    "client_qa"
)
```

Also remove from:
- `docs/reference/settings.md`
- `.env.example` (if present)

### Option B: Mark as Future

If embeddings might be added later, rename to make status clear:

```python
# FUTURE: Move to ai-psychiatrist or implement when needed
# embedding_dialogue_view: Literal[...] = "client_qa"
```

---

## Recommendation

**Remove the setting** (Option A). Reasons:

1. Master spec explicitly says embeddings are handled by `ai-psychiatrist`
2. No implementation exists or is planned
3. If embeddings ARE needed later:
   - They should be in `ai-psychiatrist` per spec
   - OR a new SPEC should be written first
   - The setting can be re-added at that time

---

## Test Plan

1. Remove the setting from `settings.py`
2. Remove documentation references
3. Run `make ci` to verify no breakage
4. Grep codebase to confirm no references remain

---

## Related

- [SPEC-11: PHQ-8 Rubric Embedding](../_specs/SPEC-11-phq8-rubric-embedding.md) (documents design decision)
- [Master Spec](../_archive/research/spec-vibe-check.md) (scope boundary definition)
