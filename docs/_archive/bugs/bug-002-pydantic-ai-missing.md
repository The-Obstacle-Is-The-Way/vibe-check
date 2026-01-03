---
severity: P1
status: fixed
---

# BUG-002: SPEC-04 ignored the SSOT PydanticAI mandate

## Summary

The SSOT selects **LangGraph + PydanticAI** for structured outputs. The initial SPEC-04 draft treated provider integration as an implementation choice via ad-hoc SDK wrappers (`FakeLLMClient` / `LLMClient`), creating a framework mismatch and risking fragmented agent interfaces.

## Evidence

- SSOT framework decision: `docs/research/spec-vibe-check.md:195`
- SPEC-04 (historical): `docs/specs/spec-04-juror-scoring-agent.md:79` (previously suggested provider SDKs / fake client instead of PydanticAI)

## Impact

- Increased implementation drift across agents (jurors/judge), inconsistent retry/usage semantics, and higher maintenance cost.
- Harder to enforce structured outputs and to test reliably without network calls.

## Fix

- Require `pydantic-ai>=1.0.0` in SPEC-04.
- Use PydanticAI `Agent` as the juror interface, and use `pydantic_ai.models.test.TestModel` for deterministic tests.

## Resolution

Fixed by updating `docs/specs/spec-04-juror-scoring-agent.md` to make PydanticAI the required interface and removing `FakeLLMClient`/`LLMClient` as the primary abstraction.
