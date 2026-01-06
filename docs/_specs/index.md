# Specification Index

> **vibe-check's ONLY job: Score SQPsychConv → Export PHQ-8 labels for ai-psychiatrist.**
>
> See [scope-clarity.md](../_archive/research/scope-clarity.md).

---

## Master Specification

- **[spec-vibe-check.md](../_archive/research/spec-vibe-check.md)** - Master specification (SSOT)
- **[clinical-alignment-review.md](../_brainstorming/clinical-alignment-review.md)** - Clinical alignment review (APPROVED for Phase 1)

---

## Active Specs (Phase 1: NA-Aware Clinical Alignment)

| ID | Title | Status | Scope |
|----|-------|--------|-------|
| SPEC-13 | [NA-Aware Schema](SPEC-13-na-aware-schema.md) | DRAFT | Schema: `PHQ8ItemScore` + `PHQ8TotalScore` with assertion semantics |
| SPEC-14 | [Clinical Inference Prompts](SPEC-14-clinical-inference-prompts.md) | DRAFT | Prompts: Replace frequency anchors with clinical inference |
| SPEC-15 | [NA-Aware Aggregation](SPEC-15-na-aware-aggregation.md) | DRAFT | Aggregation: Handle None votes, track `p_not_mentioned` |
| SPEC-16 | [HuggingFace NA-Aware Export](SPEC-16-huggingface-na-export.md) | DRAFT | Export: New NA-aware format (SPEC-08 unchanged) |

**Dependency Chain**: SPEC-13 → SPEC-14 → SPEC-15 → SPEC-16

---

## Archived Specs (Implemented)

All specs are implemented and archived in [`../_archive/specs/`](../_archive/specs/).

| ID | Title | Scope |
|----|-------|-------|
| SPEC-01 | [DevEx Foundation](../_archive/specs/spec-01-devex-foundation.md) | CI, tooling, project structure |
| SPEC-02 | [Data Pipeline](../_archive/specs/spec-02-data-pipeline.md) | Corpus loading, preprocessing, views |
| SPEC-03 | [Aggregation Engine](../_archive/specs/spec-03-aggregation-engine.md) | Posterior math, entropy, disagreement |
| SPEC-04 | [Juror Scoring Agent](../_archive/specs/spec-04-juror-scoring-agent.md) | PydanticAI juror, PHQ-8 scoring |
| SPEC-05 | [Consensus Orchestration](../_archive/specs/spec-05-consensus-orchestration.md) | LangGraph workflow, arbitration |
| SPEC-06 | [Batch Runner & Export](../_archive/specs/spec-06-batch-runner-and-export.md) | Batch processing, checkpointing |
| SPEC-07 | [Run Diagnostics](../_archive/specs/spec-07-run-diagnostics.md) | Quality metrics, gates |
| SPEC-08 | [Export Contract](../_archive/specs/spec-08-export-contract.md) | Public label format |
| SPEC-09 | [Human Alignment](../_archive/specs/spec-09-human-alignment.md) | Calibration (conditional, if diagnostics fail) |
| SPEC-10 | [Parallel Juror Execution](../_archive/specs/SPEC-10-parallel-juror-execution.md) | Performance optimization (BUG-035) |
| SPEC-11 | [PHQ-8 Rubric Embedding](../_archive/specs/SPEC-11-phq8-rubric-embedding.md) | Clinical rubric in prompts (BUG-040) |
| SPEC-12 | [Preprocessing Artifact Stripping](../_archive/specs/SPEC-12-preprocessing-artifact-stripping.md) | Strip SQPsychConv bracket artifacts |

---

## Status

- **Total specs**: 16 (12 archived, 4 active)
- **Phase 1 specs**: 4 DRAFT (pending senior review)
- **Ready for pilot run**: ⏸️ BLOCKED (Phase 1 specs must be implemented first)

### Phase 1 Implementation Order

1. **SPEC-13**: Schema changes (foundation)
2. **SPEC-14**: Prompt changes (requires SPEC-13)
3. **SPEC-15**: Aggregation changes (requires SPEC-13)
4. **SPEC-16**: Export changes (requires SPEC-15)

### Blocking Issue

Per [clinical-alignment-review.md](../_brainstorming/clinical-alignment-review.md):
> The current implementation would generate embeddings that encode incorrect patterns (frequency expectations, 0=not_mentioned conflation).

**No paid API runs until Phase 1 is complete.**
