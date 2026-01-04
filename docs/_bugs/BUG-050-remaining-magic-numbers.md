# BUG-050: Remaining Magic Numbers in Codebase

| Field | Value |
|-------|-------|
| **Severity** | P4 (Low - Code Hygiene) |
| **Status** | open |
| **Date** | 2026-01-04 |
| **Component** | Various files |
| **Impact** | Maintainability, discoverability |

---

## Summary

While many magic numbers have been extracted to `constants.py` and `settings.py`, a few remain scattered in the codebase. This audit documents all remaining hardcoded values for cleanup.

---

## Already Extracted (Good)

### `constants.py`
- `MAX_EVIDENCE_SNIPPET_WORDS = 50`
- `MAX_EVIDENCE_SNIPPET_CHARS = 400`
- `MAX_JUDGE_EVIDENCE_SNIPPETS = 10`
- `MAX_UTTERANCE_WORDS = 200`
- `MAX_UTTERANCE_CHARS = 4000`
- `SEVERITY_BUCKETS` dict

### `settings.py`
- `max_concurrent_dialogues = 50`
- `openai_rpm = 100`
- `anthropic_rpm = 60`
- `google_rpm = 100`
- `retry_max_wait = 60.0`
- `arbitration_max_prob_threshold = 0.60`
- etc.

---

## Still Hardcoded (Needs Extraction)

### 1. Preprocessing - Bracket Length Threshold

`preprocessing/extractor.py:47`:
```python
if len(inner) >= 200:  # ← Magic number
    return ""
```

**Note**: This is **different** from `MAX_UTTERANCE_WORDS = 200`. This is for bracketed meta-text.

**Fix**: Add `MAX_BRACKET_CHARS = 200` to constants.

---

### 2. Preprocessing - Speaker Prefix Pattern

`preprocessing/extractor.py:15`:
```python
_OTHER_PREFIX_RE = re.compile(r"^\s*[^:]{1,32}\s*:\s+")
#                                      ^^^^ Magic: max 32 chars for speaker name
```

**Fix**: Add `MAX_SPEAKER_PREFIX_CHARS = 32` to constants.

---

### 3. Resilience - HTTP Status Codes

`resilience.py:50`:
```python
return exc.response.status_code in (429, 500, 502, 503, 504)
```

**Verdict**: **OK to keep hardcoded** - these are HTTP standards, not tunable parameters.

---

### 4. Resilience - Default RPM Fallback

`resilience.py:185`:
```python
return 60  # Conservative default
```

**Fix**: Add `DEFAULT_RPM_FALLBACK = 60` to constants or settings.

---

### 5. Fakes - Snippet Preview Length

`scoring/fakes.py:35`:
```python
snippet = " ".join(scoring_text.strip().split()[:20]).strip()
#                                              ^^^ Magic: 20 words for fake snippet
```

**Verdict**: **OK for fakes** - test doubles don't need production constants.

---

### 6. Fakes - Token Counts

`scoring/fakes.py:62-65, 89-92`:
```python
input_tokens=100,
output_tokens=50,
reasoning_tokens=10,
total_tokens=160,
```

**Verdict**: **OK for fakes** - test doubles with arbitrary values.

---

### 7. Splitter - Bucket Count

`data/splitter.py:18`:
```python
bucket = hash_val % 10  # 10 buckets for 80/10/10 split
```

**Verdict**: **OK** - comment explains it's for train/dev/test split ratio.

---

### 8. Ledger - SQLite Timeout

`run/ledger.py:48`:
```python
self._conn = sqlite3.connect(self._path, timeout=30.0)
```

**Fix**: Add `SQLITE_TIMEOUT = 30.0` to constants or settings.

---

### 9. Ledger - Error Message Truncation

`run/ledger.py:217`:
```python
error_message[:500]  # Truncate long error messages
```

**Fix**: Add `MAX_ERROR_MESSAGE_CHARS = 500` to constants.

---

### 10. Credible Interval Alpha

`aggregation/posterior.py:46`:
```python
def compute_credible_interval(posterior: np.ndarray, *, alpha: float = 0.10) -> tuple[int, int]:
```

**Verdict**: **OK** - alpha=0.10 for 90% CI is a parameter with sensible default.

---

## Summary of Required Extractions

| Value | Current Location | Suggested Constant |
|-------|------------------|-------------------|
| 200 | `extractor.py:47` | `MAX_BRACKET_CHARS` |
| 32 | `extractor.py:15` | `MAX_SPEAKER_PREFIX_CHARS` |
| 60 | `resilience.py:185` | `DEFAULT_RPM_FALLBACK` |
| 30.0 | `ledger.py:48` | `SQLITE_TIMEOUT` |
| 500 | `ledger.py:217` | `MAX_ERROR_MESSAGE_CHARS` |

---

## Fix

Add to `constants.py`:

```python
# Preprocessing limits
MAX_BRACKET_CHARS = 200  # Max chars in bracketed text before removal
MAX_SPEAKER_PREFIX_CHARS = 32  # Max chars to consider as speaker prefix

# Operational limits
SQLITE_TIMEOUT = 30.0  # SQLite connection timeout in seconds
DEFAULT_RPM_FALLBACK = 60  # Default requests-per-minute if provider unknown
MAX_ERROR_MESSAGE_CHARS = 500  # Truncation limit for error messages in ledger
```

---

## Test Plan

1. Add constants to `constants.py`
2. Replace hardcoded values with constant references
3. Run `grep -E "\b(200|32|30\.0|500)\b" src/` to verify no stragglers
4. Run tests to ensure no regressions

---

## Related

- [BUG-042: Silent Utterance Truncation](BUG-042-silent-utterance-truncation.md) - also about preprocessing constants
- [BUG-049: Hardcoded Diagnostic Thresholds](BUG-049-hardcoded-diagnostic-thresholds.md) - diagnostic constants
