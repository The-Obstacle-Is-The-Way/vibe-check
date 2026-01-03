# SPEC-REVISION: Scope Creep Cleanup

**Status**: DRAFT — Awaiting Senior Review
**Date**: 2026-01-02
**Issue**: Original SPEC-vibe-check.md conflated vibe-check and ai-psychiatrist responsibilities

---

## 1. Summary of Scope Creep

The original `SPEC-vibe-check.md` included responsibilities that belong in **ai-psychiatrist**, not vibe-check:

| Responsibility | Originally In | Should Be In | Status |
|----------------|---------------|--------------|--------|
| Score SQPsychConv with PHQ-8 | vibe-check | vibe-check | Correct |
| Generate embeddings (Phase 2) | vibe-check | **ai-psychiatrist** | SCOPE CREEP |
| Transfer evaluation (Phase 3) | vibe-check | **ai-psychiatrist** | SCOPE CREEP |
| Clinical data handling | vibe-check | **NEVER vibe-check** | SCOPE CREEP |

---

## 2. Correct Separation of Concerns

### 2.1 vibe-check's TRUE Scope

```
SQPsychConv (synthetic dialogues)
    ↓
Multi-agent PHQ-8 scoring (GPT/Claude/Gemini)
    ↓
Consensus aggregation
    ↓
Export: scored_sqpsychconv.jsonl + validation_report.json
```

**That's it.** No embeddings. No transfer evaluation. No clinical data.

### 2.2 ai-psychiatrist's Scope

```
scored_sqpsychconv.jsonl (from vibe-check)
    ↓
Generate embeddings (sentence-transformers, etc.)
    ↓
Build retrieval index (FAISS, etc.)
    ↓
Transfer evaluation on clinical data (LOCAL ONLY)
    ↓
Performance metrics
```

The embedding and retrieval infrastructure already exists in `ai-psychiatrist`.

---

## 3. What Was Found

### 3.1 Documents With Scope Creep

| Document | Issue | Status |
|----------|-------|--------|
| `docs/research/SPEC-vibe-check.md` | Phase 2/3 include embeddings + transfer eval | Added SCOPE BOUNDARY warning |
| `docs/specs/SPEC-08-embedding-corpus.md` | Entire spec was about embeddings | **DELETED** |
| `docs/specs/SPEC-09-transfer-evaluation.md` | Entire spec was about clinical data transfer | **DELETED, replaced with label export spec** |
| `docs/specs/SPEC-06-batch-runner-and-export.md` | Minor references to clinical data | Fixed |
| `docs/specs/SPEC-07-run-diagnostics.md` | Minor references | Fixed |

### 3.2 Codebase Check

**No embedding or clinical data code has been implemented.**

- Searched `src/` for `embed|DAIC|daic` — only found metadata label usage
- No `sentence-transformers`, `faiss`, or similar in `pyproject.toml`
- No transfer evaluation code

---

## 4. Changes Made

### 4.1 Deleted Files

1. `docs/specs/SPEC-08-embedding-corpus.md` — Embeddings are ai-psychiatrist's job
2. `docs/specs/SPEC-09-transfer-evaluation.md` — Transfer eval is ai-psychiatrist's job

### 4.2 Created Files

1. `docs/specs/SPEC-08-export-contract.md` — Defines label export format only (no embeddings)
   - Originally created as SPEC-09, renamed to SPEC-08 to fill the gap

### 4.3 Edited Files

1. `docs/research/SPEC-vibe-check.md`:
   - Added SCOPE BOUNDARY warning at top
   - Clarified executive summary
   - Removed clinical data references from "Known Sharp Edges"
   - Replaced Section 3.2 (clinical data policy) with separation note

2. `docs/specs/SPEC-06-batch-runner-and-export.md`:
   - Removed clinical data references from Non-Goals

3. `docs/specs/SPEC-07-run-diagnostics.md`:
   - Added Anti-Patterns section clarifying scope

---

## 5. Remaining Work (Pending Senior Review)

### 5.1 SPEC-vibe-check.md Deep Cleanup

The master spec still contains ~20 legacy references to embeddings/transfer eval in:
- Section 5.3 (Embedding View discussions)
- Section 12.3 (Phase 2: Generate Embeddings)
- Section 12.4 (Phase 3: Transfer eval)
- Various tables and checklists

**Recommendation**: Either:
1. Add prominent "OUT OF SCOPE" banners to these sections, OR
2. Remove/rewrite these sections entirely

Awaiting senior review before proceeding.

### 5.2 Other Documents

The following may need review:
- `docs/research/SPEC-REVISION-synthetic-data-simplification.md` — 2 references
- Any other research docs

---

## 6. Why This Matters

1. **Confusion**: Agents reading the specs kept trying to implement embeddings/transfer eval in vibe-check
2. **Data governance**: Clinical data should NEVER appear in vibe-check — clear separation prevents accidents
3. **Complexity**: vibe-check is already complex enough without adding embedding infrastructure
4. **Existing work**: ai-psychiatrist already has embedding/retrieval infrastructure — no need to duplicate

---

## 7. Verification Checklist

Before proceeding with further development:

- [x] No embedding code in `src/`
- [x] No embedding dependencies in `pyproject.toml`
- [x] No clinical data references in core specs (SPEC-04 through SPEC-07)
- [x] SPEC-08 deleted (was embedding corpus)
- [x] SPEC-09 rewritten (now label export only)
- [x] SCOPE BOUNDARY warning added to master spec
- [ ] Senior review of remaining legacy content in SPEC-vibe-check.md
- [ ] Confirm approach for handling Section 12.3/12.4 (Phase 2/3)

---

## 8. References

- `_reference/ai-psychiatrist/` — Cloned from The-Obstacle-Is-The-Way/ai-psychiatrist
- This is the downstream consumer of vibe-check's label exports
- Contains existing embedding/retrieval infrastructure

---

## 9. Approval Required

**This revision requires senior review before:**
1. Removing/rewriting Phase 2/3 sections from SPEC-vibe-check.md
2. Making further changes to core documentation

**Rationale**: The original spec was the foundation document. Major structural changes should be approved to ensure alignment with project goals.
