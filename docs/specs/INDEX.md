# Specification Index

> **vibe-check's ONLY job: Score SQPsychConv → Export PHQ-8 labels for ai-psychiatrist.**
>
> See [SCOPE-CLARITY.md](../research/SCOPE-CLARITY.md).

---

## Master Specification

- **[SPEC-vibe-check.md](../research/SPEC-vibe-check.md)** - Master specification (SSOT)

---

## Active Specs

| ID | Title | Status | Notes |
|----|-------|--------|-------|
| SPEC-09 | [Human Alignment](SPEC-09-human-alignment.md) | CONDITIONAL | Only if diagnostics fail |

---

## Archived Specs (Implemented)

All core specs are implemented and archived in [`../_archive/specs/`](../_archive/specs/).

| ID | Title | Scope |
|----|-------|-------|
| SPEC-01 | [DevEx Foundation](../_archive/specs/SPEC-01-devex-foundation.md) | CI, tooling, project structure |
| SPEC-02 | [Data Pipeline](../_archive/specs/SPEC-02-data-pipeline.md) | Corpus loading, preprocessing, views |
| SPEC-03 | [Aggregation Engine](../_archive/specs/SPEC-03-aggregation-engine.md) | Posterior math, entropy, disagreement |
| SPEC-04 | [Juror Scoring Agent](../_archive/specs/SPEC-04-juror-scoring-agent.md) | PydanticAI juror, PHQ-8 scoring |
| SPEC-05 | [Consensus Orchestration](../_archive/specs/SPEC-05-consensus-orchestration.md) | LangGraph workflow, arbitration |
| SPEC-06 | [Batch Runner & Export](../_archive/specs/SPEC-06-batch-runner-and-export.md) | Batch processing, checkpointing |
| SPEC-07 | [Run Diagnostics](../_archive/specs/SPEC-07-run-diagnostics.md) | Quality metrics, gates |
| SPEC-08 | [Export Contract](../_archive/specs/SPEC-08-export-contract.md) | Public label format |

---

## Status

- **Implemented (archived)**: 8 core specs
- **Conditional**: 1 (SPEC-09)
- **Ready for production run**: ✅ YES
