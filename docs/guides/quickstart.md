# Quickstart

Get vibe-check running in 5 minutes.

---

## 1. Install Dependencies

```bash
# Clone the repository
git clone <repo-url> vibe-check
cd vibe-check

# Install with uv
uv sync
```

---

## 2. Configure API Keys (Optional for Dry Run)

Create a `.env` file:

```bash
# .env
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GOOGLE_API_KEY=...
```

---

## 3. Verify Dataset

Ensure SQPsychConv is available:

```bash
ls data/sqpsychconv/qwen-2.5/
# Should show: train/ test/ dataset_dict.json
```

---

## 4. Run a Dry Test (No API Calls)

```bash
uv run vibe-check score-corpus \
    --input data/sqpsychconv/qwen-2.5 \
    --checkpoint sqlite:///data/outputs/checkpoint.db \
    --output data/outputs \
    --limit 5
```

This runs with **fake jurors** (deterministic, no API calls).

---

## 5. Verify Output

```bash
cat data/outputs/scored.jsonl | head -1 | python -m json.tool
```

You should see a full `AggregatedPHQ8` record with:
- `final_item_scores`
- `final_total_score`
- `juror_reports`
- etc.

---

## 6. Run Diagnostics

```bash
uv run vibe-check diagnostics \
    --scored data/outputs/scored.jsonl \
    --output data/outputs/diagnostics.json
```

---

## 7. Export Labels

```bash
uv run vibe-check export \
    --input data/outputs/scored.jsonl \
    --output-dir data/exports
```

---

## Next Steps

- [Scoring a Corpus](scoring-corpus.md) - Full production run
- [Configuration](configuration.md) - All settings
- [Troubleshooting](troubleshooting.md) - Common issues

---

## Quick Command Reference

| Command | Purpose |
|---------|---------|
| `vibe-check score-corpus` | Score dialogues |
| `vibe-check diagnostics` | Validate quality |
| `vibe-check export` | Create public labels |
| `vibe-check validate-export` | Validate export file |
