# SQPsychConv Preprocessing & Schema Audit (Qwen-2.5 Export)

Date: 2026-01-05

This document is a paranoid pre-run audit of the SQPsychConv corpus files in this repo, focused on:
1) schema compatibility (CSV vs HF Arrow),
2) preprocessing hazards that could break scoring or bias labels,
3) fixes implemented before running a paid labeling job.

## Corpus Files (What’s On Disk)

- CSV export: `data/sqpsychconv/qwen-2.5-FULL-EXPORT.csv` (~12MB, 2,090 dialogues)
  - Columns: `file_id`, `condition`, `client_model`, `therapist_model`, `dialogue_chars`, `dialogue`
- HF Arrow dataset: `data/sqpsychconv/qwen-2.5/` (DatasetDict with `train`/`test`)
  - Columns: `file_id`, `condition`, `client_model`, `therapist_model`, `dialogue`

## SSOT Schema (What The Code Actually Loads)

The runtime schema is `vibe_check.schemas.input.SQPsychConvDialogue`:
- required: `file_id`, `condition` (`mdd|control`), `client_model`, `therapist_model`, `dialogue`
- computed: `computed_split` (deterministic hash split)

Notes:
- The CSV-only column `dialogue_chars` is intentionally ignored by `vibe_check.data.loader.load_corpus()`.
- When loading a HF dataset directory, we iterate all splits and **recompute** `computed_split`; we do not trust/preserve the upstream `train/test` split.

## Ingestion Path (CSV vs Arrow)

- Loader: `vibe_check.data.loader.load_corpus()`
  - `--input ...csv` → `csv.DictReader` (UTF-8, multiline fields supported)
  - `--input .../dataset_dir` → `datasets.load_from_disk()` (HF Arrow)
  - `condition` is validated strictly (`mdd`/`control` only)
  - `file_id` collisions are rejected if dialogue text differs

## Preprocessing Path (What Jurors Actually See)

- Parsing: `vibe_check.preprocessing.extractor.parse_utterances_with_diagnostics()`
  - Expects line-level speaker prefixes: `Therapist:` / `Client:`
- Views: `vibe_check.preprocessing.extractor.preprocess_dialogue()`
  - `client_only_text`: concatenated client utterances (no speaker tags)
  - `client_qa_text`: therapist prompt + client answers (speaker tags)
- Scoring uses `scoring_text` only (`client_only_text` or `client_qa_text`), not `file_id` or `condition`.

## Findings (From First Principles)

### 1) The corpus contains generation artifacts that must be stripped

Observed in the raw CSV:
- `[/END]` appears in **every** dialogue (2,090/2,090)
- template placeholders / scheduling scaffolding appear frequently (e.g., `[insert date]`, `[Next week]`, `[Please confirm the date and time.]`)
- a small number of dialogues contain bracketed stage directions (e.g., `[Sigh]`) and chunk markers (e.g., `[19/20]`)

Status: fixed via deterministic stripping (SPEC-12 + follow-up hardening).

### 2) Unicode punctuation is everywhere (and is normal)

2,089/2,090 dialogues contain the curly apostrophe `’` (U+2019).

Status: expected; code treats text as UTF-8 and artifact stripping patterns explicitly match both straight and curly apostrophes.

### 3) `file_id` encodes the class label (do not leak it)

In this corpus:
- `file_id` starting with `control...` is always `condition=control`
- `file_id` starting with `active...` / `not_active...` is always `condition=mdd`

Status: safe for current pipeline because `file_id` is not included in juror/judge prompts; **dangerous** if used as an input feature in any downstream ML training.

### 4) Resume safety: dataset fingerprint must include content, not just IDs

If a corpus changes but keeps the same `file_id`s, a fingerprint based only on IDs can allow a resume into the wrong dataset.

Status: fixed by hashing `file_id + dialogue sha256` (see below).

## Fixes Implemented Before Pilot

- Expanded deterministic artifact stripping so `client_only_text`/`client_qa_text` contain **no bracket artifacts** for this corpus.
  - Implementation: `src/vibe_check/constants.py` + `src/vibe_check/preprocessing/extractor.py`
  - Coverage test: `tests/unit/test_extractor.py`
- Made run `dataset_fingerprint` content-sensitive (prevents accidental resume across dataset edits).
  - Implementation: `src/vibe_check/run/runner.py`

## Suggested Preflight Checks (Cheap)

- Validate corpus integrity:
  - `python -c "from vibe_check.data import load_corpus, validate_corpus; print(validate_corpus(load_corpus('data/sqpsychconv/qwen-2.5')).model_dump())"`
- Run a small offline (fake) pilot to validate the full pipeline without spending money:
  - `vibe-check score-corpus --input data/sqpsychconv/qwen-2.5 --checkpoint checkpoints/pilot.sqlite --output runs/pilot --limit 5`
