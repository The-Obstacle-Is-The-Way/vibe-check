# BUG-043: Flag Overloading Hides Data Loss

| Field | Value |
|-------|-------|
| **Severity** | P2 (Medium - Data Integrity) |
| **Status** | resolved |
| **Date** | 2026-01-04 |
| **Component** | `preprocessing/extractor.py` |
| **Impact** | Cannot distinguish data loss from noise filtering |

---

## Summary

The `had_unknown` boolean flag is used to track **multiple different conditions**, making it impossible to distinguish between:

1. **Data loss** (content was dropped)
2. **Noise filtering** (meta-text was cleaned)
3. **Parse warnings** (unknown speaker labels)

This conflation violates a core principle: **data loss must be distinguishable from data cleaning**.

---

## Conditions Merged Into `had_unknown`

| Line | Condition | Severity | Should Be |
|------|-----------|----------|-----------|
| 47-53 | Long/keyworded bracketed meta removed | Noise filter | `meta_text_removed_count` |
| 106-107 | `_looks_like_meta()` returns True | Noise filter | `meta_text_removed_count` |
| 111-115 | Exceeds caps → truncated | DATA LOSS | `truncated_utterance_count` |
| 149-153 | Unknown speaker prefix pattern | Parse warning | `unknown_speaker_count` |
| 155-157 | Line without speaker context | Parse warning | `orphan_line_count` |

**Result**: When `has_unknown_speaker=True`, you cannot know if:
- A 5000-character client monologue was dropped (CRITICAL)
- A `[Guidelines: stay calm]` bracket was removed (fine)
- A line started with "System:" (fine)

---

## Evidence

### Current Schema

`schemas/views.py:32-39`:
```python
truncated_utterance_count: int = 0
has_empty_client_text: bool = False
has_unknown_speaker: bool = False  # ← Currently conflates unknown speaker + meta-cleaning
```

### Validator Uses It

`data/validator.py:81-83`:
```python
_utterances, had_unknown, _truncated = parse_utterances_with_diagnostics(d.dialogue)
if had_unknown:
    unknown_speaker_count += 1  # ← Count includes truncation!
```

The validator reports `unknown_speaker_count` but this number includes dialogues that had **content truncated**, not just unknown speakers.

---

## Impact

1. **Audit failure**: Cannot answer "how many dialogues lost content?"
2. **Misleading metrics**: `unknown_speaker_count` in validator output is inflated
3. **Debugging impossible**: When scores seem wrong, can't trace to data loss
4. **Research validity**: Silent data loss in labeled dataset

---

## Fix

### Option A: Separate Flags (Recommended)

Replace single boolean with granular counts:

```python
@dataclass
class PreprocessingDiagnostics:
    truncated_utterance_count: int = 0  # DATA LOSS
    truncated_bracket_count: int = 0    # DATA LOSS
    meta_text_removed_count: int = 0    # Noise filter
    unknown_speaker_count: int = 0      # Parse warning
    orphan_line_count: int = 0          # Parse warning

    @property
    def has_data_loss(self) -> bool:
        return self.truncated_utterance_count > 0 or self.truncated_bracket_count > 0

    @property
    def had_unknown(self) -> bool:
        """Backwards-compatible flag."""
        return any([
            self.truncated_utterance_count,
            self.truncated_bracket_count,
            self.meta_text_removed_count,
            self.unknown_speaker_count,
            self.orphan_line_count,
        ])
```

### Option B: At Minimum, Separate Data Loss

```python
class DialogueViews(BaseModel):
    # ... existing fields ...
    has_unknown_speaker: bool = False
    has_data_loss: bool = False  # ← NEW: True if any content was truncated
    truncated_char_count: int = 0  # ← NEW: How many chars were lost
```

---

## Related

- [BUG-042: Silent Utterance Truncation](bug-042-silent-utterance-truncation.md) - The truncation itself
- Both bugs should be fixed together

---

## Test Plan

1. Create test dialogue with:
   - One 5000-char utterance (truncated)
   - One `[Guidelines: be nice]` bracket (meta-removed)
   - One line starting with "System:" (unknown speaker)
2. Verify each condition increments the correct counter
3. Verify `has_data_loss=True` only for truncation
4. Verify corpus validator shows separate counts

---

## Resolution (Implemented)

Implemented a dedicated `PreprocessingDiagnostics` structure in `src/vibe_check/preprocessing/extractor.py` and surfaced separate counters in `src/vibe_check/schemas/views.py`, `src/vibe_check/data/validator.py`, and `src/vibe_check/run/runner.py` so meta-cleaning is no longer conflated with unknown-speaker warnings or truncation.
