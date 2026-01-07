# Bug Tracker

## Active Bugs

| ID | Severity | Status | Title |
|----|----------|--------|-------|
| — | — | — | No active bugs |

---

## Recently Resolved

| ID | Severity | Status | Title |
|----|----------|--------|-------|
| BUG-055 | P1 | resolved | [LLM output schemas allow boolean coercion in numeric fields](../_archive/bugs/bug-055-llm-output-schemas-boolean-coercion.md) |
| BUG-054 | P2 | resolved | [HuggingFace export missing `judge_model` provenance](../_archive/bugs/bug-054-hf-export-missing-judge-model.md) |
| BUG-053 | P1 | resolved | [SPEC-08 export crashes on NA juror votes](../_archive/bugs/bug-053-spec-08-export-crashes-on-na-votes.md) |
| BUG-052 | P0 | resolved | [Live run breaks with NA-aware schema (judge + prompt defaults)](../_archive/bugs/bug-052-live-run-breaks-with-na-aware-schema.md) |
| BUG-051 | P1 | resolved | [DAIC-WOZ PHQ-8 Ground Truth Integrity](../_archive/bugs/bug-051-daic-woz-ground-truth-integrity.md) |
| BUG-050 | P4 | resolved | [Remaining Magic Numbers in Codebase](../_archive/bugs/bug-050-remaining-magic-numbers.md) |
| BUG-049 | P3 | resolved | [Hardcoded Diagnostic Thresholds](../_archive/bugs/bug-049-hardcoded-diagnostic-thresholds.md) |
| BUG-048 | P1 | resolved | [No Temperature Control for LLM Calls](../_archive/bugs/bug-048-no-temperature-control-for-llm-calls.md) |
| BUG-046 | P3 | resolved | [No Maximum Iteration Limit on LangGraph](../_archive/bugs/bug-046-no-graph-iteration-limit.md) |
| BUG-045 | P4 | resolved | [Synchronous Judge Function in Async Graph](../_archive/bugs/bug-045-sync-judge-in-async-graph.md) |
| BUG-044 | P4 | resolved | [Over-Parameterized `score_corpus_async()` Function](../_archive/bugs/bug-044-over-parameterized-score-corpus.md) |
| BUG-043 | P2 | resolved | [Flag Overloading Hides Data Loss](../_archive/bugs/bug-043-flag-overloading-hides-data-loss.md) |
| BUG-047 | P5 | resolved | [Bare `pass` Statement in Runner](../_archive/bugs/bug-047-runner-bare-pass-statement.md) |
| BUG-042 | P2 | resolved | [Silent Utterance Truncation in Preprocessing](../_archive/bugs/bug-042-silent-utterance-truncation.md) |
| BUG-041 | P3 | resolved | [Unused `embedding_dialogue_view` Setting (Dead Code)](../_archive/bugs/bug-041-unused-embedding-dialogue-view-setting.md) |
| BUG-040 | P0 | resolved | [Missing PHQ-8 Clinical Rubric in System Prompts](../_archive/bugs/bug-040-missing-phq8-rubric-in-prompts.md) |
| BUG-035 | P2 | resolved | [Sequential juror execution limits throughput](../_archive/bugs/bug-035-sequential-juror-execution.md) |
| BUG-027 | P1 | resolved | [CLI `--prompt-version` / `--dialogue-view` can desync from live agent prompts](../_archive/bugs/bug-027-cli-prompt-version-view-mismatch.md) |
| BUG-028 | P1 | resolved | [Live Gemini jurors env var mismatch](../_archive/bugs/bug-028-google-gla-env-var-mismatch.md) |
| BUG-029 | P2 | resolved | [`vibe-check export --format csv` fails](../_archive/bugs/bug-029-export-csv-only-fails.md) |
| BUG-030 | P2 | resolved | [`RUNS_PER_MODEL` > 2 breaks scoring](../_archive/bugs/bug-030-runs-per-model-schema-constraint.md) |
| BUG-031 | P2 | resolved | [`DISAGREEMENT_RANGE_THRESHOLD` is exposed but unused](../_archive/bugs/bug-031-disagreement-range-threshold-unused.md) |
| BUG-032 | P3 | resolved | [Token usage totals omit judge calls](../_archive/bugs/bug-032-judge-token-usage-missing.md) |
| BUG-033 | P3 | resolved | [Resume can silently mix runs](../_archive/bugs/bug-033-resume-run-config-mismatch.md) |
| BUG-034 | P4 | resolved | [`.env.example` missing arbitration threshold keys](../_archive/bugs/bug-034-env-example-missing-arbitration-thresholds.md) |
| BUG-036 | P3 | resolved | [JudgeItemResolution.item not validated against PHQ8_ITEMS](../_archive/bugs/bug-036-judge-item-name-not-validated.md) |
| BUG-037 | P4 | resolved | [Arbitration parameters hardcoded in disagreement.py](../_archive/bugs/bug-037-hardcoded-arbitration-params.md) |
| BUG-038 | P4 | resolved | [No API key validation before live run](../_archive/bugs/bug-038-no-api-key-validation-before-live-run.md) |
| BUG-039 | P4 | resolved | [max_concurrency parameter misleading for jurors](../_archive/bugs/bug-039-max-concurrency-misleading-for-jurors.md) |

---

## Archived Bugs

All resolved bugs are in [`docs/_archive/bugs/`](../_archive/bugs/index.md).

| Range | Count | Description |
|-------|-------|-------------|
| BUG-001 to BUG-013 | 13 | Initial development bugs |
| BUG-014 to BUG-026 | 13 | Post-implementation bug hunt |
| BUG-027 to BUG-034 | 8 | CI/run/export hardening |
| BUG-035 to BUG-039 | 5 | Validation and configuration hardening |
| BUG-040 to BUG-041 | 2 | PHQ-8 rubric + config cleanup |
| BUG-042 to BUG-042 | 1 | Preprocessing truncation audit |
| BUG-043 to BUG-050 | 8 | Reproducibility + diagnostics + hygiene |
| BUG-051 to BUG-055 | 5 | NA-aware pipeline fixes |

**Total resolved**: 55 bugs

---

## Filing New Bugs

1. Use the next available number: **BUG-056**
2. Create file in this directory: `BUG-NNN-short-description.md`
3. Include: Severity, Status, Date, Summary, Root Cause, Fix
4. When resolved, move to `docs/_archive/bugs/`
