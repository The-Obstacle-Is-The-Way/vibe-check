# SPEC-05: Consensus Orchestration (Jury + Judge + Checkpointing)

**Status**: DRAFT (2026-01-02)
**Slice Type**: Vertical (Single Dialogue → Final Consensus Output)
**Dependencies**: SPEC-02 (Views), SPEC-03 (Aggregation), SPEC-04 (Juror Scorer)
**Estimated Scope**: ~500 lines of code, ~350 lines of tests

---

## 1. Objective

Implement the smallest production-grade orchestration layer that:

1. Runs a **heterogeneous jury** (3 models × 2 runs = 6 `PHQ8Report`s)
2. Aggregates with SPEC-03 (`aggregate_reports`)
3. Triggers judge arbitration when disagreement criteria fire
4. Produces a **final, exportable PHQ-8 label** per dialogue (items + total)
5. Persists state so the pipeline can resume (SQLite checkpointing)

This slice is “one dialogue end-to-end”, but with the same control flow and persistence primitives needed for the full batch job.

### Success Criteria

```python
from vibe_check.graph.single_dialogue import score_one_dialogue
from vibe_check.schemas.output import AggregatedPHQ8

result: AggregatedPHQ8 = score_one_dialogue(
    file_id="active82",
    corpus_dir="data/sqpsychconv/qwq",
    prompt_version="v1",
    checkpoint_db="sqlite:///data/checkpoints/dev.db",
    jurors=[...],        # 3 models × 2 runs (real or deterministic fakes)
    judge_item=...,      # callable returning JudgeItemResolution
)

assert result.items["sleep"].posterior["2"] >= 0.0
assert result.total_ci_90[0] <= result.total_mode <= result.total_ci_90[1]
assert result.triggered_arbitration in {True, False}
```

---

## 2. Deliverables

### 2.1 New Source Files

| File | Purpose |
|------|---------|
| `src/vibe_check/graph/__init__.py` | Graph package (already exists) |
| `src/vibe_check/graph/state.py` | Typed state definitions (already exists) |
| `src/vibe_check/graph/single_dialogue.py` | LangGraph workflow for one dialogue |
| `src/vibe_check/judge/schema.py` | Judge output schema (per contested item) |
| `src/vibe_check/judge/prompting.py` | Judge prompt builder (excerpt + juror evidence) |

### 2.2 Updated Schemas (SSOT-safe)

`AggregatedPHQ8` must become export-ready by adding:

- `final_item_scores: dict[str, int]` (0–3 per item)
- `final_total_score: int` (0–24)
- `final_severity_bucket: Literal["0-4", "5-9", "10-14", "15-19", "20-24"]`
- `final_source: Literal["jury_mode", "jury_expected", "judge_override"]` or equivalent provenance

Rule:
- If an item is arbitrated, `final_item_scores[item]` must come from the judge.
- Otherwise default to the juror consensus (mode unless explicitly changed).

### 2.3 Dependencies

Add orchestration/runtime deps:

- `langgraph>=1.0.0`
- `langgraph-checkpoint-sqlite>=1.0.0`
- `tenacity` (bounded retries; no infinite loops)
- `aiolimiter` (rate limiting)

All network calls must remain optional in tests (fake clients).

---

## 3. Workflow Design

### 3.1 Graph Nodes (Single Dialogue)

**1) Jury (fan-out)**
- Run 6 juror calls (3 models × 2 runs)
- Each juror node uses `state['scoring_text']` (passed in state)
- Each call returns `PHQ8Report` (SPEC-04)
- Collect into state as `juror_reports: list[PHQ8Report]`

**2) Aggregate**
- Call `aggregate_reports(...)` (SPEC-03)
- Output: `AggregatedPHQ8` with arbitration flags set

**3) Arbitrate (conditional)**
- If `AggregatedPHQ8.triggered_arbitration`:
  - For each contested item, call the judge with:
    - PHQ-8 item definition
    - juror scores + evidence
    - a short transcript excerpt (derived from `state['scoring_text']`)
  - Produce `judge_resolution` and compute `final_item_scores`

**4) Finalize**
- Compute `final_total_score` and derived severity bucket from final item scores

### 3.2 Checkpointing

Use LangGraph checkpointing (SQLite) so that:

- A crash after the jury step does not repeat completed calls
- Retries are bounded and error-coded
- The checkpointed state contains full context (including dialogue text) for debugging

Implementation note: accept either a raw SQLite file path (e.g., `data/checkpoints/dev.db`) or SQLAlchemy-style `sqlite:///data/checkpoints/dev.db` and normalize internally.

---

## 4. Arbitration Semantics

### 4.1 Judge Output Schema (Per Item)

Judge returns strict JSON:

```json
{
  "item": "sleep",
  "final_score": 2,
  "confidence": 0.77,
  "rationale": "Client reports difficulty sleeping most nights."
}
```

### 4.2 How Judge Overrides Work

- Judge only decides contested items (never re-scores everything)
- The judge decision is the final label for that item
- Store all judge outputs for audit

---

## 5. Testing Strategy

### 5.1 Unit Tests

- Routing: arbitration triggers take the arbitration branch
- Judge override: final scores differ from jury mode when judge contradicts
- Schema evolution: added `final_*` fields validate and remain backward-compatible where possible

### 5.2 Integration Tests (Deterministic)

Use fake jurors/judge:

- Provide 6 deterministic `PHQ8Report`s that trigger arbitration
- Provide deterministic judge JSON for contested items
- Assert:
  - final scores reflect judge
  - `AggregatedPHQ8` still includes original juror aggregation stats

### 5.3 Checkpoint/Resume Test (Critical)

- Run the graph, force a failure after N juror calls
- Resume using the same checkpoint DB
- Assert already-completed juror calls are not repeated (use call counters in fake clients)

---

## 6. Non-Goals

- Batch processing across 2,090 dialogues (SPEC-06)
- Embedding generation and retrieval indexing (deferred)
- Provider-specific reliability tuning based on synthetic artifacts
