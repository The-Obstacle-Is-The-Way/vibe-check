# Bug Tracker

## Active Bugs

| ID | Severity | Status | Title |
|----|----------|--------|-------|
| BUG-042 | P2 | open | [Silent Utterance Truncation in Preprocessing](BUG-042-silent-utterance-truncation.md) |

---

## Recently Resolved

| ID | Severity | Status | Title |
|----|----------|--------|-------|
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

**Total resolved**: 41 bugs

---

## Filing New Bugs

1. Use the next available number: **BUG-043**
2. Create file in this directory: `BUG-NNN-short-description.md`
3. Include: Severity, Status, Date, Summary, Root Cause, Fix
4. When resolved, move to `docs/_archive/bugs/`
