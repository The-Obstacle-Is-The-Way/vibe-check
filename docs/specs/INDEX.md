# Specification Index

This directory contains the vertical slice specifications for vibe-check. Each spec defines a focused deliverable with clear acceptance criteria.

## Master Specification

The comprehensive system design lives in the research directory:

- **[SPEC-vibe-check.md](../research/SPEC-vibe-check.md)** - Master specification (SSOT)

---

## Implementation Specs

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
| SPEC-09 | [Human Alignment](SPEC-09-human-alignment.md) | PLANNED | Calibration, golden set, Kappa metrics |
| SPEC-10 | [Adversarial Robustness](SPEC-10-adversarial-robustness.md) | PLANNED | Chaos testing, prompt injection, resilience |
| SPEC-11 | [Interactive Inspector](SPEC-11-interactive-inspector.md) | PLANNED | TUI, visualization, explainability |

---

## Status Legend

- **IMPLEMENTED**: Spec has been fully implemented and tested
- **IN PROGRESS**: Spec is currently being implemented
- **PLANNED**: Spec is approved but not yet started
- **DRAFT**: Spec is still being designed

---

## Statistics

- **Total specs**: 11
- **Implemented**: 8
- **In Progress**: 0
- **Planned**: 3

---

## Adding New Specs

When creating a new specification:

1. Use the next available number (currently: **SPEC-12**)
2. Follow the naming convention: `SPEC-XX-short-description.md`
3. Include: Status, Dependencies, Deliverables, Acceptance Criteria
4. Update this index after creating the spec file
