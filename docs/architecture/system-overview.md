# System Overview

This document provides a high-level view of the vibe-check scoring pipeline.

---

## Pipeline Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                    VIBE-CHECK PIPELINE                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  SQPsychConv Corpus (2,090 dialogues)                           │
│         │                                                       │
│         ▼                                                       │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                   PREPROCESSING                         │    │
│  │  • Parse speaker labels (Therapist:/Client:)            │    │
│  │  • Remove generation artifacts                          │    │
│  │  • Extract dialogue views (client_qa, client_only)      │    │
│  └─────────────────────────────────────────────────────────┘    │
│         │                                                       │
│         ▼                                                       │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                    JURY PHASE                           │    │
│  │                                                         │    │
│  │  ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐        │    │
│  │  │GPT-1│ │GPT-2│ │CLD-1│ │CLD-2│ │GEM-1│ │GEM-2│        │    │
│  │  └──┬──┘ └──┬──┘ └──┬──┘ └──┬──┘ └──┬──┘ └──┬──┘        │    │
│  │     │       │       │       │       │       │           │    │
│  │     └───────┴───────┴───┬───┴───────┴───────┘           │    │
│  │                         │                               │    │
│  │              6 PHQ8Reports (sequential)                 │    │
│  │                                                         │    │
│  │  Each juror independently scores all 8 PHQ-8 items      │    │
│  │  with confidence ratings and evidence extraction        │    │
│  └─────────────────────────────────────────────────────────┘    │
│         │                                                       │
│         ▼                                                       │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                  AGGREGATION PHASE                      │    │
│  │                                                         │    │
│  │  For each PHQ-8 item:                                   │    │
│  │    1. Collect votes from all 6 jurors                   │    │
│  │    2. Compute Dirichlet posterior (0-3 distribution)    │    │
│  │    3. Calculate entropy and clinical probability        │    │
│  │    4. Check arbitration triggers                        │    │
│  │                                                         │    │
│  │  For total score:                                       │    │
│  │    1. Convolve 8 item posteriors → 0-24 distribution    │    │
│  │    2. Compute mode, expected value, credible interval   │    │
│  │    3. Map to severity bucket                            │    │
│  └─────────────────────────────────────────────────────────┘    │
│         │                                                       │
│         ▼                                                       │
│    ┌─────────────────────────────────────┐                      │
│    │        Arbitration Needed?         │                      │
│    │                                    │                      │
│    │   Triggers (any one activates):    │                      │
│    │   • max_prob < 0.60                │                      │
│    │   • entropy > 1.2                  │                      │
│    │   • vote_range ≥ 2                 │                      │
│    │   • clinical_prob in [0.4, 0.6]    │                      │
│    │   • insufficient_evidence ≥ 2      │                      │
│    │   • total_score_std ≥ 2.0          │                      │
│    └─────────────────┬──────────────────┘                      │
│               │                                                 │
│         ┌─────┴─────┐                                           │
│         ▼           ▼                                           │
│        NO          YES                                          │
│         │           │                                           │
│         │     ┌─────▼─────────────────────────────────────┐     │
│         │     │              JUDGE PHASE                  │     │
│         │     │                                           │     │
│         │     │  For each contested item:                 │     │
│         │     │    1. Collect all juror evidence          │     │
│         │     │    2. Send to Judge (Claude Opus)         │     │
│         │     │    3. Receive JudgeItemReport             │     │
│         │     │    4. Override final_item_scores[item]    │     │
│         │     └───────────────────────────────────────────┘     │
│         │           │                                           │
│         └─────┬─────┘                                           │
│               ▼                                                 │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                  FINAL OUTPUT                           │    │
│  │                                                         │    │
│  │  AggregatedPHQ8:                                        │    │
│  │    • final_item_scores: {anhedonia: 1, ...}             │    │
│  │    • final_total_score: 15                              │    │
│  │    • final_severity_bucket: "15-19"                     │    │
│  │    • triggered_arbitration: true/false                  │    │
│  │    • juror_reports: [PHQ8Report × 6]                    │    │
│  │    • judge_resolution: {...} (if arbitrated)            │    │
│  └─────────────────────────────────────────────────────────┘    │
│         │                                                       │
│         ▼                                                       │
│  ┌──────────────┐    ┌───────────────┐    ┌──────────────┐      │
│  │ scored.jsonl │    │  Diagnostics  │    │    Export    │      │
│  │  (internal)  │───▶│ Quality Gates │───▶│ vibe_check_  │      │
│  │              │    │               │    │ labels.jsonl │      │
│  │ Full records │    │ • Reliability │    │ Flattened    │      │
│  │ with proofs  │    │ • Consistency │    │ schema for   │      │
│  │              │    │ • Separation  │    │ downstream   │      │
│  └──────────────┘    └───────────────┘    └──────────────┘      │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Component Summary

| Component | Input | Output | Key Files |
|-----------|-------|--------|-----------|
| **Preprocessing** | Raw dialogue | DialogueViews | `preprocessing/extractor.py` |
| **Jury** | scoring_text | 6 × PHQ8Report | `scoring/juror.py` |
| **Aggregation** | PHQ8Reports | AggregatedPHQ8 | `aggregation/aggregate.py` |
| **Judge** | Contested items | JudgeItemReport | `judge/agent.py` |
| **Diagnostics** | scored.jsonl | DiagnosticReport | `diagnostics/runner.py` |
| **Export** | scored.jsonl | vibe_check_labels.jsonl | `export/writer.py` |

---

## Processing Modes

| Mode | Flag | Behavior |
|------|------|----------|
| **Live** | `--live` | Real LLM API calls |
| **Fake** | (default) | Deterministic fake jurors |
| **Dry-run** | `--limit N` | Process only N dialogues |

---

## Output Artifacts

| File | Purpose | Retention |
|------|---------|-----------|
| `scored.jsonl` | Full scoring records | Internal |
| `run_manifest.json` | Run metadata | Internal |
| `ledger.sqlite` | Job status + token ledger | Internal |
| `rows/` | Per-dialogue JSON rows | Internal |
| `data/checkpoints/vibe_check.db` | LangGraph checkpoints | Temporary |
| `vibe_check_labels.jsonl` | Public export | Permanent |
| `vibe_check_labels.csv` | Alternative format | Permanent |

---

## Related Documentation

- [Data Flow](data-flow.md) - Detailed transformation stages
- [LangGraph Workflow](langgraph-workflow.md) - Single-dialogue graph
- [Scoring: Jury Consensus](../scoring/jury-consensus.md) - How jurors work
- [Scoring: Bayesian Aggregation](../scoring/bayesian-aggregation.md) - Math details
