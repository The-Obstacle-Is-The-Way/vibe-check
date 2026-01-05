# Production Run Preflight Checklist

> **Purpose**: Verify all prerequisites before running `vibe-check score-corpus` on live APIs.

---

## 1. API Credits (Recommended Minimums)

Based on the SQPsychConv qwen-2.5 corpus (2,090 dialogues):

| Provider | Minimum | With 50% Buffer | Notes |
|----------|---------|-----------------|-------|
| **OpenAI** | $40 | $60 | GPT model juror (2 runs) |
| **Anthropic** | $580 | $870 | Claude Sonnet juror + Opus judge |
| **Google** | $20 | $30 | Gemini juror (2 runs) |

**Total estimate**: ~$640 (+ 50% buffer = ~$960)

### Cost Breakdown

| Component | Calls | Input Tokens | Output Tokens | Est. Cost |
|-----------|-------|--------------|---------------|-----------|
| GPT Juror (×2 runs) | 4,180 | ~8.8M | ~1.7M | ~$39 |
| Claude Sonnet Juror (×2 runs) | 4,180 | ~8.8M | ~1.7M | ~$51 |
| Gemini Juror (×2 runs) | 4,180 | ~8.8M | ~1.7M | ~$19 |
| Opus Judge (~30% arb, 8 items) | ~5,000 | ~10M | ~5M | ~$527 |

> **Note**: Judge costs dominate. Consider using `--limit 100` for initial validation runs.

---

## 2. Environment Verification

### 2.1 API Keys

```bash
# Check .env file exists
cat .env | grep -E "^(OPENAI|ANTHROPIC|GOOGLE)_API_KEY" | sed 's/=.*/=***/'
```

**Expected output**:
```
OPENAI_API_KEY=***
ANTHROPIC_API_KEY=***
GOOGLE_API_KEY=***
```

### 2.2 Python Environment

```bash
# Verify vibe-check is installed
uv run vibe-check --help

# Verify all dependencies
uv sync
```

### 2.3 Model Availability

```bash
# Quick API connectivity test (costs ~$0.01)
uv run python -c "
from openai import OpenAI
from anthropic import Anthropic
import google.generativeai as genai
import os

# OpenAI
client = OpenAI()
r = client.chat.completions.create(model='gpt-4o-mini', messages=[{'role':'user','content':'hi'}], max_tokens=5)
print(f'✓ OpenAI: {r.model}')

# Anthropic
client = Anthropic()
r = client.messages.create(model='claude-3-5-haiku-latest', messages=[{'role':'user','content':'hi'}], max_tokens=5)
print(f'✓ Anthropic: {r.model}')

# Google
genai.configure(api_key=os.environ['GOOGLE_API_KEY'])
model = genai.GenerativeModel('gemini-1.5-flash')
r = model.generate_content('hi')
print(f'✓ Google: gemini ok')
"
```

---

## 3. Data Verification

### 3.1 Corpus Loading

```bash
uv run python -c "
from vibe_check.data import load_corpus

corpus = load_corpus('data/sqpsychconv/qwen-2.5')
print(f'Dialogues: {len(corpus)}')
print(f'MDD: {sum(1 for d in corpus if d.condition==\"mdd\")}')
print(f'Control: {sum(1 for d in corpus if d.condition==\"control\")}')
"
```

**Expected**: 2,090 dialogues (912 MDD, 1,178 Control)

### 3.2 Preprocessing Sanity Check

```bash
uv run python -c "
from vibe_check.data import load_corpus, preprocess_dialogue

corpus = load_corpus('data/sqpsychconv/qwen-2.5')
sample = corpus[0]
views = preprocess_dialogue(sample)

print(f'file_id: {sample.file_id}')
print(f'condition: {sample.condition}')
print(f'client_qa chars: {len(views.client_qa_text)}')
print(f'truncated_utterance_count: {views.truncated_utterance_count}')
"
```

---

## 4. Test Suite

### 4.1 Full Test Suite (Required)

```bash
uv run pytest -q
```

**Expected**: 141 passed, 1 skipped

### 4.2 Offline Dry Run

