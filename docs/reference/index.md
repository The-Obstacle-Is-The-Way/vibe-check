# Reference

Technical reference documentation for vibe-check.

---

## Reference Documents

| Document | Description |
|----------|-------------|
| [CLI](cli.md) | Command-line interface reference |
| [Schemas](schemas.md) | All Pydantic data models |
| [Settings](settings.md) | Configuration field reference |
| [Thresholds](thresholds.md) | Numeric thresholds explained |

---

## Quick Links

### Commands

- `vibe-check score-corpus` - Score dialogues
- `vibe-check diagnostics` - Run quality checks
- `vibe-check export` - Create label files
- `vibe-check validate-export` - Validate export

### Key Schemas

- `SQPsychConvDialogue` - Input corpus record
- `PHQ8Report` - Single juror output
- `AggregatedPHQ8` - Final aggregated output
- `ScoredDialogueExport` - Public export format

### Key Settings

- API keys: `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GOOGLE_API_KEY` (or `GEMINI_API_KEY`)
- Models: `JUROR_GPT_MODEL`, `JUDGE_MODEL`
- Thresholds: `ARBITRATION_*`
