# Scoring a Corpus

Complete walkthrough of running vibe-check on the full SQPsychConv dataset.

---

## Prerequisites

1. API keys configured (see [Configuration](configuration.md))
2. SQPsychConv dataset available
3. Sufficient API quota for 2,090 dialogues

---

## Estimated Cost

For full 2,090 dialogues with 6 jurors + arbitration (~30%):

| Component | Calls | Input Tokens | Output Tokens | Est. Cost |
|-----------|-------|--------------|---------------|-----------|
| GPT-5.2 Juror (×2 runs) | 4,180 | ~8.3M | ~1.7M | ~$225 |
| Sonnet-4.5 Juror (×2 runs) | 4,180 | ~8.3M | ~1.7M | ~$50 |
| Gemini-3-Pro Juror (×2 runs) | 4,180 | ~8.3M | ~1.7M | ~$19 |
| **Juror Subtotal** | 12,540 | ~24.9M | ~5.0M | **~$293** |
| Opus-4.5 Judge (per item) | ~1,881* | ~4.7M | ~0.6M | ~$113 |
| **TOTAL** | | | | **~$406** |

*With 50% buffer: **~$609***

> **Note**: Judge calls assume ~30% of dialogues arbitrated × ~3 contested items per arbitrated dialogue. If arbitration triggers `__total__` (8 items), judge calls can reach ~5,000 and costs scale accordingly.

See [Preflight Checklist](../preflight-checklist/index.md) for more detailed cost breakdown.

---

## Step 1: Configure Environment

```bash
# Create .env file
cat > .env << 'EOF'
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GOOGLE_API_KEY=...
EOF
```

---

## Step 2: Test Run (Dry)

Before spending money, verify everything works:

```bash
uv run vibe-check score-corpus \
    --input data/sqpsychconv/qwen-2.5 \
    --checkpoint sqlite:///data/outputs/checkpoint.db \
    --output data/outputs \
    --limit 10
```

Check the output:

```bash
wc -l data/outputs/scored.jsonl
# Should show: 10

head -1 data/outputs/scored.jsonl | python -m json.tool | head -20
```

---

## Step 3: Production Run

```bash
uv run vibe-check score-corpus \
    --input data/sqpsychconv/qwen-2.5 \
    --checkpoint sqlite:///data/outputs/checkpoint.db \
    --output data/outputs \
    --live \
    --prompt-version v1.0.0
```

### Flags Explained

| Flag | Description |
|------|-------------|
| `--input` | Path to HuggingFace dataset or CSV |
| `--checkpoint` | SQLite database for checkpointing |
| `--output` | Directory for output files |
| `--live` | Use real LLM APIs (costs money!) |
| `--prompt-version` | Label embedded in outputs |

---

## Step 4: Monitor Progress

The runner does not print a progress bar. Progress is tracked via `ledger.sqlite` (job status) and `rows/` (one JSON per completed dialogue).

---

## Step 5: Handle Interruptions

If the run is interrupted:

```bash
# Just run the same command again
uv run vibe-check score-corpus \
    --input data/sqpsychconv/qwen-2.5 \
    --checkpoint sqlite:///data/outputs/checkpoint.db \
    --output data/outputs \
    --live
```

Resume uses two SQLite databases:
- `ledger.sqlite`: which dialogues are `done` / `running` / `failed`, plus token usage totals
- `--checkpoint` DB: LangGraph state checkpoints per `file_id`

### Resume Safety: Dataset Fingerprinting

The runner computes a **content-sensitive dataset fingerprint** by hashing `file_id + dialogue SHA-256` for all dialogues. This prevents accidental resume into a modified corpus:

```python
# Fingerprint includes content, not just IDs
dataset_rows = sorted(
    f"{d.file_id}:{hashlib.sha256(d.dialogue.encode()).hexdigest()}"
    for d in corpus
)
fingerprint = hashlib.sha256("\n".join(dataset_rows).encode()).hexdigest()
```

If the corpus changes (even with same file_ids), the fingerprint changes and resume is blocked unless you use `--force`.

---

## Step 6: Verify Outputs

After completion:

```bash
# Check output count
wc -l data/outputs/scored.jsonl
# Should show: 2090

# Check manifest
cat data/outputs/run_manifest.json | python -m json.tool
```

---

## Output Files

| File | Description |
|------|-------------|
| `scored.jsonl` | One `AggregatedPHQ8` per line (final output) |
| `run_manifest.json` | Run metadata, counts, and token usage totals |
| `ledger.sqlite` | Processing ledger tracking job statuses |
| `rows/` | Individual row JSON files (intermediate outputs) |
| `checkpoint.db` | LangGraph checkpoints (at checkpoint path) |

### scored.jsonl Record

```json
{
  "file_id": "active436",
  "condition": "mdd",
  "final_item_scores": {"anhedonia": 2, "depressed_mood": 3, ...},
  "final_total_score": 15,
  "final_severity_bucket": "15-19",
  "triggered_arbitration": true,
  "juror_reports": [...],
  "judge_resolution": {...}
}
```

### run_manifest.json

```json
{
  "dialogues_total": 2090,
  "completed": 2090,
  "failed": 0,
  "arbitration_rate": 0.28,
  "rows_written": 2090,
  "arbitrated_dialogues": 585,
  "counts_by_condition": {"mdd": 1045, "control": 1045},
  "counts_by_split": {"train": 1464, "dev": 313, "test": 313},
  "token_usage_totals": {
    "input_tokens": 12500000,
    "output_tokens": 450000,
    "reasoning_tokens": 0,
    "total_tokens": 12950000
  }
}
```

---

## Advanced Options

### Limit Concurrency

The `--max-concurrency` flag controls how many dialogues are processed concurrently. Within each dialogue, jurors run in parallel (default: 6 jurors = up to 6 concurrent API calls per dialogue, rate-limited per provider).

```bash
uv run vibe-check score-corpus \
    --input data/sqpsychconv/qwen-2.5 \
    --checkpoint sqlite:///data/outputs/checkpoint.db \
    --output data/outputs \
    --live \
    --max-concurrency 10
```

This allows up to 10 dialogues to be scored concurrently. Adjust based on API rate limits and memory constraints.

### Use Client-Only View

```bash
uv run vibe-check score-corpus \
    --input data/sqpsychconv/qwen-2.5 \
    --checkpoint sqlite:///data/outputs/checkpoint.db \
    --output data/outputs \
    --live \
    --dialogue-view client_only
```

---

## Next Steps

After scoring completes:

1. [Run Diagnostics](running-diagnostics.md) - Validate quality
2. [Export Labels](exporting-labels.md) - Create public format

---

## Troubleshooting

See [Troubleshooting](troubleshooting.md) for common issues:
- Rate limit errors
- API key problems
- Checkpoint recovery
