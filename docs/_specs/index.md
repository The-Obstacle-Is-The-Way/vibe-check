# Specification Index

> **vibe-check's ONLY job: Score SQPsychConv → Export PHQ-8 labels for ai-psychiatrist.**
>
> See [scope-clarity.md](../_archive/research/scope-clarity.md).

---

## Master Specification

- **[spec-vibe-check.md](../_archive/research/spec-vibe-check.md)** - Master specification (SSOT)

---

## Active Specs

| ID | Title | Status | Priority |
|----|-------|--------|----------|
| SPEC-12 | [Preprocessing Artifact Stripping](./SPEC-12-preprocessing-artifact-stripping.md) | **ACTIVE** | P2 (before pilot) |

### SPEC-12: Preprocessing Artifact Stripping

Strip generation artifacts (`[/END]`, `[insert date]`, `[Client's Name]`, etc.) that currently pass through preprocessing unchanged. See [SPEC-12](./SPEC-12-preprocessing-artifact-stripping.md) for details.

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

---

## Status

- **Total specs**: 12 (11 archived + 1 active)
- **SPEC-12 active**: Preprocessing artifact stripping (P2, ~30 min)
- **Ready for pilot run**: ✅ YES (SPEC-12 is optional but recommended)
