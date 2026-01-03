# Dialogue Views

Dialogue views are cleaned, structured representations of raw therapy transcripts. Preprocessing transforms messy dialogue text into consistent formats suitable for LLM scoring.

---

## Why Preprocess?

Raw SQPsychConv dialogues contain:
- Inconsistent speaker labels (`Therapist:`, `therapist:`, `THERAPIST:`)
- Generation artifacts (`[word limit: 64]`, `[check guidelines]`)
- Bracketed meta-instructions that leak into output
- Irregular whitespace and formatting

Preprocessing creates **deterministic, clean views** for reliable scoring.

---

## Available Views

| View | Content | Use Case |
|------|---------|----------|
| `dialogue_clean` | Normalized speaker labels + whitespace | Full context debugging |
| `client_only_text` | Client utterances only | **Not recommended** (semantic void risk) |
| `client_qa_text` | Client + preceding therapist question | **Default for scoring** |

---

## View Descriptions

### `dialogue_clean`

The full dialogue with normalized speaker labels:

```
Therapist: How have you been sleeping lately?
Client: Not well. I wake up at 3am most nights.
Therapist: That sounds difficult. How long has this been going on?
Client: About two months now.
```

### `client_only_text`

Only client utterances, concatenated:

```
Not well. I wake up at 3am most nights.
About two months now.
```

**Warning**: This view loses context. Short answers like "Yes" or "About two months" become meaningless without the therapist's question.

### `client_qa_text` (Default)

Client utterances with the **preceding therapist question** for context:

```
Therapist: How have you been sleeping lately?
Client: Not well. I wake up at 3am most nights.
Therapist: How long has this been going on?
Client: About two months now.
```

This is the default view for scoring because it preserves the semantic context of client responses.

---

## Preprocessing Pipeline

```
┌────────────────────────────────────────────────────────────────┐
│                    PREPROCESSING PIPELINE                      │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│  Raw dialogue text                                             │
│         │                                                      │
│         ▼                                                      │
│  ┌──────────────────────────────────────┐                      │
│  │ 1. Parse Utterances                  │                      │
│  │    - Detect speaker labels           │                      │
│  │    - Split into (speaker, text)      │                      │
│  │    - Handle multi-line utterances    │                      │
│  └────────────────┬─────────────────────┘                      │
│                   │                                            │
│                   ▼                                            │
│  ┌──────────────────────────────────────┐                      │
│  │ 2. Sanitize Text                     │                      │
│  │    - Remove bracketed meta-text      │                      │
│  │    - Strip generation artifacts      │                      │
│  │    - Filter overly long utterances   │                      │
│  └────────────────┬─────────────────────┘                      │
│                   │                                            │
│                   ▼                                            │
│  ┌──────────────────────────────────────┐                      │
│  │ 3. Build Views                       │                      │
│  │    - dialogue_clean                  │                      │
│  │    - client_only_text                │                      │
│  │    - client_qa_text                  │                      │
│  └────────────────┬─────────────────────┘                      │
│                   │                                            │
│                   ▼                                            │
│  DialogueViews (output schema)                                 │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

---

## Artifact Removal

The preprocessor removes common generation artifacts:

| Pattern | Example | Action |
|---------|---------|--------|
| Bracketed instructions | `[word limit: 64]` | Remove |
| Long bracketed text | `[Check the guidelines...]` | Remove |
| Meta-commentary | `"" This finalizes the...` | Truncate |
| Excessively long utterances | `> 4000 chars or > 200 words` | Skip |
| Unknown speaker labels | `Assistant:`, `User:` | Flag as unknown |

---

## DialogueViews Schema

```python
class DialogueViews(BaseModel):
    file_id: str

    dialogue_clean: str        # Normalized full dialogue
    client_only_text: str      # Client utterances only
    client_qa_text: str        # Client + preceding therapist Q

    client_utterance_count: int
    therapist_utterance_count: int
    short_answer_count: int    # Client responses < 5 words

    has_empty_client_text: bool
    has_unknown_speaker: bool
```

---

## Diagnostics

The views include diagnostic flags:

| Flag | Meaning | Implication |
|------|---------|-------------|
| `has_empty_client_text` | No client utterances found | Cannot score |
| `has_unknown_speaker` | Unrecognized speaker labels | Possible parsing errors |
| `short_answer_count` | Many terse responses | May need `client_qa_text` for context |

---

## Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| `scoring_dialogue_view` | `client_qa` | Which view to use for scoring |

---

## Code Reference

| File | Function | Purpose |
|------|----------|---------|
| `preprocessing/extractor.py` | `preprocess_dialogue()` | Main entry point |
| `preprocessing/extractor.py` | `parse_utterances()` | Speaker/text parsing |
| `schemas/views.py` | `DialogueViews` | Output schema |

---

## Related Concepts

- [Jury Consensus](jury-consensus.md) - How views are used for scoring
