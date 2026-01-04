---
severity: P4
status: open
opened_date: 2026-01-03
---

# BUG-038: No API Key Validation Before Live Run

## Summary

When running `vibe-check score-corpus --live`, the CLI does not validate that the required API keys are present before starting the run. Users only discover missing keys when the first API call fails.

## Evidence

In `src/vibe_check/cli.py:112-128`:

```python
if args.live:
    export_provider_api_keys(settings)  # Exports whatever keys exist (even None)

    # BUG-027 fix: Pass CLI args to factory functions, not Settings defaults
    jurors = build_real_jury(
        settings,
        prompt_version=args.prompt_version,
        dialogue_view=args.dialogue_view,
    )
    judge_item = build_real_judge_item(
        settings,
        prompt_version=args.prompt_version,
    )
```

And `export_provider_api_keys()`:

```python
def export_provider_api_keys(settings: Settings) -> None:
    if settings.openai_api_key:
        os.environ.setdefault("OPENAI_API_KEY", settings.openai_api_key)
    if settings.anthropic_api_key:
        os.environ.setdefault("ANTHROPIC_API_KEY", settings.anthropic_api_key)
    if settings.google_api_key:
        os.environ.setdefault("GOOGLE_API_KEY", settings.google_api_key)
        os.environ.setdefault("GEMINI_API_KEY", settings.google_api_key)
```

No validation occurs. If all three keys are `None`, the run starts and builds jurors, but the first `agent.run()` call will fail with an authentication error.

## Impact

- **UX**: Users discover missing keys mid-run, after potentially processing some dialogues
- **Debugging**: Error messages from provider SDKs may not clearly indicate "key missing"
- **Wasted compute**: If one provider's key is missing, jurors for other providers might complete successfully before the error

## Root Cause

No upfront validation of required credentials.

## Proposed Fix

Add validation before building real jurors:

```python
if args.live:
    required_keys = {
        "OPENAI_API_KEY": settings.openai_api_key,
        "ANTHROPIC_API_KEY": settings.anthropic_api_key,
        "GOOGLE_API_KEY": settings.google_api_key,
    }
    missing = [k for k, v in required_keys.items() if not v]
    if missing:
        raise ValueError(
            f"--live requires API keys: {', '.join(missing)}. "
            f"Set them in .env or environment."
        )

    export_provider_api_keys(settings)
    # ... build jurors/judge
```

## Considerations

- Should we allow partial live runs (e.g., only OpenAI key set)?
- Current design assumes all 3 providers are used for the 6-juror ensemble
- Single-provider mode would require different juror configuration

## Verification

- [ ] Add test for missing key detection
- [ ] Verify error message is clear
- [ ] Test with partial keys (if supported)
