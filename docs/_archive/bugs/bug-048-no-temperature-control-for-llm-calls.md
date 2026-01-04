# BUG-048: No Temperature Control for LLM Calls

| Field | Value |
|-------|-------|
| **Severity** | P1 (High - Research Reproducibility) |
| **Status** | resolved |
| **Date** | 2026-01-04 |
| **Component** | `scoring/agent.py`, `judge/agent.py`, `run/factory.py` |
| **Impact** | Non-reproducible scores, research validity |

---

## Summary

**No explicit LLM sampling/inference parameters are specified anywhere in the codebase.** All LLM calls use provider/model defaults (temperature/top_p/max_tokens/timeout/etc.), which introduces unnecessary randomness into clinical scoring.

This is a **critical research reproducibility issue**.

### Spec-Implementation Gap

The master spec **explicitly mentions temperature** but the implementation ignores it:

| Location | Spec Says | Implementation |
|----------|-----------|----------------|
| `docs/_archive/research/spec-vibe-check.md:49` | "LLM JSON failures can be deterministic at temperature=0" | No temperature set |
| `docs/_archive/research/spec-vibe-check.md:1643` | "Do not retry blindly at temperature=0" | No temperature set |
| `docs/_archive/research/spec-vibe-check.md:1683` | `call_model(..., temperature=0.1)` | No temperature passed |

**The spec acknowledges temperature matters but the code doesn't implement it.**

---

## Evidence

```bash
$ grep -r "temperature\|top_p\|top_k\|max_tokens" src/
# NO MATCHES
```

### Agent Construction (No Model Settings)

`scoring/agent.py:40-49`:
```python
return Agent(
    model=model,
    output_type=PHQ8Assessment,
    retries=retries,
    system_prompt=build_juror_system_prompt(...),
    # ← NO temperature, NO model_settings
)
```

`judge/agent.py` - Same pattern.

---

## Why This Matters

### 1. Non-Reproducibility

| Temperature | Behavior |
|-------------|----------|
| 0.0 | Most stable / lowest randomness (not strictly deterministic) |
| 0.3-0.7 | Low variability (reasonable for creative tasks) |
| provider default | Potential variability (different output each run) |

With temperature=1.0:
- Same dialogue scored twice → potentially different PHQ-8 scores
- Cannot reproduce results from a previous run
- "Consensus" may be artificially inflated by random agreement

### 2. Research Validity

Clinical scoring should be **deterministic**:
- Score reflects dialogue content, not random sampling
- Inter-rater reliability metrics become meaningful
- Results can be audited and verified

### 3. Cross-Model Consistency

Different providers have different defaults:
- OpenAI: temperature=1.0 by default
- Anthropic: temperature=1.0 by default
- Google: temperature varies by model

Without explicit control, jurors from different providers may have different "personalities."

---

## Recommended Settings for Clinical Scoring

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| `temperature` | **0.0** | Most stable scoring |
| `top_p` | 1.0 | Keep nucleus sampling wide; rely on temperature |
| `max_tokens` | 2000 | Sufficient for JSON response |
| `timeout` | 60.0 | Avoid indefinite hangs |

### Alternative: Low Temperature with Seed

Some research prefers `temperature=0.1` with an explicit seed for controlled variance:
```python
model_settings={"temperature": 0.1, "seed": 42}
```

This allows studying scoring distribution while maintaining reproducibility.

---

## Fix

### Option A: Add to Settings (Recommended)

`settings.py`:
```python
# Model Inference Settings
llm_temperature: float = 0.0
llm_max_tokens: int = 2000
llm_seed: int | None = None  # Optional: for reproducible randomness
```

### Option B: Configure in Agent Builder

`scoring/agent.py`:
```python
from pydantic_ai import Agent
from pydantic_ai.settings import ModelSettings

def build_juror_agent(
    *,
    model: Model | KnownModelName | str | None,
    prompt_version: str,
    view_name: str = "client_qa",
    instructions: str | None = None,
    retries: int = 2,
    temperature: float = 0.0,  # ← NEW
    max_tokens: int = 2000,    # ← NEW
) -> Agent[None, PHQ8Assessment]:
    return Agent(
        model=model,
        output_type=PHQ8Assessment,
        retries=retries,
        system_prompt=build_juror_system_prompt(...),
        model_settings=ModelSettings(
            temperature=temperature,
            max_tokens=max_tokens,
        ),
    )
```

