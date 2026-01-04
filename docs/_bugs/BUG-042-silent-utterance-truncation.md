# BUG-042: Silent Utterance Truncation in Preprocessing

| Field | Value |
|-------|-------|
| **Severity** | P2 (Medium - Data Loss Risk) |
| **Status** | open |
| **Date** | 2026-01-04 |
| **Component** | `preprocessing/extractor.py` |
| **Impact** | Undetected data loss, scoring on incomplete dialogues |

---

## Summary

The `_sanitize_utterance_text()` function silently drops utterances that exceed length thresholds (>4000 chars or >200 words). This data loss is hidden behind a generic `had_unknown` flag that conflates multiple unrelated conditions.

---

## Code Location

`src/vibe_check/preprocessing/extractor.py:88-89`:

```python
if len(cleaned) > 4000 or _word_count(cleaned) > 200:
    return "", True  # ← Silently drops entire utterance
```

---

## Problems

### 1. Silent Data Loss

When a long utterance is dropped:
- No log message
- No metric tracked
- No warning to user
- The `had_unknown` flag is set, but this same flag is used for 5+ other conditions

### 2. Flag Overloading

The `had_unknown` boolean conflates multiple distinct conditions:

| Condition | Same Flag? |
|-----------|------------|
| Utterance too long (>4000 chars) | `had_unknown = True` |
| Utterance too many words (>200) | `had_unknown = True` |
| Meta text detected | `had_unknown = True` |
| Unknown speaker prefix | `had_unknown = True` |
| Line without speaker context | `had_unknown = True` |
| Bracketed meta removed | `had_unknown = True` |

Impossible to distinguish "dialogue had noise" from "dialogue lost content."

### 3. Magic Numbers

```python
if len(cleaned) > 4000 or _word_count(cleaned) > 200:
```

These thresholds are undocumented. Why 4000 chars? Why 200 words? No constants, no comments, no settings reference.

---

## Impact

1. **Data Integrity**: A dialogue with one 250-word client monologue loses that entire utterance
2. **Scoring Accuracy**: LLM scores dialogue missing key evidence
3. **Audit Trail**: No way to know which dialogues lost content
4. **Debugging**: When scores seem wrong, no indication preprocessing dropped data

---

## Evidence

Grep shows no logging or metrics for truncation:

```bash
$ grep -n "4000\|200 words" src/vibe_check/
src/vibe_check/preprocessing/extractor.py:42:        if len(inner) >= 200:
src/vibe_check/preprocessing/extractor.py:88:        if len(cleaned) > 4000 or _word_count(cleaned) > 200:
```

No logger calls, no metrics, no constants.

---

## Fix Options

### Option A: Log + Metrics (Recommended)

```python
# Add to constants.py
MAX_UTTERANCE_CHARS = 4000
MAX_UTTERANCE_WORDS = 200

# In extractor.py
import logging
logger = logging.getLogger(__name__)

def _sanitize_utterance_text(text: str, file_id: str | None = None) -> tuple[str, bool, bool]:
    """Return (cleaned_text, had_meta, was_truncated)."""
    # ... existing logic ...

    if len(cleaned) > MAX_UTTERANCE_CHARS or _word_count(cleaned) > MAX_UTTERANCE_WORDS:
        logger.warning(
            "Utterance truncated: %d chars, %d words (file_id=%s)",
            len(cleaned), _word_count(cleaned), file_id or "unknown"
        )
        return "", True, True  # ← New: separate truncation flag

    return cleaned, had_meta, False
```

### Option B: Add to DialogueViews Schema

```python
class DialogueViews(BaseModel):
    # ... existing fields ...
    truncated_utterance_count: int = 0  # ← Track truncation explicitly
```

### Option C: Raise on Truncation

```python
if len(cleaned) > MAX_UTTERANCE_CHARS:
    raise ValueError(
        f"Utterance exceeds {MAX_UTTERANCE_CHARS} chars ({len(cleaned)}). "
        "Consider chunking or raise thresholds."
    )
```

---

## Recommendation

**Option A + B**: Log warnings AND track in schema. This maintains backwards compatibility while adding visibility.

Key changes:
1. Extract magic numbers to `constants.py`
2. Add logging when truncation occurs
3. Add `truncated_utterance_count` to `DialogueViews`
4. Include in diagnostics output

---

## Test Plan

1. Create test dialogue with 250-word utterance
2. Verify warning logged
3. Verify `truncated_utterance_count > 0` in views
4. Verify diagnostics report includes truncation stats

---

## Related

- [BUG-040: Missing PHQ-8 Rubric](BUG-040-missing-phq8-rubric-in-prompts.md) - Another data integrity issue
- [SPEC-07: Run Diagnostics](../_archive/specs/spec-07-run-diagnostics.md) - Diagnostic schema could include truncation
