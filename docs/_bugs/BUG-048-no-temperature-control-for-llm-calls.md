# BUG-048: No Temperature Control for LLM Calls

| Field | Value |
|-------|-------|
| **Severity** | P1 (High - Research Reproducibility) |
| **Status** | open |
| **Date** | 2026-01-04 |
| **Component** | `scoring/agent.py`, `judge/agent.py`, `run/factory.py` |
| **Impact** | Non-reproducible scores, research validity |

---

## Summary

**No temperature, top_p, top_k, or max_tokens parameters are specified anywhere in the codebase.** All LLM calls use provider defaults (typically temperature=1.0), which introduces randomness into clinical scoring.

This is a **critical research reproducibility issue**.

### Spec-Implementation Gap

The master spec **explicitly mentions temperature** but the implementation ignores it:

| Location | Spec Says | Implementation |
|----------|-----------|----------------|
| `spec-vibe-check.md:49` | "LLM JSON failures can be deterministic at temperature=0" | No temperature set |
| `spec-vibe-check.md:1643` | "Do not retry blindly at temperature=0" | No temperature set |
| `spec-vibe-check.md:1683` | `call_model(..., temperature=0.1)` | No temperature passed |
| `docs/reference/cli.md:245` | `--seed` for deterministic sampling | Seed not connected to model calls |

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
| 0.0 | Deterministic (same input → same output) |
| 0.3-0.7 | Low variability (reasonable for creative tasks) |
| 1.0 (default) | High variability (different output each run) |

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
| `temperature` | **0.0** | Deterministic scoring |
| `top_p` | 1.0 | Use temperature control instead |
| `max_tokens` | 2000 | Sufficient for JSON response |

### Alternative: Low Temperature with Seed

Some research prefers `temperature=0.1` with explicit seed for slight variation:
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
3. Run same dialogue twice with temperature=0.0 → verify identical scores
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

## Research Best Practices (2025)

### Academic Consensus

| Source | Recommendation |
|--------|----------------|
| [arXiv:2402.05201](https://arxiv.org/html/2402.05201v2) | "For problem-solving tasks, set temperature to 0.0 to maximize reproducibility without compromising accuracy" |
| [arXiv:2506.07295](https://arxiv.org/html/2506.07295v1) | Studies temperature's impact on LLM reasoning and consistency |
| [PromptFoo Guide](https://www.promptfoo.dev/docs/guides/evaluate-llm-temperature/) | "Run systematic evaluation to find optimal temperature for your use case" |
| [IBM LLM Temperature](https://www.ibm.com/think/topics/llm-temperature) | "For applications needing reliable, reproducible outputs, use 0.2-0.3" |
| [Prompt Engineering Guide](https://www.promptingguide.ai/introduction/settings) | "For research contexts, combine moderate temperature with fixed seed" |

### Key Findings

1. **Temperature 0.0** maximizes reproducibility for evaluation/scoring tasks
2. **Seed parameter** is essential - OpenAI introduced it specifically for reproducibility
3. **System fingerprint** should be tracked to detect backend changes affecting outputs
4. **Performance drops** significantly at temperature > 1.0 for structured tasks

### Recommended Configuration for Clinical Scoring

```python
ModelSettings(
    temperature=0.0,    # Deterministic for reproducibility
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

- [ADR-001: Three-Layer Resilience](../architecture/decisions/ADR-001-three-layer-resilience.md)
- [PydanticAI ModelSettings](https://docs.pydantic.dev/latest/concepts/agents/#model-settings)
- [arXiv:2402.05201 - Effect of Temperature on LLM Problem Solving](https://arxiv.org/html/2402.05201v2)
- [arXiv:2506.07295 - Temperature Impact Study](https://arxiv.org/html/2506.07295v1)
