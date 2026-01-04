# Troubleshooting

Common errors and how to fix them.

---

## API Errors

### Rate Limit Errors (429)

**Symptom**: `HTTPStatusError: 429 Too Many Requests`

**Cause**: Exceeding provider rate limits.

**Solutions**:

1. Reduce concurrency:
   ```bash
   --max-concurrency 10
   ```

2. Lower RPM settings:
   ```bash
   OPENAI_RPM=30
   ANTHROPIC_RPM=20
   ```

3. Wait and retry - the resilience layer will handle this automatically.

---

### Authentication Errors

**Symptom**: `AuthenticationError: Invalid API key`

**Cause**: Missing or invalid API key.

**Solutions**:

1. Check `.env` file exists:
   ```bash
   cat .env | grep API_KEY
   ```

2. Verify key is valid:
   ```bash
   curl https://api.openai.com/v1/models \
       -H "Authorization: Bearer $OPENAI_API_KEY"
   ```

3. Ensure no extra whitespace in `.env`:
   ```bash
   OPENAI_API_KEY=sk-...  # No spaces!
   ```

---

### Model Not Found

**Symptom**: `NotFoundError: model 'xxx' not found`

**Cause**: Invalid model ID.

**Solutions**:

1. Check model name spelling
2. Verify model is available in your region
3. Check provider documentation for current model names

---

## Validation Errors

### Schema Validation Failed

**Symptom**: `ValidationError: ... validation error for PHQ8Assessment`

**Cause**: LLM returned malformed JSON.

**Solutions**:

1. This is handled automatically by PydanticAI retries
2. If persistent, check prompt for issues
3. Try a different model

---

### Insufficient Evidence

**Symptom**: Many items flagged `insufficient_evidence: true`

**Cause**: Dialogue doesn't contain enough client statements about PHQ-8 items.

**Solutions**:

1. This is expected for some dialogues
2. The scoring still proceeds with best-effort scores
3. Check if corpus is appropriate for PHQ-8 scoring

---

## Checkpoint Issues

### Corrupted Checkpoint

**Symptom**: `sqlite3.DatabaseError: database disk image is malformed`

**Cause**: Interrupted write or disk issues.

**Solutions**:

1. Delete checkpoint and restart:
   ```bash
   rm data/outputs/checkpoint.db
   uv run vibe-check score-corpus ...
   ```

2. Note: This will re-process all dialogues

---

### Checkpoint Not Resuming

**Symptom**: Run starts from beginning despite checkpoint.

**Cause**: Different checkpoint path or thread ID mismatch.

**Solutions**:

1. Ensure checkpoint path is identical:
   ```bash
   # Must match exactly
   --checkpoint sqlite:///data/outputs/checkpoint.db
   ```

2. Check checkpoint has data:
   ```bash
   sqlite3 data/outputs/checkpoint.db ".tables"
   ```

---

### Run Configuration Mismatch

**Symptom**: `ValueError: run configuration mismatch`

**Cause**: Resuming a run with different `--prompt-version`, `--dialogue-view`, or other config.

**Solutions**:

1. Use the original configuration:
   ```bash
   # Check what config was used
   cat data/outputs/run_manifest.json | jq '.run_config'
   ```

2. Start a fresh run with new paths:
   ```bash
   --output data/outputs_v2 \
   --checkpoint sqlite:///data/outputs_v2/checkpoint.db
   ```

3. Force reset (loses existing progress):
   ```bash
   --force  # Resets ledger and starts fresh
   ```

---

## Diagnostics Failures

### Reliability Gate Failed

**Symptom**: `passes_reliability_gate: false`, Krippendorff α < 0.67

**Cause**: Jurors disagreeing too much.

**Solutions**:

1. Check per-item reliability:
   ```bash
   cat diagnostics.json | jq '.reliability.krippendorff_alpha_per_item'
   ```

2. Review prompts for problematic items
3. Consider adding more jurors
4. Lower arbitration thresholds to invoke judge more often

---

### Consistency Gate Failed

**Symptom**: `passes_consistency_gate: false`, Cronbach α < 0.70

**Cause**: PHQ-8 items not correlating internally.

**Solutions**:

1. Check item-total correlations:
   ```bash
   cat diagnostics.json | jq '.consistency.item_total_correlations'
   ```

2. Items with low correlation may need prompt improvements

---

### Separation Gate Failed

**Symptom**: `passes_separation_gate: false`

**Cause**: MDD scores not higher than Control.

**Solutions**:

1. Check means:
   ```bash
   cat diagnostics.json | jq '{mdd: .separation.mdd_mean, control: .separation.control_mean}'
   ```

2. Verify corpus condition labels are correct
3. Check if corpus has sufficient MDD/Control cases

---

### Arbitration Gate Failed

**Symptom**: `passes_arbitration_gate: false`, rate > 30%

**Cause**: Too many items need judge arbitration.

**Solutions**:

1. Check per-item rates:
   ```bash
   cat diagnostics.json | jq '.arbitration.per_item_rate'
   ```

2. Increase thresholds to reduce arbitration:
   ```bash
   ARBITRATION_MAX_PROB_THRESHOLD=0.50
   ARBITRATION_ENTROPY_THRESHOLD=1.5
   ```

3. Review prompts for high-rate items

---

## Export Issues

### Empty Export

**Symptom**: `vibe_check_labels.jsonl` is empty.

**Cause**: `scored.jsonl` has no records.

**Solutions**:

1. Check scored file:
   ```bash
   wc -l data/outputs/scored.jsonl
   ```

2. Verify scoring completed successfully

---

### Validation Failed

**Symptom**: `validate-export` returns non-zero.

**Cause**: Export records don't match schema.

**Solutions**:

1. Check validation report:
   ```bash
   cat validation_report.json | python -m json.tool
   ```

2. Re-run export from valid `scored.jsonl`

---

## Performance Issues

### Slow Processing

**Symptom**: Processing takes much longer than expected.

**Solutions**:

1. Increase concurrency (if rate limits allow):
   ```bash
   --max-concurrency 50
   ```

2. Use faster models for jurors
3. Check network latency to providers

---

### High Memory Usage

**Symptom**: Process uses excessive memory.

**Solutions**:

1. Reduce concurrency:
   ```bash
   --max-concurrency 10
   ```

2. Process in batches with `--limit`

---

## Getting Help

If issues persist:

1. Check logs for detailed error messages
2. Verify all prerequisites are met
3. Review [Configuration](configuration.md) for settings
4. Check provider status pages for outages

---

## Quick Fixes

| Issue | Quick Fix |
|-------|-----------|
| Rate limits | `--max-concurrency 10` |
| Auth errors | Check `.env` for API keys |
| Checkpoint issues | Delete checkpoint, restart |
| Validation errors | Handled automatically |
| Slow processing | Increase concurrency |
