# SPEC-11: PHQ-8 Rubric Embedding

| Field | Value |
|-------|-------|
| **Status** | IMPLEMENTED |
| **Priority** | P0 (Critical) |
| **Fixes** | [BUG-040](../_archive/bugs/bug-040-missing-phq8-rubric-in-prompts.md) |
| **Author** | Claude |
| **Date** | 2026-01-04 |

---

## Problem Statement

The current system prompts rely on LLM pre-trained knowledge of PHQ-8, which creates:

1. **Non-reproducibility**: Different models interpret item names differently
2. **No audit trail**: `prompt_version=v1` is undefined—what rubric was used?
3. **Clinical validity risk**: May conflate PHQ-8 with PHQ-9 or use wrong scoring criteria
4. **Cross-model inconsistency**: GPT, Claude, Gemini may "remember" PHQ-8 differently

### Evidence from Research

| Paper | Finding |
|-------|---------|
| [LMIQ (arxiv:2406.06636)](https://arxiv.org/abs/2406.06636) | Embeds full question text in prompts |
| [Chain-of-Thought (arxiv:2408.14053)](https://arxiv.org/abs/2408.14053) | "Fed the PHQ-8 rubric" before scoring |
| [HopeBot 2025 (arxiv:2507.05984)](https://arxiv.org/abs/2507.05984) | Uses RAG for item-specific clarifications |

**Consensus**: Embed the clinical rubric explicitly. Do not rely on model memory.

---

## Solution Overview

### 1. Add Rubric Constants (`constants.py`)

```python
# Official PHQ-8 item definitions (derived from PHQ-9, self-harm excluded)
PHQ8_RUBRIC: dict[str, str] = {
    "anhedonia": "Little interest or pleasure in doing things",
    "depressed_mood": "Feeling down, depressed, or hopeless",
    "sleep": "Trouble falling or staying asleep, or sleeping too much",
    "fatigue": "Feeling tired or having little energy",
    "appetite": "Poor appetite or overeating",
    "guilt": (
        "Feeling bad about yourself—or that you are a failure "
        "or have let yourself or your family down"
    ),
    "concentration": (
        "Trouble concentrating on things, such as reading "
        "the newspaper or watching television"
    ),
    "psychomotor": (
        "Moving or speaking so slowly that other people could have noticed? "
        "Or the opposite—being so fidgety or restless that you have been "
        "moving around a lot more than usual"
    ),
}

PHQ8_SCORE_SCALE: str = """Score each item 0-3 based on frequency OVER THE LAST 2 WEEKS:
  0 = Not at all
  1 = Several days
  2 = More than half the days
  3 = Nearly every day"""

PHQ8_TIME_FRAME: str = "Over the last 2 weeks"

# Version hash for audit trail
def phq8_rubric_hash() -> str:
    """Return a stable hash of the rubric for audit."""
    import hashlib
    content = str(sorted(PHQ8_RUBRIC.items())) + PHQ8_SCORE_SCALE
    return hashlib.sha256(content.encode()).hexdigest()[:12]
```

---

### 2. Update Juror System Prompt (`scoring/prompting.py`)

#### Current (BAD)

```text
Items (PHQ-8):
- anhedonia
- depressed_mood
- sleep
- fatigue
- appetite
- guilt
- concentration
- psychomotor
```

#### Proposed (GOOD)

```text
PHQ-8 CLINICAL RUBRIC
=====================

Score each item based on how often the CLIENT has been bothered by the following
OVER THE LAST 2 WEEKS:

Scoring Scale:
  0 = Not at all
  1 = Several days
  2 = More than half the days
  3 = Nearly every day

Items:
  1. anhedonia: "Little interest or pleasure in doing things"
  2. depressed_mood: "Feeling down, depressed, or hopeless"
  3. sleep: "Trouble falling or staying asleep, or sleeping too much"
  4. fatigue: "Feeling tired or having little energy"
  5. appetite: "Poor appetite or overeating"
  6. guilt: "Feeling bad about yourself—or that you are a failure or have let yourself or your family down"
  7. concentration: "Trouble concentrating on things, such as reading the newspaper or watching television"
  8. psychomotor: "Moving or speaking so slowly that other people could have noticed? Or the opposite—being so fidgety or restless that you have been moving around a lot more than usual"

IMPORTANT: Match evidence to the EXACT item definition above. Do not infer beyond the text.
```

#### Implementation

```python
def build_juror_system_prompt(
    prompt_version: str,
    view_name: str = "client_qa",
    extra_instructions: str | None = None,
) -> str:
    """Build the system prompt for a single juror PHQ-8 scoring run."""
    from vibe_check.constants import PHQ8_RUBRIC, PHQ8_SCORE_SCALE, PHQ8_TIME_FRAME

    rubric_items = "\n".join(
        f"  {i}. {name}: \"{definition}\""
        for i, (name, definition) in enumerate(PHQ8_RUBRIC.items(), 1)
    )

    base = f"""You are a clinical scoring juror. Score PHQ-8.

Input: a preprocessed dialogue view named `{view_name}` from a synthetic therapy conversation.
Prompt version: {prompt_version}.

PHQ-8 CLINICAL RUBRIC
=====================

Score each item based on how often the CLIENT has been bothered by the following
{PHQ8_TIME_FRAME}:

{PHQ8_SCORE_SCALE}

Items:
{rubric_items}

IMPORTANT: Match evidence to the EXACT item definition above. Do not infer beyond the text.

Rules:
- Use ONLY the provided text. Do not assume facts not stated.
- Score PHQ-8 items only (8 items). Self-harm is a separate boolean tag, not an extra item.
- Therapist lines are context; evidence should quote/paraphrase CLIENT statements.
- If evidence is insufficient for an item, set `insufficient_evidence=true` and still choose the best score (0-3).

For each item, return:
- score: integer 0-3
- confidence: float 0.0-1.0
- evidence: list of up to 3 short snippets (each <= 50 words)
- insufficient_evidence: boolean

Also return:
- mentions_self_harm: boolean (true if the client expresses self-harm/suicidal ideation)
- self_harm_evidence: list of up to 3 short snippets
- total_score: sum of the 8 item scores (0-24)

Return JSON ONLY. No markdown, no code fences, no prose.
"""
    if extra_instructions:
        return base + "\n" + extra_instructions.strip() + "\n"
    return base
```

---

### 3. Update Judge System Prompt (`judge/prompting.py`)

#### Current (BAD)

```text
You are an expert judge resolving contested PHQ-8 item scores.
Prompt version: {prompt_version}.

Return JSON ONLY. No markdown, no code fences, no prose.
```

#### Proposed (GOOD)

```text
You are an expert judge resolving contested PHQ-8 item scores.
Prompt version: {prompt_version}.

PHQ-8 CLINICAL RUBRIC
=====================

{PHQ8_SCORE_SCALE}

Item Definitions:
{rubric_items}

ARBITRATION CRITERIA
====================

When jurors disagree on a score:
1. Review the juror evidence against the EXACT item definition
2. Apply the 0-3 frequency scale strictly (0=Not at all, 3=Nearly every day)
3. If evidence supports multiple interpretations, choose the score best supported by direct CLIENT quotes
4. If evidence is sparse, favor the majority juror vote
5. Higher confidence when multiple jurors cite consistent evidence; lower when evidence is contradictory

Return JSON ONLY. No markdown, no code fences, no prose.
```

#### Implementation

```python
def build_judge_system_prompt(prompt_version: str) -> str:
    from vibe_check.constants import PHQ8_RUBRIC, PHQ8_SCORE_SCALE

    rubric_items = "\n".join(
        f"  - {name}: \"{definition}\""
        for name, definition in PHQ8_RUBRIC.items()
    )

    return f"""You are an expert judge resolving contested PHQ-8 item scores.
Prompt version: {prompt_version}.

PHQ-8 CLINICAL RUBRIC
=====================

{PHQ8_SCORE_SCALE}

Item Definitions:
{rubric_items}

ARBITRATION CRITERIA
====================

When jurors disagree on a score:
1. Review the juror evidence against the EXACT item definition
2. Apply the 0-3 frequency scale strictly (0=Not at all, 3=Nearly every day)
3. If evidence supports multiple interpretations, choose the score best supported by direct CLIENT quotes
4. If evidence is sparse, favor the majority juror vote
5. Higher confidence when multiple jurors cite consistent evidence; lower when evidence is contradictory

Return JSON ONLY. No markdown, no code fences, no prose.
"""
```

---

### 4. Update Judge Item Prompt (`judge/prompting.py`)

#### Current (BAD)

```text
Contested item: {item}
```

#### Proposed (GOOD)

```text
Contested item: {item}
Item definition: "{PHQ8_RUBRIC[item]}"
```

#### Implementation

```python
def build_judge_item_prompt(
    *,
    scoring_text: str,
    item: str,
    juror_votes: list[int],
    juror_evidence: list[str],
) -> str:
    from vibe_check.constants import PHQ8_RUBRIC, MAX_JUDGE_EVIDENCE_SNIPPETS, PHQ8_ITEMS

    if item not in PHQ8_ITEMS:
        raise ValueError(f"Unknown PHQ-8 item: {item!r}")

    item_definition = PHQ8_RUBRIC[item]
    evidence_block = "\n".join(f"- {e}" for e in juror_evidence[:MAX_JUDGE_EVIDENCE_SNIPPETS])

    return f"""Contested item: {item}
Item definition: "{item_definition}"

Juror votes: {juror_votes}
Juror evidence snippets:
{evidence_block}

Dialogue (view text):
{scoring_text}

Apply the scoring scale (0=Not at all, 1=Several days, 2=More than half the days, 3=Nearly every day) strictly.

Respond with JSON:
{{"item": "{item}", "final_score": <0-3>, "confidence": <0.0-1.0>, "rationale": "..."}}
"""
```

---

### 5. Add Rubric Hash to Manifest

Update `run/runner.py` to record rubric hash:

```python
def _build_manifest(self, ...) -> dict:
    from vibe_check.constants import phq8_rubric_hash

    return {
        ...
        "rubric_hash": phq8_rubric_hash(),
        ...
    }
```

This enables audit: "This run used rubric version `a1b2c3d4e5f6`."

---

## Files Changed

| File | Change |
|------|--------|
| `src/vibe_check/constants.py` | Add `PHQ8_RUBRIC`, `PHQ8_SCORE_SCALE`, `PHQ8_TIME_FRAME`, `phq8_rubric_hash()` |
| `src/vibe_check/scoring/prompting.py` | Embed full rubric in juror prompt |
| `src/vibe_check/judge/prompting.py` | Embed rubric + arbitration criteria in judge prompts |
| `src/vibe_check/run/runner.py` | Add `rubric_hash` to manifest |
| `tests/unit/test_prompting.py` | Verify rubric appears in prompts |
| `tests/unit/test_constants.py` | Test rubric hash stability |

---

## Test Plan

### Unit Tests

1. **Rubric in juror prompt**: Assert all 8 item definitions appear
2. **Score scale in prompt**: Assert "0 = Not at all" through "3 = Nearly every day" appear
3. **Time frame in prompt**: Assert "last 2 weeks" appears
4. **Rubric in judge prompt**: Assert item definitions appear
5. **Arbitration criteria**: Assert judge prompt includes criteria
6. **Item definition in judge item prompt**: Assert definition for contested item appears
7. **Rubric hash stability**: Same rubric → same hash

### Integration Tests

1. **Prompt version tracking**: Verify manifest contains `rubric_hash`
2. **Cross-model consistency**: (Qualitative) Same dialogue scored by real jurors should show improved agreement

---

## Prompt Before/After Comparison

### Juror Prompt Size

| Version | Approximate Tokens |
|---------|-------------------|
| Current | ~250 tokens |
| Proposed | ~450 tokens |
| Delta | +200 tokens (~$0.0006 per call at GPT-4 rates) |

**Trade-off**: Small cost increase for major reproducibility/validity improvement.

### Judge Prompt Size

| Version | Approximate Tokens |
|---------|-------------------|
| Current | ~50 tokens |
| Proposed | ~300 tokens |
| Delta | +250 tokens |

**Trade-off**: Significant improvement in judge guidance for minimal cost.

---

## Migration

This is a **prompt version change**. After implementation:

1. Update `prompt_version` default to `v2` (or keep `v1` with rubric hash)
2. Existing runs with `prompt_version=v1` are NOT comparable to new runs
3. Document this in release notes

---

## Design Decision: Prompt Embedding vs Vector Embeddings

### Clarification of Terminology

- **"Prompt embedding"** = Including text directly in the LLM prompt (what this spec proposes)
- **"Vector embeddings"** = Numerical ML representations for semantic search/RAG

### Why Prompt Embedding (Not Vector RAG)?

For the PHQ-8 rubric specifically, **direct prompt embedding is the correct choice**:

| Approach | Pros | Cons |
|----------|------|------|
| **Direct Prompt Embedding ✓** | 100% deterministic, no retrieval errors, simple | Slightly larger prompts (~200 tokens) |
| **Vector RAG** | Good for large/dynamic knowledge bases | Overkill for 8 fixed items, adds complexity |

**Decision**: The PHQ-8 rubric is small (8 items, ~200 tokens) and static. Direct prompt embedding guarantees the rubric is always correctly provided to the LLM with no retrieval failures.

### Where Vector Embeddings ARE Useful (Future)

Vector embeddings may be valuable for other vibe-check use cases (future scope):

| Use Case | Embedding Model Recommendation (2025) |
|----------|---------------------------------------|
| Dialogue similarity search | **Voyage-3-large** (best retrieval, $0.06-0.18/M tokens) |
| Evidence clustering | **text-embedding-3-large** (OpenAI, $0.13/M tokens) |
| Multilingual sessions | **Gemini Embedding** (100+ languages, free tier) |

### Current State: `embedding_dialogue_view` Setting

The codebase has a placeholder setting in `settings.py`:

```python
embedding_dialogue_view: Literal["client_qa", "client_contextualized", "client_only"] = "client_qa"
```

**Status**: Setting exists but NO implementation code. This is a **future enhancement**, not a critical gap.

**Current flow** (no vector embeddings):
```
Dialogue → Preprocess → Full view to LLM → PHQ-8 scores
```

**Future flow** (with vector embeddings):
```
Dialogue → Preprocess → Embed → Store in vector DB
                    ↓
Query → Retrieve similar → Compare/analyze
```

### When to Implement Dialogue Embeddings (Future SPEC)

Implement if ANY of these become true:

1. **Corpus scale**: >10,000 dialogues needing similarity search
2. **Long dialogues**: Sessions >4000 tokens where RAG would help jurors find evidence
3. **Research needs**: Finding similar cases, clustering by symptom patterns
4. **Multi-session tracking**: Same client over time needs embedding-based continuity

**Recommendation**: Create a separate SPEC-12 when these needs arise. For now, focus on BUG-040 (critical).

#### Best Embedding APIs (2025-2026 Research)

| Provider | Model | MTEB Score | Cost | Notes |
|----------|-------|-----------|------|-------|
| **Voyage AI** | voyage-3-large | Top-tier | $0.06-0.18/M | Anthropic recommended partner |
| **Mistral** | mistral-embed | 77.8% acc | Moderate | Best raw accuracy |
| **OpenAI** | text-embedding-3-large | Good | $0.13/M | 3072 dimensions |
| **Google** | gemini-embedding-001 | Good | Free tier | Best value for small teams |
| **NVIDIA** | NV-Embed | 69.32 MTEB | Enterprise | Best for on-prem |

**Sources**:
- [Embedding Models: OpenAI vs Gemini vs Cohere 2026](https://research.aimultiple.com/embedding-models/)
- [Top Embedding Models 2026](https://artsmart.ai/blog/top-embedding-models-in-2025/)
- [MTEB Leaderboard](https://huggingface.co/spaces/mteb/leaderboard)
- [Google Gemini Embedding](https://techcrunch.com/2025/03/07/google-debuts-a-new-gemini-based-text-embedding-model/)

---

## Related

- [BUG-040: Missing PHQ-8 Rubric in Prompts](../_bugs/BUG-040-missing-phq8-rubric-in-prompts.md)
- [Prompts Reference](../prompts/index.md)
- [SPEC-04: Juror Scoring Agent](../_archive/specs/spec-04-juror-scoring-agent.md)
- [SPEC-05: Consensus Orchestration](../_archive/specs/spec-05-consensus-orchestration.md)
