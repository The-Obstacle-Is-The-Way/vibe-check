# Specification Index

> **vibe-check's ONLY job: Score SQPsychConv → Export PHQ-8 labels for ai-psychiatrist.**
>
> See [scope-clarity.md](../_archive/research/scope-clarity.md).

---

## Master Specification

- **[spec-vibe-check.md](../_archive/research/spec-vibe-check.md)** - Master specification (SSOT)
- **[clinical-alignment-review.md](../_brainstorming/clinical-alignment-review.md)** - Clinical alignment review (APPROVED for Phase 1)

---

## Active Specs

| ID | Title | Status | Scope |
|----|-------|--------|-------|
| — | — | — | No active specs |

All specs have been implemented and archived.

---

## Archived Specs (Implemented)

All specs are implemented and archived in [`../_archive/specs/`](../_archive/specs/).

### Phase 1: NA-Aware Clinical Alignment (SPEC-13 to SPEC-18)

| ID | Title | Scope |
|----|-------|-------|
| SPEC-13 | [NA-Aware Schema](../_archive/specs/SPEC-13-na-aware-schema.md) | Schema: `PHQ8ItemScore` + `discussed` + `PHQ8TotalScore` |
| SPEC-14 | [Clinical Inference Prompts](../_archive/specs/SPEC-14-clinical-inference-prompts.md) | Prompts: v2 constants, JSON skeleton, no frequency anchors |
| SPEC-15 | [NA-Aware Aggregation](../_archive/specs/SPEC-15-na-aware-aggregation.md) | Aggregation: 25-bin posterior, NA→0 imputation |
| SPEC-16 | [HuggingFace NA-Aware Export](../_archive/specs/SPEC-16-huggingface-na-export.md) | Export: `vibe_check_labels_huggingface.jsonl` |
| SPEC-17 | [Judge NA Semantics](../_archive/specs/SPEC-17-judge-na-semantics.md) | Judge: NA-aware arbitration, `possible ⇒ score=1` |
| SPEC-18 | [Diagnostics NA Updates](../_archive/specs/SPEC-18-diagnostics-na-updates.md) | Diagnostics: Coverage metrics, assertion distribution |

### Foundation (SPEC-01 to SPEC-12)

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
| SPEC-09 | [Human Alignment](../_archive/specs/spec-09-human-alignment.md) | Calibration (conditional) |
| SPEC-10 | [Parallel Juror Execution](../_archive/specs/SPEC-10-parallel-juror-execution.md) | Performance optimization |
| SPEC-11 | [PHQ-8 Rubric Embedding](../_archive/specs/SPEC-11-phq8-rubric-embedding.md) | Clinical rubric in prompts |
| SPEC-12 | [Preprocessing Artifact Stripping](../_archive/specs/SPEC-12-preprocessing-artifact-stripping.md) | Strip SQPsychConv bracket artifacts |

---

## Status

- **Total specs**: 18 (all archived)
- **Active specs**: 0
- **Ready for pilot run**: ✅ Phase 1 complete
