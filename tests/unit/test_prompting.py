from __future__ import annotations

from vibe_check.scoring.prompting import build_juror_system_prompt


def test_juror_prompt_invariants() -> None:
    prompt = build_juror_system_prompt(prompt_version="v1", view_name="client_qa")

    assert "PHQ-8" in prompt
    assert "PHQ-9" not in prompt
    assert "JSON" in prompt
    assert "insufficient_evidence" in prompt
    assert "mentions_self_harm" in prompt

    for item in (
        "anhedonia",
        "depressed_mood",
        "sleep",
        "fatigue",
        "appetite",
        "guilt",
        "concentration",
        "psychomotor",
    ):
        assert item in prompt
