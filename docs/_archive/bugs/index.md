# Bug Index (Archived)

All bugs in this directory have been **resolved**. Bug numbers are permanent identifiers and must not be reused.

---

## Bug Registry

| ID | Title | Severity | Status |
|----|-------|----------|--------|
| BUG-001 | [State governance conflict](bug-001-state-governance-conflict.md) | - | FIXED |
| BUG-002 | [PydanticAI missing](bug-002-pydantic-ai-missing.md) | - | FIXED |
| BUG-003 | [Token usage missing](bug-003-token-usage-missing.md) | - | FIXED |
| BUG-004 | [Evidence snippet bounds](bug-004-evidence-snippet-bounds.md) | - | FIXED |
| BUG-005 | [Runner hardcoded fakes](bug-005-runner-hardcoded-fakes.md) | - | FIXED |
| BUG-006 | [Agent bypasses PydanticAI](bug-006-agent-bypasses-pydanticai.md) | - | FIXED |
| BUG-007 | [Incomplete settings](bug-007-incomplete-settings.md) | - | FIXED |
| BUG-008 | [Magic numbers and DRY](bug-008-magic-numbers-and-dry.md) | - | FIXED |
| BUG-009 | [Silent failures and parsing](bug-009-silent-failures-and-parsing.md) | - | FIXED |
| BUG-010 | [Token usage persistence](bug-010-token-usage-persistence.md) | P2 | FIXED |
| BUG-011 | [Running status recovery](bug-011-running-status-recovery.md) | P3 | FIXED |
| BUG-012 | [Export crashes on empty rows](bug-012-export-crashes-on-empty-rows.md) | P2 | FIXED |
| BUG-013 | [Ledger connection churn](bug-013-ledger-connection-churn.md) | P3 | FIXED |
| BUG-014 | [CI real-data tests depend on untracked dataset](bug-014-ci-realdata-tests-depend-on-untracked-dataset.md) | P3 | RESOLVED |
| BUG-015 | [Run manifest arbitration rate wrong on resume](bug-015-run-manifest-arbitration-rate-wrong-on-resume.md) | P2 | RESOLVED |
| BUG-016 | [CLI default should be offline-safe](bug-016-cli-default-should-be-offline-safe.md) | P3 | RESOLVED |
| BUG-017 | [SPEC-04 deliverables mismatch parsing module](bug-017-spec-04-deliverables-mismatch-parsing-module.md) | P3 | RESOLVED |
| BUG-018 | [Spec status stale for implemented slices](bug-018-spec-status-stale-for-implemented-slices.md) | P4 | RESOLVED |
| BUG-019 | [Type ignore in deterministic fakes](bug-019-type-ignore-in-deterministic-fakes.md) | P4 | RESOLVED |
| BUG-020 | [Deprecated datetime.utcnow](bug-020-deprecated-datetime-utcnow.md) | P4 | RESOLVED |
| BUG-021 | [Fake jury model ID mismatch](bug-021-fake-jury-model-id-mismatch.md) | P3 | RESOLVED |
| BUG-022 | [Rate limiting not implemented](bug-022-rate-limiting-not-implemented.md) | P1 | RESOLVED |
| BUG-023 | [Judge lacks ADR-001 resilience](bug-023-judge-lacks-adr001-resilience.md) | P2 | RESOLVED |
| BUG-024 | [Krippendorff alpha constraint too restrictive](bug-024-krippendorff-alpha-constraint-too-restrictive.md) | P2 | RESOLVED |
| BUG-025 | [Arbitration sensitivity hardcoded](bug-025-arbitration-sensitivity-hardcoded.md) | P3 | RESOLVED |
| BUG-026 | [Judge evidence truncation hardcoded](bug-026-judge-evidence-truncation-hardcoded.md) | P3 | RESOLVED |
| BUG-027 | [CLI prompt/version/view mismatch](bug-027-cli-prompt-version-view-mismatch.md) | P1 | RESOLVED |
| BUG-028 | [Google Gemini env var mismatch](bug-028-google-gla-env-var-mismatch.md) | P1 | RESOLVED |
| BUG-029 | [Export csv-only fails](bug-029-export-csv-only-fails.md) | P2 | RESOLVED |
| BUG-030 | [RUNS_PER_MODEL schema constraint mismatch](bug-030-runs-per-model-schema-constraint.md) | P2 | RESOLVED |
| BUG-031 | [DISAGREEMENT_RANGE_THRESHOLD unused](bug-031-disagreement-range-threshold-unused.md) | P2 | RESOLVED |
| BUG-032 | [Judge token usage missing](bug-032-judge-token-usage-missing.md) | P3 | RESOLVED |
| BUG-033 | [Resume run config mismatch](bug-033-resume-run-config-mismatch.md) | P3 | RESOLVED |
| BUG-034 | [.env.example missing arbitration keys](bug-034-env-example-missing-arbitration-thresholds.md) | P4 | RESOLVED |
| BUG-035 | [Sequential juror execution limits throughput](bug-035-sequential-juror-execution.md) | P2 | RESOLVED |
| BUG-036 | [JudgeItemResolution.item not validated](bug-036-judge-item-name-not-validated.md) | P3 | RESOLVED |
| BUG-037 | [Hardcoded arbitration parameters](bug-037-hardcoded-arbitration-params.md) | P4 | RESOLVED |
| BUG-038 | [No API key validation before live run](bug-038-no-api-key-validation-before-live-run.md) | P4 | RESOLVED |
| BUG-039 | [max_concurrency misleading for jurors](bug-039-max-concurrency-misleading-for-jurors.md) | P4 | RESOLVED |
| BUG-040 | [Missing PHQ-8 clinical rubric in prompts](bug-040-missing-phq8-rubric-in-prompts.md) | P0 | RESOLVED |
| BUG-041 | [Unused embedding_dialogue_view setting](bug-041-unused-embedding-dialogue-view-setting.md) | P3 | RESOLVED |
| BUG-042 | [Silent utterance truncation in preprocessing](bug-042-silent-utterance-truncation.md) | P2 | RESOLVED |
| BUG-047 | [Bare pass statement in runner](bug-047-runner-bare-pass-statement.md) | P5 | RESOLVED |

---

## Statistics

- **Total bugs**: 43
- **Resolved/Fixed**: 43
- **Open**: 0

---

## Next Bug Number

When filing new bugs, use: **BUG-048**

Place new bugs in `docs/_bugs/` (not `_archive`). Move to archive when resolved.
