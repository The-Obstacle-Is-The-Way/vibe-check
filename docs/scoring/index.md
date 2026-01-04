# Scoring

This section documents the core PHQ-8 scoring pipeline: how jurors vote, how votes are aggregated, and when the judge intervenes.

---

## Documents

| Document | Description |
|----------|-------------|
| [Jury Consensus](jury-consensus.md) | How jurors score each dialogue (default: 6) |
| [Bayesian Aggregation](bayesian-aggregation.md) | Combining votes into probability distributions |
| [Arbitration](arbitration.md) | When and why the judge intervenes |

---

## Overview

The scoring pipeline works in three phases:

```
┌─────────────────────────────────────────────────────────────┐
│                    SCORING PIPELINE                         │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Dialogue Text                                              │
│         │                                                   │
│         ▼                                                   │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ PHASE 1: JURY                                       │    │
│  │  3 models × RUNS_PER_MODEL jurors score independently│    │
│  │  → N PHQ8Reports                                     │    │
│  └─────────────────────────────────────────────────────┘    │
│         │                                                   │
│         ▼                                                   │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ PHASE 2: AGGREGATION                                │    │
│  │  Dirichlet posteriors + convolution                 │    │
│  │  → Probability distributions, entropy, CI           │    │
│  └─────────────────────────────────────────────────────┘    │
│         │                                                   │
│         ▼                                                   │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ PHASE 3: ARBITRATION (if triggered)                 │    │
│  │  Judge reviews contested items                      │    │
│  │  → Final scores with judge override                 │    │
│  └─────────────────────────────────────────────────────┘    │
│         │                                                   │
│         ▼                                                   │
│  AggregatedPHQ8 (final output)                              │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Key Concepts

### Multi-Model Jury

Instead of trusting a single LLM, vibe-check by default uses 6 jurors from 3 different providers. This provides:
- Cross-model validation
- Uncertainty quantification
- Detection of model-specific biases

### Bayesian Aggregation

Juror votes are combined using Dirichlet posteriors, preserving full probability distributions rather than just point estimates. This enables:
- Credible intervals (90% CI)
- Entropy-based uncertainty
- Clinical probability estimation

### Conditional Arbitration

When jurors disagree beyond thresholds, a "judge" (Claude Opus) reviews the evidence and renders a final decision. This balances:
- Quality (careful review of contested items)
- Cost (judge only invoked when needed)

---

## Related Sections

- [Preprocessing](../preprocessing/) - How dialogues become scoring text
- [Reliability](../reliability/) - Quality gates and resilience
- [Architecture](../architecture/) - System design and data flow
