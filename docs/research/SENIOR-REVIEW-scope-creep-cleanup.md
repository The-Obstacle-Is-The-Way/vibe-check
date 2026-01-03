# Senior Review Request: Scope Creep Cleanup

**Date**: 2026-01-02
**Reviewer**: Senior Engineer / Project Lead
**Status**: AWAITING REVIEW
**Related**: `SPEC-REVISION-scope-creep-cleanup.md`

---

## 1. Executive Summary

We discovered that the original `SPEC-vibe-check.md` conflated the responsibilities of TWO separate repositories:

| Repository | Correct Responsibility |
|------------|------------------------|
| **vibe-check** | Score SQPsychConv → Export PHQ-8 labels |
| **ai-psychiatrist** | Generate embeddings → Transfer evaluation |

The original spec included "Phase 2: Generate Embeddings" and "Phase 3: Transfer Evaluation" which should NEVER have been in vibe-check.

---

## 2. Evidence: ai-psychiatrist Already Has This Infrastructure

We examined `_reference/ai-psychiatrist/` (cloned from `The-Obstacle-Is-The-Way/ai-psychiatrist`) and confirmed:

### 2.1 Embedding Infrastructure EXISTS in ai-psychiatrist

```
_reference/ai-psychiatrist/
├── src/ai_psychiatrist/services/
│   ├── embedding.py           # EmbeddingService with cosine similarity search
│   ├── chunking.py            # Transcript chunking
│   ├── chunk_scoring.py       # Chunk-level PHQ-8 scoring
│   ├── reference_store.py     # NPZ/JSON reference loading
│   └── reference_validation.py # CRAG validation
├── docs/embeddings/
│   ├── embedding-generation.md    # How to generate embeddings
│   ├── embeddings-explained.md    # Architecture
│   ├── few-shot-design-considerations.md
│   └── chunk-scoring.md          # Spec 35 implementation
└── scripts/
    └── generate_embeddings.py     # CLI for embedding generation
```

### 2.2 ai-psychiatrist README Confirms This

From `_reference/ai-psychiatrist/README.md`:
> "**Embedding-Based Few-Shot Learning**: Paper reports 22% lower item-level MAE vs zero-shot (0.796 → 0.619)"

The embedding pipeline is a CORE feature of ai-psychiatrist, not vibe-check.

### 2.3 ai-psychiatrist CLAUDE.md Confirms This

From `_reference/ai-psychiatrist/CLAUDE.md`:
> "**Few-Shot RAG Pipeline (Specs 33-36)**: Our implementation fixes the original methodology's core flaw..."

ai-psychiatrist has 4 specs (33-36) dedicated to few-shot retrieval. Duplicating this in vibe-check would be redundant.

---

## 3. What Belongs Where

### 3.1 vibe-check's TRUE Scope

```
SQPsychConv (2,090 synthetic dialogues)
    ↓
Multi-agent PHQ-8 scoring (GPT/Claude/Gemini via cloud APIs)
    ↓
Jury consensus + Judge arbitration
    ↓
Export: scored_sqpsychconv.jsonl
```

**No embeddings. No transfer evaluation. No clinical data.**

### 3.2 ai-psychiatrist's Scope

```
scored_sqpsychconv.jsonl (from vibe-check)
    ↓
Generate embeddings (sentence-transformers, Ollama, HuggingFace)
    ↓
Build retrieval index (NPZ + JSON sidecars)
    ↓
Few-shot prompting for clinical transcripts (LOCAL ONLY)
    ↓
Transfer evaluation metrics (MAE, AURC, AUGRC)
```

ai-psychiatrist handles ALL embedding and clinical data concerns.

---

## 4. What We Found in vibe-check Documentation

### 4.1 Scope Creep in SPEC-vibe-check.md

| Section | Issue |
|---------|-------|
| Section 5.3 | Extensive discussion of "Embedding View" (`client_qa`) |
| Section 12.3 | "Phase 2: Generate Embeddings" — describes embedding pipeline |
| Section 12.4 | "Phase 3: Transfer Evaluation" — describes DAIC-WOZ eval |
| Various tables | References to embedding dimensions, DAIC-WOZ MAE targets |

