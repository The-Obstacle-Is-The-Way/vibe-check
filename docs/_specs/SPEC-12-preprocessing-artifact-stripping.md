# SPEC-12: Preprocessing Artifact Stripping

> **Status**: ACTIVE
> **Priority**: P2 (should do before pilot)
> **Effort**: Small (~30 min)
> **Blocks**: Production run (optional but recommended)

---

## Problem Statement

The SQPsychConv qwen-2.5 corpus contains generation artifacts that should be stripped before scoring:

| Artifact | Count | Example | Current Behavior |
|----------|-------|---------|------------------|
| `[/END]` termination marker | 2,492 occurrences | `Therapist: See you next week. [/END]` | **NOT STRIPPED** |
| Template placeholders | 492 occurrences | `[insert date]`, `[Client's Name]` | **NOT STRIPPED** |

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
STRIP_BRACKET_PATTERNS: tuple[str, ...] = (
    r"\[/?END\]",                          # [/END] or [END]
    r"\[insert\s+[^\]]+\]",                # [insert date], [insert time], etc.
    r"\[next\s+available[^\]]*\]",         # [next available date], etc.
    r"\[Client'?s?\s*Name\]",              # [Client's Name], [Clients Name]
    r"\[Therapist'?s?\s*Name\]",           # [Therapist's Name]
    r"\[Keep\s+silent\]",                  # [Keep silent]
    r"\[Pause[^\]]*\]",                    # [Pause and say nothing]
    r"\[No\s+reply\]",                     # [No reply]
    r"\[Quiet\]",                          # [Quiet]
)
```

### 2. Add stripping function to `extractor.py`

```python
import re
from vibe_check.constants import STRIP_BRACKET_PATTERNS

_ARTIFACT_RE = re.compile(
    "|".join(STRIP_BRACKET_PATTERNS),
    re.IGNORECASE
)

def _strip_generation_artifacts(text: str) -> str:
    """Remove known generation artifacts like [/END], [insert date], etc."""
    return _ARTIFACT_RE.sub("", text).strip()
```

### 3. Call in `_sanitize_utterance_text()`

```python
def _sanitize_utterance_text(text: str) -> tuple[str, bool, bool]:
    """Strip obvious generation artifacts from speaker-labeled utterances."""
    # NEW: Strip known generation artifacts first
    cleaned = _strip_generation_artifacts(text.strip())

    cleaned, bracket_removed = _strip_bracketed_meta(cleaned)
    # ... rest unchanged
```

---

## Acceptance Criteria

1. [ ] `[/END]` is stripped from all dialogues (verify with grep)
2. [ ] `[insert ...]` placeholders are stripped
3. [ ] `[Client's Name]` / `[Therapist's Name]` are stripped
4. [ ] `[Keep silent]`, `[Quiet]`, `[No reply]` are stripped
5. [ ] Existing tests pass
6. [ ] New test: `test_strip_generation_artifacts()`
7. [ ] Preprocessing diagnostics show 0 bracket artifacts after fix

---

## Verification Commands

```bash
# Before fix - should show counts
uv run python -c "
import re
from vibe_check.data import load_corpus
corpus = load_corpus('data/sqpsychconv/qwen-2.5')
end_count = sum(1 for d in corpus if '[/END]' in d.dialogue or '[END]' in d.dialogue)
print(f'Dialogues with [/END]: {end_count}')
"

# After fix - should show 0
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

**Recommendation: Do before pilot.**

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

1. `src/vibe_check/constants.py` - Add `STRIP_BRACKET_PATTERNS`
2. `src/vibe_check/preprocessing/extractor.py` - Add `_strip_generation_artifacts()`, call in `_sanitize_utterance_text()`
3. `tests/preprocessing/test_extractor.py` - Add test for artifact stripping

---

*Created: 2026-01-04*
*Author: Claude Opus 4.5*
