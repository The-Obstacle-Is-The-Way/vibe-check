# Core Concepts

This section explains the fundamental ideas behind vibe-check's multi-agent PHQ-8 scoring system.

---

## Overview

vibe-check uses a **jury-judge consensus model** to score therapy dialogues for depression severity. Multiple LLM "jurors" independently score each dialogue, their votes are aggregated using Bayesian statistics, and a "judge" arbitrates when jurors disagree significantly.

---

## Concepts

| Concept | Description |
|---------|-------------|
| [Jury Consensus](jury-consensus.md) | How multiple jurors vote independently and why diversity improves reliability |
| [Bayesian Aggregation](bayesian-aggregation.md) | Dirichlet posteriors, entropy, and how votes become probability distributions |
| [Arbitration](arbitration.md) | When and why the judge intervenes to resolve contested items |
| [Dialogue Views](dialogue-views.md) | How raw dialogues are preprocessed into scoring-ready text |
| [Resilience](resilience.md) | Three-layer retry and rate-limiting strategy for reliable LLM calls |
| [Quality Gates](quality-gates.md) | Diagnostics that validate scoring quality before export |

---

## Key Terminology

| Term | Definition |
|------|------------|
| **PHQ-8** | 8-item Patient Health Questionnaire for depression severity (0-24 scale) |
| **Juror** | An LLM agent that independently scores a dialogue |
| **Judge** | An LLM agent that arbitrates when jurors disagree |
| **Posterior** | Probability distribution over possible scores after observing votes |
| **Arbitration** | Process of resolving contested items via judge intervention |
| **Severity Bucket** | Score ranges: 0-4 (minimal), 5-9 (mild), 10-14 (moderate), 15-19 (moderately severe), 20-24 (severe) |

---

## How It All Fits Together

```
Dialogue → Preprocessing → 6 Jurors → Aggregation → [Arbitration] → Final Score
              (views)       (votes)    (posteriors)    (if needed)    (PHQ-8)
```

1. **Preprocessing** extracts a clean dialogue view (e.g., `client_qa`)
2. **Jury Phase** runs 6 independent jurors (3 models × 2 runs each)
3. **Aggregation** computes Bayesian posteriors and detects disagreement
4. **Arbitration** (if triggered) calls the judge to resolve contested items
5. **Final Score** is the PHQ-8 total with severity classification
