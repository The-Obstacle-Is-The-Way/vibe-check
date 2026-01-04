# Bug Tracker

## Active Bugs

No open bugs.

---

## Recently Resolved

| ID | Severity | Status | Title |
|----|----------|--------|-------|
| BUG-027 | P1 | resolved | [CLI `--prompt-version` / `--dialogue-view` can desync from live agent prompts](../_archive/bugs/bug-027-cli-prompt-version-view-mismatch.md) |
| BUG-028 | P1 | resolved | [Live Gemini jurors env var mismatch](../_archive/bugs/bug-028-google-gla-env-var-mismatch.md) |
| BUG-029 | P2 | resolved | [`vibe-check export --format csv` fails](../_archive/bugs/bug-029-export-csv-only-fails.md) |
| BUG-030 | P2 | resolved | [`RUNS_PER_MODEL` > 2 breaks scoring](../_archive/bugs/bug-030-runs-per-model-schema-constraint.md) |
| BUG-031 | P2 | resolved | [`DISAGREEMENT_RANGE_THRESHOLD` is exposed but unused](../_archive/bugs/bug-031-disagreement-range-threshold-unused.md) |
| BUG-032 | P3 | resolved | [Token usage totals omit judge calls](../_archive/bugs/bug-032-judge-token-usage-missing.md) |
| BUG-033 | P3 | resolved | [Resume can silently mix runs](../_archive/bugs/bug-033-resume-run-config-mismatch.md) |
| BUG-034 | P4 | resolved | [`.env.example` missing arbitration threshold keys](../_archive/bugs/bug-034-env-example-missing-arbitration-thresholds.md) |

---

## Archived Bugs

All resolved bugs are in [`docs/_archive/bugs/`](../_archive/bugs/index.md).

| Range | Count | Description |
|-------|-------|-------------|
| BUG-001 to BUG-013 | 13 | Initial development bugs |
| BUG-014 to BUG-026 | 13 | Post-implementation bug hunt |
| BUG-027 to BUG-034 | 8 | CI/run/export hardening |

**Total resolved**: 34 bugs

---

## Filing New Bugs

1. Use the next available number: **BUG-035**
2. Create file in this directory: `BUG-NNN-short-description.md`
3. Include: Severity, Status, Date, Summary, Root Cause, Fix
4. When resolved, move to `docs/_archive/bugs/`
