# Specification Index

This directory contains the vertical slice specifications for vibe-check. Each spec defines a focused deliverable with clear acceptance criteria.

## Scope Reminder

> **vibe-check's ONLY job: Score SQPsychConv → Export PHQ-8 labels for ai-psychiatrist.**
>
> See [SCOPE-CLARITY.md](../research/SCOPE-CLARITY.md) before adding new specs.

## Master Specification

The comprehensive system design lives in the research directory:

- **[SPEC-vibe-check.md](../research/SPEC-vibe-check.md)** - Master specification (SSOT)

---

## Core Specs (Required for Definition of Done)

| ID | Title | Status | Scope |
|----|-------|--------|-------|
| SPEC-01 | [DevEx Foundation](SPEC-01-devex-foundation.md) | IMPLEMENTED | CI, tooling, project structure |
| SPEC-02 | [Data Pipeline](SPEC-02-data-pipeline.md) | IMPLEMENTED | Corpus loading, preprocessing, views |
| SPEC-03 | [Aggregation Engine](SPEC-03-aggregation-engine.md) | IMPLEMENTED | Posterior math, entropy, disagreement |
| SPEC-04 | [Juror Scoring Agent](SPEC-04-juror-scoring-agent.md) | IMPLEMENTED | PydanticAI juror, PHQ-8 scoring |
| SPEC-05 | [Consensus Orchestration](SPEC-05-consensus-orchestration.md) | IMPLEMENTED | LangGraph workflow, arbitration |
| SPEC-06 | [Batch Runner & Export](SPEC-06-batch-runner-and-export.md) | IMPLEMENTED | Batch processing, checkpointing |
| SPEC-07 | [Run Diagnostics](SPEC-07-run-diagnostics.md) | IMPLEMENTED | Quality metrics, gates |
| SPEC-08 | [Export Contract](SPEC-08-export-contract.md) | IMPLEMENTED | Public label format |

**All core specs are implemented. Ready to run production batch.**

---

## Optional Spec

| ID | Title | Status | Rationale |
|----|-------|--------|-----------|
| SPEC-09 | [Human Alignment](SPEC-09-human-alignment.md) | CONDITIONAL | Only implement if SPEC-07 diagnostics fail quality gates |

---

## Status Legend

- **IMPLEMENTED**: Spec has been fully implemented and tested
- **CONDITIONAL**: Implement only if specific conditions are met

---

## Statistics

- **Core specs**: 8 (all IMPLEMENTED)
- **Optional**: 1 (CONDITIONAL)
- **Ready for production run**: ✅ YES

---

## Adding New Specs

Before adding new specs, ask: **Does this help us label SQPsychConv?**

If the answer is no, don't add it. See [SCOPE-CLARITY.md](../research/SCOPE-CLARITY.md).
