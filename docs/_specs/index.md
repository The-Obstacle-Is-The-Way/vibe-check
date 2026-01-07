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
| SPEC-13 | [NA-Aware Schema](SPEC-13-na-aware-schema.md) | READY | Schema: `PHQ8ItemScore` + `discussed` + `PHQ8TotalScore` |
| SPEC-14 | [Clinical Inference Prompts](SPEC-14-clinical-inference-prompts.md) | READY | Prompts: v2 constants, JSON skeleton, no frequency anchors |
| SPEC-15 | [NA-Aware Aggregation](SPEC-15-na-aware-aggregation.md) | READY | Aggregation: 25-bin posterior, NA→0 imputation, shared test utils |
| SPEC-16 | [HuggingFace NA-Aware Export](SPEC-16-huggingface-na-export.md) | READY | Export: `vibe_check_labels_huggingface.jsonl` (SPEC-08 unchanged) |
| SPEC-17 | [Judge NA Semantics](SPEC-17-judge-na-semantics.md) | READY | Judge: NA-aware arbitration, `possible ⇒ score=1` |
| SPEC-18 | [Diagnostics NA Updates](SPEC-18-diagnostics-na-updates.md) | READY | Diagnostics: Coverage metrics, assertion distribution, NA-safe gates |

### Dependency Chain

```
SPEC-13 (Schema) ──┬──> SPEC-14 (Prompts)
                   │
                   ├──> SPEC-15 (Aggregation) ──> SPEC-16 (Export)
                   │                          └──> SPEC-18 (Diagnostics)
                   │
                   └──> SPEC-17 (Judge)
```

### Key Design Decisions (Finalized)

| Decision | Resolution | Rationale |
|----------|------------|-----------|
| `possible` assertion score | **score=1 only** | SSOT Q4: ambiguous evidence → conservative low severity |
| Total posterior bins | **25 bins always** | NA items → point-mass at 0; preserves compatibility |
| `severity_bucket_phq_like` | **Gated by `is_proration_valid`** | Only clinically comparable when ≥7 items discussed |
| Coverage gate thresholds | **MIN_ITEM=0.50, MAX_NA=0.25, MIN_DIAL=0.90** | Reasonable Phase 1 defaults |
| `judge_model` in export | **Best-effort nullable** | Metadata only; doesn't affect labels |
| v1 constants | **Preserved unchanged** | Hash stability for existing runs |

### Implementation Order

1. **SPEC-13**: Schema changes (foundation) - `PHQ8ItemScore`, `PHQ8TotalScore`
2. **SPEC-14**: Prompt changes (v2 constants) - no frequency anchors
3. **SPEC-17**: Judge changes - NA-aware arbitration schema
4. **SPEC-15**: Aggregation changes - `ItemAggregationNA`, `AggregatedPHQ8` updates
5. **SPEC-16**: Export changes - HuggingFace writer
6. **SPEC-18**: Diagnostics changes - coverage, assertions, NA-safe gates

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

- **Total specs**: 18 (12 archived, 6 active)
- **Phase 1 specs**: 6 READY for implementation
- **Ready for pilot run**: ✅ After Phase 1 implementation

### Blocking Issue (RESOLVED by Phase 1)

Per [clinical-alignment-review.md](../_brainstorming/clinical-alignment-review.md):
> The current implementation would generate embeddings that encode incorrect patterns (frequency expectations, 0=not_mentioned conflation).

**Phase 1 implementation unblocks paid API runs.**
