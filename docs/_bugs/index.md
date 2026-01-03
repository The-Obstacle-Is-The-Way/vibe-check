# Bug Tracker

## Active Bugs

| ID | Severity | Status | Title |
|----|----------|--------|-------|
| BUG-028 | P1 | open | [Live Gemini jurors fail: `google-gla` expects `GEMINI_API_KEY` (not `GOOGLE_API_KEY`)](bug-028-google-gla-env-var-mismatch.md) |
| BUG-029 | P2 | open | [`vibe-check export --format csv` fails (JSONL validation runs unconditionally)](bug-029-export-csv-only-fails.md) |
| BUG-030 | P2 | open | [`RUNS_PER_MODEL` > 2 breaks scoring (`PHQ8Report.run_number` is capped at 2)](bug-030-runs-per-model-schema-constraint.md) |
| BUG-031 | P2 | open | [`DISAGREEMENT_RANGE_THRESHOLD` is exposed but unused (hardcoded range threshold)](bug-031-disagreement-range-threshold-unused.md) |
| BUG-032 | P3 | open | [Token usage totals omit judge calls (manifest undercounts arbitration cost)](bug-032-judge-token-usage-missing.md) |
| BUG-033 | P3 | open | [Resume can silently mix runs (no run-config hash / ledger reuse footgun)](bug-033-resume-run-config-mismatch.md) |
| BUG-034 | P4 | open | [`.env.example` missing arbitration threshold keys](bug-034-env-example-missing-arbitration-thresholds.md) |

---

## Recently Resolved

| ID | Severity | Status | Title |
|----|----------|--------|-------|
| BUG-027 | P1 | resolved | [CLI `--prompt-version` / `--dialogue-view` can desync from live agent prompts](bug-027-cli-prompt-version-view-mismatch.md) |

---

## Archived Bugs

All resolved bugs are in [`docs/_archive/bugs/`](../_archive/bugs/index.md).

| Range | Count | Description |
|-------|-------|-------------|
| BUG-001 to BUG-013 | 13 | Initial development bugs |
| BUG-014 to BUG-026 | 13 | Post-implementation bug hunt |
| BUG-027 | 1 | CLI/Settings desync |

**Total resolved**: 27 bugs

---

## Filing New Bugs

1. Use the next available number: **BUG-035**
2. Create file in this directory: `BUG-NNN-short-description.md`
3. Include: Severity, Status, Date, Summary, Root Cause, Fix
4. When resolved, move to `docs/_archive/bugs/`
