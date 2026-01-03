---
severity: P1
status: open
opened_date: 2026-01-03
---

# BUG-028: Live Gemini jurors fail: `google-gla` expects `GEMINI_API_KEY` (not `GOOGLE_API_KEY`)

## Summary
In `--live` runs, the real jury includes Gemini jurors using the PydanticAI provider prefix `google-gla`, but our CLI and `.env.example` configure `GOOGLE_API_KEY`. PydanticAI's `google-gla` provider reads **only** `GEMINI_API_KEY` and is marked **deprecated**, so live runs can fail immediately when the Gemini jurors are invoked.

## Evidence
- `src/vibe_check/run/factory.py`
  - Uses `("google-gla", settings.juror_gemini_model)` and builds models like `google-gla:gemini-...`.
- `src/vibe_check/cli.py`
  - In `--live` mode, exports `settings.google_api_key` to `GOOGLE_API_KEY` (not `GEMINI_API_KEY`).
- `.env.example`
  - Documents `GOOGLE_API_KEY=...` (no `GEMINI_API_KEY`).
- `pydantic_ai.providers.google_gla.GoogleGLAProvider`
  - Provider name is `google-gla`
  - Auth is read from `GEMINI_API_KEY`
  - The provider is marked deprecated (risk of removal in future versions)

## Impact
- `vibe-check score-corpus --live` can fail for all dialogues even when `GOOGLE_API_KEY` is set (per our own `.env.example`).
- Long-term maintenance risk: `google-gla` is deprecated upstream.

## Repro (typical)
1. Set `GOOGLE_API_KEY` in `.env` (or environment), do **not** set `GEMINI_API_KEY`.
2. Run `vibe-check score-corpus --live ...`.
3. Gemini juror calls raise a PydanticAI `UserError` requesting `GEMINI_API_KEY`.

## Fix Plan
- Prefer: migrate Gemini jurors from `google-gla` → `google` provider prefix (non-deprecated).
- Also: set both env vars in live mode (`GEMINI_API_KEY` and `GOOGLE_API_KEY`) for compatibility, or switch Settings to use `GEMINI_API_KEY` as the canonical field.
- Update `.env.example` and docs to match the provider actually used.
- Add a unit test covering live env var wiring for the Gemini provider.
