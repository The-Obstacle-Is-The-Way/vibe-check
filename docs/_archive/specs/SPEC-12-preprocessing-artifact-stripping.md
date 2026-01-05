# SPEC-12: Preprocessing Artifact Stripping

> **Status**: IMPLEMENTED (2026-01-05)
> **Priority**: P2 (before pilot)
> **Effort**: Small (~30 min)
> **Blocks**: None (recommended cleanup)

---

## Problem Statement

The SQPsychConv qwen-2.5 corpus contains generation artifacts that should be stripped before scoring:

| Artifact | Count | Example | Current Behavior |
|----------|-------|---------|------------------|
| `[/END]` termination marker | 2,492 occurrences | `Therapist: See you next week. [/END]` | **STRIPPED** |
| Template placeholders | 492 occurrences | `[insert date]`, `[Client's Name]` | **STRIPPED** |

These artifacts:
1. Waste ~10,000 tokens across the corpus (~$0.30)
2. May confuse LLM jurors (low risk, but unnecessary)
3. Make the synthetic nature obvious (cosmetic)

---

## Root Cause

In `src/vibe_check/preprocessing/extractor.py`, the `_strip_bracketed_meta()` function only removes brackets if:
- Content is >= 200 chars, OR
- Content contains specific tokens: "guideline", "instructions", "the user", "format", "word limit"

`[/END]` and `[insert date]` don't match either condition, so they pass through.

---

## Proposed Solution

Add a new stripping step in `_sanitize_utterance_text()` that removes known generation artifacts.

### 1. Add artifact patterns to `constants.py`

```python
# Generation artifact patterns to strip (SPEC-12)
STRIP_GENERATION_ARTIFACT_PATTERNS: tuple[str, ...] = (
    r"\[\s*/?\s*END\s*\]",                 # [/END] or [END]
    r"\[\s*insert[^\]]*\]",                # [insert date], [insert time], etc.
    r"\[\s*next[^\]]*\]",                  # [next week], [next available date], etc.
    r"\[\s*please\s+confirm[^\]]*\]",      # [Please confirm the date and time.]
    r"\[\s*review[^\]]*\]",                # [Reviewing calendar], etc.
    r"\[\s*turn\s+\d+[^\]]*\]",            # [Turn 20]
    r"\[\s*client\s+agrees[^\]]*\]",       # [Client agrees]
    r"\[\s*if\s+the\s+client\s+agrees[^\]]*\]",
    r"\[\s*client(?:'|’)?s?\s*name\s*\]",  # straight or curly apostrophe
    r"\[\s*therapist(?:'|’)?s?\s*name\s*\]",
    r"\[\s*colleague(?:'|’)?s?\s*name\s*\]",
    r"\[\s*(?:daughter|sister)(?:'|’)?s?\s*name\s*\]",
    r"\[\s*keep\s+silent\s*\]",            # [Keep silent]
    r"\[\s*pause[^\]]*\]",                 # [Pause and say nothing], [Pauses, ...]
    r"\[\s*no\s+reply\s*\]",               # [No reply]
    r"\[\s*quiet\s*\]",                    # [Quiet]
)
```

### 2. Add stripping function to `extractor.py`

```python
import re
from vibe_check.constants import STRIP_GENERATION_ARTIFACT_PATTERNS

_ARTIFACT_RE = re.compile(
    "|".join(STRIP_GENERATION_ARTIFACT_PATTERNS),
    re.IGNORECASE
)

def _strip_generation_artifacts(text: str) -> tuple[str, bool]:
    """Remove known generation artifacts like [/END], [insert date], etc."""
    cleaned = _ARTIFACT_RE.sub("", text)
    return cleaned.strip(), (cleaned != text)
```

### 3. Call in `_sanitize_utterance_text()`

```python
def _sanitize_utterance_text(text: str) -> tuple[str, bool, bool]:
    """Strip obvious generation artifacts from speaker-labeled utterances."""
    # NEW: Strip known generation artifacts first
    cleaned, artifacts_removed = _strip_generation_artifacts(text.strip())

    cleaned, bracket_removed = _strip_bracketed_meta(cleaned)
    # ... rest unchanged
```

---

## Acceptance Criteria

1. [x] `[/END]` is stripped from all **preprocessed views** (verify with grep)
2. [x] Common bracket placeholders (`[insert ...]`, `[next ...]`, name placeholders) are stripped
3. [x] Semantic-void directives (`[Keep silent]`, `[Quiet]`, `[No reply]`, `[Pause ...]`) are stripped
4. [x] Existing tests pass
5. [x] New unit test covers artifact stripping
6. [x] No obvious punctuation artifacts introduced (e.g., `Mr..` after removing `[Client's Name]`)

---

## Verification Commands

```bash
# Raw corpus (before preprocessing) - should show counts
uv run python -c "
import re
from vibe_check.data import load_corpus
corpus = load_corpus('data/sqpsychconv/qwen-2.5')
end_count = sum(1 for d in corpus if '[/END]' in d.dialogue or '[END]' in d.dialogue)
print(f'Dialogues with [/END]: {end_count}')
"

# After preprocessing - should show 0
uv run python -c "
from vibe_check.data import load_corpus, preprocess_dialogue
corpus = load_corpus('data/sqpsychconv/qwen-2.5')
for d in corpus[:10]:
    views = preprocess_dialogue(d)
    if '[/END]' in views.client_qa_text or '[END]' in views.client_qa_text:
        print(f'FAIL: {d.file_id} still has [/END]')
        break
else:
    print('PASS: No [/END] in preprocessed views')
"
```

---

## Decision: Required or Optional?

**Recommendation: Do before pilot.** ✅ Implemented

Rationale:
- Small effort (~30 min)
- Eliminates an entire class of potential confusion
- Makes the pipeline cleaner for publication
- $0.30 token savings is trivial, but "no artifacts" is a cleaner claim

If skipped:
- Low risk - LLMs will likely ignore these
- Document explicitly in DATA-QUALITY-ANALYSIS.md Section 2

---

## Files to Modify

1. `src/vibe_check/constants.py` - Add `STRIP_GENERATION_ARTIFACT_PATTERNS`
2. `src/vibe_check/preprocessing/extractor.py` - Add `_strip_generation_artifacts()`, call in `_sanitize_utterance_text()`
3. `tests/unit/test_extractor.py` - Add test for artifact stripping

---

## Implementation Notes (2026-01-05)

Implemented deterministic stripping in:
- `src/vibe_check/constants.py` (`STRIP_GENERATION_ARTIFACT_PATTERNS`)
- `src/vibe_check/preprocessing/extractor.py` (artifact stripping + whitespace/punctuation cleanup)
- `tests/unit/test_extractor.py` (unit test coverage)

---

*Created: 2026-01-04*
*Author: Claude Opus 4.5*
