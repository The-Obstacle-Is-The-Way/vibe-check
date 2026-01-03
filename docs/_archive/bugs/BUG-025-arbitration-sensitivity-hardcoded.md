# BUG-016: Arbitration sensitivity parameters are hardcoded

**Severity**: P3 (Research Flexibility)
**Status**: RESOLVED
**Date**: 2026-01-03
**Component**: Aggregation / Arbitration
**Resolution**: Added parameters to Settings and plumbed them through the runner to aggregation logic.

## Summary

The logic that triggers judge arbitration relies on specific thresholds defined as default arguments in `vibe_check.aggregation.disagreement.should_arbitrate_item`:

- `max_prob_threshold`: 0.60
- `entropy_threshold`: 1.2
- `clinical_ambiguity_band`: (0.4, 0.6)

These values are not exposed in `Settings` or passed down from the runner. This makes it impossible to tune the "sensitivity" of the judge without modifying library code.

## Impact

Researchers cannot easily experiment with "stricter" or "looser" arbitration triggers.

## Fix

1. Add these parameters to `Settings` (e.g., `arbitration_max_prob_threshold`, `arbitration_entropy_threshold`).
2. Pass them through `runner.py` -> `build_single_dialogue_graph` -> `aggregate_node` -> `aggregate_reports` -> `aggregate_votes` -> `should_arbitrate_item`.