### 4.2 Incorrect Specs We Wrote

| Spec | Problem |
|------|---------|
| SPEC-08-embedding-corpus.md | Entire spec was about embedding generation |
| SPEC-09-transfer-evaluation.md | Entire spec was about DAIC-WOZ transfer |

---

## 5. Actions Already Taken

| Action | Status |
|--------|--------|
| DELETED `SPEC-08-embedding-corpus.md` | Done |
| DELETED `SPEC-09-transfer-evaluation.md` | Done |
| CREATED `SPEC-08-export-contract.md` (label export only) | Done |
| Added SCOPE BOUNDARY warning to top of `SPEC-vibe-check.md` | Done |
| Fixed DAIC-WOZ references in SPEC-06, SPEC-07 | Done |
| Verified NO embedding code in `src/` | Done |
| Verified NO embedding deps in `pyproject.toml` | Done |

---

## 6. Codebase Verification

```bash
# Searched for embedding code in src/
grep -r "embed" src/
# Result: Only 1 match — metadata label ("embed in outputs"), NOT embedding generation

# Searched for embedding dependencies
grep -E "sentence-transformers|faiss" pyproject.toml
# Result: No matches

# Searched for DAIC-WOZ in src/
grep -r "DAIC|daic" src/
# Result: No matches
```

**Conclusion**: The scope creep was in DOCUMENTATION only. No incorrect code was implemented.

---

## 7. Remaining Work (Pending Your Approval)

### 7.1 Option A: Add OUT OF SCOPE Banners

Keep Sections 5.3, 12.3, 12.4 in SPEC-vibe-check.md but add prominent warnings:

```markdown
> **OUT OF SCOPE**: This section describes functionality that has been
> moved to `ai-psychiatrist`. Do not implement in vibe-check.
```

### 7.2 Option B: Remove Sections Entirely

Delete Sections 12.3 (Phase 2) and 12.4 (Phase 3) from SPEC-vibe-check.md entirely, keeping only:
- Phase 0: Sanity Checks
- Phase 1: Score SQPsychConv (the actual work)

### 7.3 Recommendation

**Option A** is safer — it preserves context for future readers while making scope clear. Deleting historical content risks losing important design rationale.

---

## 8. Questions for Senior Review

1. **Confirm separation**: Is it correct that vibe-check should ONLY produce labels, with ai-psychiatrist handling ALL embedding/retrieval?

2. **Approach for legacy content**: Should we add OUT OF SCOPE banners (Option A) or delete sections entirely (Option B)?

3. **SPEC-vibe-check.md Section 5.3**: The "Embedding View" discussion (`client_qa` vs `client_only`) is actually relevant for SCORING view selection too. Should we rename this section to "Dialogue View Selection" and clarify it's about scoring input format, not embeddings?

4. **Data flow confirmation**: vibe-check exports `scored_sqpsychconv.jsonl` → ai-psychiatrist ingests this → generates embeddings → runs transfer evaluation. Is this the correct architecture?

---

## 9. Files to Review

1. `docs/research/SPEC-REVISION-scope-creep-cleanup.md` — Documents the issue
2. `docs/research/SPEC-vibe-check.md` — Original spec with scope creep (see SCOPE BOUNDARY warning at top)
3. `docs/specs/SPEC-08-export-contract.md` — New spec for label export only
4. `_reference/ai-psychiatrist/` — Reference implementation showing ai-psychiatrist's embedding infrastructure

---

## 10. TL;DR

**vibe-check**: Score synthetic dialogues → Export labels.

**ai-psychiatrist**: Generate embeddings → Transfer evaluation on clinical data.

The original spec mixed these concerns. We've cleaned up the actionable specs (deleted old SPEC-08/09, created new SPEC-08) but the master spec (SPEC-vibe-check.md) still has legacy content in Sections 5.3, 12.3, 12.4.

**Awaiting your decision on how to handle the legacy content.**