```bash
# Score 5 dialogues with fake jurors (no API calls)
# NOTE: Do NOT pass `--live`; fake mode is the default.
uv run vibe-check score-corpus \
  --input data/sqpsychconv/qwen-2.5 \
  --output data/outputs/preflight-test \
  --checkpoint sqlite:///data/checkpoints/preflight-test.db \
  --limit 5

# Check outputs
ls data/outputs/preflight-test/
```

**Expected files**: `rows/`, `scored.jsonl`, `run_manifest.json`

---

## 5. Production Run Commands

### 5.1 Validation Run (Recommended First)

```bash
# Score 50 dialogues live (~$15-20)
uv run vibe-check score-corpus \
  --input data/sqpsychconv/qwen-2.5 \
  --output data/outputs/validation-run \
  --checkpoint sqlite:///data/checkpoints/validation.db \
  --limit 50 \
  --max-concurrency 5 \
  --live
```

### 5.2 Full Production Run

```bash
# Score entire corpus (~$640)
uv run vibe-check score-corpus \
  --input data/sqpsychconv/qwen-2.5 \
  --output data/outputs/production-run \
  --checkpoint sqlite:///data/checkpoints/production.db \
  --max-concurrency 50 \
  --live

# Run diagnostics after completion
uv run vibe-check diagnostics \
  --scored data/outputs/production-run/scored.jsonl \
  --output data/outputs/production-run/diagnostics.json \
  --format json \
  --strict

# Export public labels
uv run vibe-check export \
  --input data/outputs/production-run/scored.jsonl \
  --output-dir data/outputs/production-run/public \
  --format jsonl
```

---

## 6. Monitoring During Run

### 6.1 Check Progress

```bash
# View run manifest (updates live)
cat data/outputs/production-run/run_manifest.json | python -m json.tool

# Check ledger status
uv run python -c "
from vibe_check.run.ledger import JobLedger
from pathlib import Path

with JobLedger(Path('data/outputs/production-run/ledger.sqlite')) as ledger:
    all_ids = ledger.list_all()
    done = sum(1 for fid in all_ids if ledger.get_status(fid) == 'done')
    failed = sum(1 for fid in all_ids if ledger.get_status(fid) == 'failed')
    running = sum(1 for fid in all_ids if ledger.get_status(fid) == 'running')
    pending = sum(1 for fid in all_ids if ledger.get_status(fid) == 'pending')
    print(f'Done: {done} | Failed: {failed} | Running: {running} | Pending: {pending}')
"
```

### 6.2 Resume After Interruption

Runs are resumable. Just re-run the same command:

```bash
# Same command resumes from last checkpoint
uv run vibe-check score-corpus \
  --input data/sqpsychconv/qwen-2.5 \
  --output data/outputs/production-run \
  --checkpoint sqlite:///data/checkpoints/production.db \
  --max-concurrency 50 \
  --live
```

---

## 7. Post-Run Validation

### 7.1 Diagnostics Report

```bash
uv run vibe-check diagnostics \
  --scored data/outputs/production-run/scored.jsonl \
  --output data/outputs/production-run/diagnostics.json \
  --format json \
  --strict
```

**Quality gates** (from SPEC-07):
- Krippendorff's α ≥ 0.67
- Cronbach's α ≥ 0.70
- Arbitration rate ≤ 30%
- Cohen's d ≥ 0.5 (MDD vs Control separation)

### 7.2 Export Validation

```bash
uv run vibe-check validate-export \
  --input data/outputs/production-run/public/vibe_check_labels.jsonl
```

---

## 8. Troubleshooting

| Issue | Cause | Fix |
|-------|-------|-----|
| Rate limit errors | Too many concurrent calls | Reduce `--max-concurrency` |
| API key invalid | Wrong key in .env | Check provider dashboard |
| Run config mismatch | Changed params mid-run | Use `--force` or new output dir |
| High arbitration rate | Unclear dialogues | Expected for ambiguous cases |

---

## Checklist Summary

- [ ] API credits loaded (OpenAI $60, Anthropic $870, Google $30)
- [ ] `.env` file has all 3 API keys
- [ ] `uv run pytest` passes (141 tests)
- [ ] Offline dry run completes successfully
- [ ] Validation run (50 dialogues) completes without errors
- [ ] Ready for production run

---

*Last updated: 2026-01-05*
