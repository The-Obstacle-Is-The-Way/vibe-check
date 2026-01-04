from __future__ import annotations

from vibe_check.constants import PHQ8_RUBRIC, PHQ8_SCORE_SCALE, PHQ8_TIME_FRAME
from vibe_check.scoring.prompting import build_juror_system_prompt


def test_juror_prompt_invariants() -> None:
    prompt = build_juror_system_prompt(prompt_version="v1", view_name="client_qa")

    assert "PHQ-8" in prompt
    assert "PHQ-9" not in prompt
    assert "JSON" in prompt
    assert "insufficient_evidence" in prompt
    assert "mentions_self_harm" in prompt

    assert PHQ8_TIME_FRAME in prompt
    for line in PHQ8_SCORE_SCALE.splitlines():
        assert line in prompt

    for item, definition in PHQ8_RUBRIC.items():
        assert item in prompt
        assert definition in prompt
