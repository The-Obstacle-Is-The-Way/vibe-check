# BUG-044: Over-Parameterized `score_corpus_async()` Function

| Field | Value |
|-------|-------|
| **Severity** | P4 (Low - Code Smell) |
| **Status** | resolved |
| **Date** | 2026-01-04 |
| **Component** | `run/runner.py` |
| **Impact** | Maintainability, readability, error-prone call sites |

---

## Summary

The batch runner entrypoint (`score_corpus()` / `score_corpus_async()`) takes **~19 parameters**, making it error-prone and difficult to evolve.

This is a maintainability issue (not a correctness bug), but it increases the chance of misconfigured runs and inconsistent manifest recording.

---

## Current State

`src/vibe_check/run/runner.py:83-104`:

```python
async def score_corpus_async(
    *,
    input_path: str | Path,
    output_dir: Path,
    checkpoint_db: str,
    jurors: Sequence[Juror],
    judge_item: JudgeItemFn,
    limit: int | None = None,
    prompt_version: str,
    dialogue_view: DialogueViewName = "client_qa",
    max_concurrency: int = 1,
    fail_fast: bool = False,
    force: bool = False,
    dirichlet_alpha: float = 0.5,
    disagreement_range_threshold: int = 2,
    arbitration_total_std_threshold: float = 2.0,
    arbitration_max_prob_threshold: float = 0.60,
    arbitration_entropy_threshold: float = 1.2,
    clinical_ambiguity_band_low: float = 0.4,
    clinical_ambiguity_band_high: float = 0.6,
    insufficient_evidence_threshold: int = 2,
) -> None:
```

**Problems**:
1. Hard to remember parameter order
2. Easy to accidentally swap parameters
3. Call sites become walls of keyword arguments
4. Adding new parameters makes it worse

---

## Fix

### Expand and use the existing `RunConfig` dataclass (Recommended)

`src/vibe_check/run/config.py` already defines `RunConfig`, but it currently only covers paths + a few knobs. Expand it to include the aggregation parameters and execution flags, then update `score_corpus()` / `score_corpus_async()` to accept a single config object.

This keeps call sites small, makes it easier to persist a complete run manifest, and reduces accidental mismatches between CLI args, Settings, and the runner.

```python
# run/config.py
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

@dataclass(frozen=True)
class RunConfig:
    """Configuration for a scoring run."""

    output_dir: Path
    prompt_version: str
    dialogue_view: Literal["client_qa", "client_only"] = "client_qa"
    max_concurrency: int = 10
    fail_fast: bool = False
    force: bool = False

    # Aggregation parameters
    dirichlet_alpha: float = 0.5
    disagreement_range_threshold: int = 2
    arbitration_total_std_threshold: float = 2.0
    arbitration_max_prob_threshold: float = 0.60
    arbitration_entropy_threshold: float = 1.2
    clinical_ambiguity_band_low: float = 0.4
    clinical_ambiguity_band_high: float = 0.6
    insufficient_evidence_threshold: int = 2

    @classmethod
    def from_settings(cls, settings: Settings, output_dir: Path) -> "RunConfig":
        """Create config from Settings with output_dir override."""
        return cls(
            output_dir=output_dir,
            prompt_version=settings.prompt_version,
            dialogue_view=settings.scoring_dialogue_view,
            max_concurrency=settings.max_concurrent_dialogues,
            dirichlet_alpha=settings.dirichlet_alpha,
            # ... etc
        )
```

### Simplified function signature

```python
async def score_corpus_async(
    *,
    jurors: Sequence[Juror],
    judge_item: JudgeItemFn,
    config: RunConfig,
) -> None:
```

**3 parameters** instead of ~19.

---

## Test Plan

1. Create `RunConfig` dataclass
2. Update `score_corpus_async()` to accept config
3. Update CLI to build config from args
4. Verify all tests pass

---

## Related

- Clean Code principle: "Functions should have few arguments" (ideally 0-3)
- `run/config.py` already exists but is underutilized

---

## Resolution (Implemented)

Expanded `RunConfig` in `src/vibe_check/run/config.py` and refactored `src/vibe_check/run/runner.py` so `score_corpus()`/`score_corpus_async()` take a single `config` object, with the CLI constructing `RunConfig` and persisting the full configuration into the run manifest for reproducibility.
