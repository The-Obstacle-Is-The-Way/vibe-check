# Resilience Strategy

vibe-check implements a **three-layer resilience strategy** for juror scoring (and Layers 1-2 for judge calls) to handle LLM API failures gracefully. For implementation details, see [Architecture: Resilience](../architecture/resilience.md).

---

## Why Three Layers?

LLM APIs fail in different ways:

| Failure Type | Cause | Solution |
|--------------|-------|----------|
| **Validation errors** | Malformed JSON output | Re-prompt with error context |
| **Rate limits (429)** | Too many requests | Backoff and retry |
| **Server errors (5xx)** | Provider issues | Backoff and retry |
| **Network errors** | Connection issues | Retry with delay |

No single mechanism handles all cases. The three-layer approach ensures each failure type is handled appropriately.

---

## Layer Architecture

```
┌─────────────────────────────────────────────────────────────┐
│              THREE-LAYER RESILIENCE STRATEGY                │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  INCOMING REQUEST (score one juror run)                     │
│         │                                                   │
│         ▼                                                   │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ LAYER 3: PROACTIVE RATE LIMITING (aiolimiter)       │    │
│  │                                                     │    │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐           │    │
│  │  │ OpenAI   │  │Anthropic │  │  Google  │           │    │
│  │  │ 100 RPM  │  │  60 RPM  │  │ 100 RPM  │           │    │
│  │  └──────────┘  └──────────┘  └──────────┘           │    │
│  │                                                     │    │
│  │  → Throttles requests BEFORE hitting provider       │    │
│  │  → Prevents 429 errors proactively                  │    │
│  └─────────────────────────────────────────────────────┘    │
│         │                                                   │
│         ▼                                                   │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ LAYER 2: TRANSIENT RETRY (tenacity)                 │    │
│  │                                                     │    │
│  │  Retries on:                                        │    │
│  │    • 429 Rate Limit                                 │    │
│  │    • 500, 502, 503, 504 Server Errors               │    │
│  │    • Network/Connection Errors                      │    │
│  │    • Timeouts                                       │    │
│  │                                                     │    │
│  │  Strategy:                                          │    │
│  │    • Max 5 attempts                                 │    │
│  │    • Exponential backoff with jitter                │    │
│  │    • Initial: 1s → Max: 60s                         │    │
│  └─────────────────────────────────────────────────────┘    │
│         │                                                   │
│         ▼                                                   │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ LAYER 1: VALIDATION RETRY (PydanticAI)              │    │
│  │                                                     │    │
│  │  Retries on:                                        │    │
│  │    • JSON schema validation failures                │    │
│  │    • Missing required fields                        │    │
│  │    • Invalid field types                            │    │
│  │                                                     │    │
│  │  Strategy:                                          │    │
│  │    • retries=2 in Agent constructor                 │    │
│  │    • Re-prompts with validation error context       │    │
│  └─────────────────────────────────────────────────────┘    │
│         │                                                   │
│         ▼                                                   │
│  SUCCESS: PHQ8Report returned                               │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Layer 1: Validation Retry (PydanticAI)

**Purpose**: Handle malformed LLM outputs

When an LLM returns invalid JSON (missing fields, wrong types), PydanticAI automatically:
1. Detects the validation error
2. Re-prompts with the error message
3. Gives the model a chance to correct its output

```python
agent = Agent(
    model="openai:gpt-5.2",
    output_type=PHQ8Assessment,
    retries=2,  # Layer 1: 2 validation retries
)
```

---

## Layer 2: Transient Retry (Tenacity)

**Purpose**: Handle temporary API failures

Uses exponential backoff with jitter to retry transient errors:

```python
@with_retry(
    max_attempts=5,
    initial_wait=1.0,
    max_wait=60.0,
    jitter=5.0,
)
async def _call_with_retry():
    return await agent.run(scoring_text)
```

### Retry Schedule

| Attempt | Base Wait | With Jitter (±5s) |
|---------|-----------|-------------------|
| 1 | 1s | 0-6s |
| 2 | 2s | 0-7s |
| 3 | 4s | 0-9s |
| 4 | 8s | 3-13s |
| 5 | 16s | 11-21s |

### Transient Error Detection

The `_is_transient_error()` function identifies retryable errors:

```python
# Retryable errors:
- HTTPStatusError with status 429, 500, 502, 503, 504
- NetworkError, TimeoutException
- ConnectionError, OSError
- SDK errors containing: "ratelimit", "timeout", "connection", "overload", "server"
```

---

## Layer 3: Rate Limiting (Aiolimiter)

**Purpose**: Prevent 429 errors proactively

Uses token bucket algorithm for per-provider rate limiting:

```python
class ProviderRateLimiters:
    def __init__(self, settings: Settings):
        self._openai = AsyncLimiter(settings.openai_rpm, 60.0)
        self._anthropic = AsyncLimiter(settings.anthropic_rpm, 60.0)
        self._google = AsyncLimiter(settings.google_rpm, 60.0)
```

### How Token Bucket Works

```
┌────────────────────────────────────────────────────────────┐
│                    TOKEN BUCKET                            │
├────────────────────────────────────────────────────────────┤
│                                                            │
│  Bucket capacity: N tokens (N = configured RPM)            │
│  Refill rate: N tokens per 60 seconds                      │
│                                                            │
│  Request arrives:                                          │
│    - If bucket has token → consume and proceed             │
│    - If bucket empty → wait for refill                     │
│                                                            │
│  Effect: Smooths request rate to stay under limit          │
│                                                            │
└────────────────────────────────────────────────────────────┘
```

---

## How Layers Interact

```python
async def ascore(self, scoring_text: str) -> PHQ8Report:
    # Layer 3: Rate limiting (wait for token)
    async with self._rate_limiter:
        # Layer 2: Transient retry wrapper
        @with_retry(max_attempts=5, ...)
        async def _call():
            # Layer 1: PydanticAI validation retry (internal)
            return await self._agent.run(scoring_text)

        result = await _call()

    return self._to_report(result)
```

Execution order:
1. **Layer 3** waits for rate limit token
2. **Layer 2** wraps the call with retry logic
3. **Layer 1** (inside PydanticAI) handles validation retries

---

## Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| `openai_rpm` | `100` | OpenAI requests per minute |
| `anthropic_rpm` | `60` | Anthropic requests per minute |
| `google_rpm` | `100` | Google requests per minute |
| `max_retries` | `5` | Max transient retry attempts |
| `retry_initial_wait` | `1.0` | Initial backoff (seconds) |
| `retry_max_wait` | `60.0` | Max backoff (seconds) |
| `retry_jitter` | `5.0` | Random jitter (seconds) |
| `validation_retries` | `2` | PydanticAI validation retries |

---

## Code Reference

| File | Component | Purpose |
|------|-----------|---------|
| `resilience.py` | `with_retry()` | Tenacity decorator for Layer 2 |
| `resilience.py` | `ProviderRateLimiters` | Layer 3 rate limiting |
| `resilience.py` | `_is_transient_error()` | Transient error detection |
| `scoring/agent.py` | `build_juror_agent()` | Layer 1 via `retries` param |
| `run/factory.py` | `build_real_jury()` | Wires all three layers |

---

## Related Concepts

- [Jury Consensus](../scoring/jury-consensus.md) - How jurors use resilience
- [Arbitration](../scoring/arbitration.md) - How the judge uses resilience
