# BUG-017: Judge evidence truncation is hardcoded

**Severity**: P3 (Data Integrity)
**Status**: RESOLVED
**Date**: 2026-01-03
**Component**: Judge Agent
**Resolution**: Replaced magic number 10 with `MAX_JUDGE_EVIDENCE_SNIPPETS` constant.

## Summary

In `vibe_check.judge.prompting.build_judge_item_prompt`, the evidence list is silently truncated to the first 10 items:

```python
evidence_block = "\n".join(f"- {e}" for e in juror_evidence[:10])
```

The limit `10` is a magic number. If we run a large jury (e.g. 5 models * 3 runs = 15 jurors), valid evidence from later jurors will be ignored by the judge.

## Fix

1. Define `MAX_JUDGE_EVIDENCE_SNIPPETS` in `vibe_check.constants`.
2. Use this constant in `judge/prompting.py`.
3. Consider if this should be in `Settings`. For now, a shared constant is sufficient to remove the magic number.

```
