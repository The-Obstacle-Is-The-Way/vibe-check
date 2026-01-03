# Preprocessing

This section documents how raw therapy dialogues are transformed into clean, structured text for LLM scoring.

---

## Documents

| Document | Description |
|----------|-------------|
| [Dialogue Views](dialogue-views.md) | Available views (client_qa, client_only) and preprocessing pipeline |

---

## Overview

Raw SQPsychConv dialogues require preprocessing before scoring:

```
┌─────────────────────────────────────────────────────────────┐
│                  PREPROCESSING PIPELINE                     │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Raw Dialogue                                               │
│  "therapist: How are you? [word limit: 64]                  │
│   Client: I'm not doing well..."                            │
│         │                                                   │
│         ▼                                                   │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ 1. Parse speaker labels                             │    │
│  │ 2. Remove generation artifacts                      │    │
│  │ 3. Normalize whitespace                             │    │
│  └─────────────────────────────────────────────────────┘    │
│         │                                                   │
│         ▼                                                   │
│  DialogueViews                                              │
│  ├── dialogue_clean   (full normalized text)                │
│  ├── client_only_text (client utterances only)              │
│  └── client_qa_text   (client + therapist questions)        │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Why Preprocess?

Raw dialogues contain:
- **Inconsistent labels**: `Therapist:`, `therapist:`, `THERAPIST:`
- **Generation artifacts**: `[word limit: 64]`, `[check guidelines]`
- **Meta-commentary**: Leaked instructions from LLM generation
- **Irregular formatting**: Extra whitespace, missing punctuation

Preprocessing creates deterministic, clean views for reliable scoring.

---

## Default View

The default view for scoring is `client_qa_text`:
- Includes client responses with preceding therapist questions
- Preserves semantic context for short answers
- Removes artifacts and normalizes formatting

---

## Related Sections

- [Scoring](../scoring/) - How preprocessed text becomes scores
- [Architecture: Data Flow](../architecture/data-flow.md) - Full input-to-output journey