### Option C: At Model Level in Factory

`run/factory.py`:
```python
agent = build_juror_agent(
    model=full_model_name,
    prompt_version=prompt_version,
    view_name=dialogue_view,
    retries=settings.validation_retries,
    temperature=settings.llm_temperature,  # ← NEW
    max_tokens=settings.llm_max_tokens,    # ← NEW
)
```

---

## PydanticAI Model Settings Reference

```python
from pydantic_ai.settings import ModelSettings

ModelSettings(
    temperature=0.0,      # 0.0-2.0, lower = more deterministic
    top_p=1.0,            # Nucleus sampling threshold
    max_tokens=2000,      # Maximum response length
    timeout=60.0,         # Request timeout
)
```

---

## Files to Change

| File | Change |
|------|--------|
| `settings.py` | Add `llm_temperature`, `llm_max_tokens` |
| `scoring/agent.py` | Accept and pass model settings |
| `judge/agent.py` | Accept and pass model settings |
| `run/factory.py` | Wire settings through to agents |
| `.env.example` | Document new settings |
| `docs/reference/settings.md` | Document new settings |

---

## Test Plan

1. Add temperature parameter to agent builders
2. Verify PydanticAI passes settings to providers
3. Run same dialogue twice with temperature=0.0 → expect much higher stability (provider determinism may still vary)
4. Run same dialogue twice with temperature=1.0 → observe variation
5. Update manifest to record temperature used

---

## Audit Trail Impact

Add to `run_manifest.json`:
```json
{
  "llm_temperature": 0.0,
  "llm_max_tokens": 2000,
  ...
}
```

This enables answering: "What inference settings produced these scores?"

---

## Suggested Reading (Background)

| Source | Recommendation |
|--------|----------------|
| [arXiv:2402.05201](https://arxiv.org/html/2402.05201v2) | Discussion of temperature effects in evaluation-style tasks |
| [arXiv:2506.07295](https://arxiv.org/html/2506.07295v1) | Study of temperature impact on reasoning/consistency |
| [PromptFoo Guide](https://www.promptfoo.dev/docs/guides/evaluate-llm-temperature/) | Practical guidance for evaluating temperature settings |
| [IBM LLM Temperature](https://www.ibm.com/think/topics/llm-temperature) | General overview of temperature and its tradeoffs |
| [Prompt Engineering Guide](https://www.promptingguide.ai/introduction/settings) | General overview of inference settings |

### Key Findings

1. **Low temperature** improves stability for evaluation/scoring tasks
2. **Record inference settings** (temperature/top_p/max_tokens/timeout/seed) for auditability
3. **Seeds can help** for providers/models that support them, but determinism is not guaranteed

### Recommended Configuration for Clinical Scoring

```python
ModelSettings(
    temperature=0.0,    # Most stable / lowest randomness
    seed=42,            # Fixed seed across runs
    max_tokens=2000,    # Sufficient for structured JSON
)
```

**Alternative for studying variance**:
```python
ModelSettings(
    temperature=0.1,    # Minimal variance
    seed=42,            # Still reproducible
    top_p=0.95,         # Slight diversity
)
```

---

## Related

- [ADR-001: Rate limiting & retries](../architecture/adr-001-rate-limiting-retries.md)
- [PydanticAI ModelSettings](https://docs.pydantic.dev/latest/concepts/agents/#model-settings)
- [arXiv:2402.05201 - Effect of Temperature on LLM Problem Solving](https://arxiv.org/html/2402.05201v2)
- [arXiv:2506.07295 - Temperature Impact Study](https://arxiv.org/html/2506.07295v1)

---

## Resolution (Implemented)

Added explicit inference controls to `src/vibe_check/settings.py` (`llm_temperature`, `llm_top_p`, `llm_max_tokens`, `llm_timeout`, optional `llm_seed`) and wired them through agent construction (`src/vibe_check/scoring/agent.py`, `src/vibe_check/judge/agent.py`, `src/vibe_check/run/factory.py`). The selected settings are recorded in the run manifest via `RunConfig` (`src/vibe_check/run/config.py`, `src/vibe_check/run/runner.py`) and documented in `.env.example` and `docs/reference/settings.md`.
