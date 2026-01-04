from __future__ import annotations

import pytest
from pydantic import ValidationError
from pydantic_ai.models.test import TestModel

from vibe_check.judge.agent import build_judge_agent
from vibe_check.judge.prompting import build_judge_item_prompt, build_judge_system_prompt
from vibe_check.judge.schema import JudgeItemResolution


def test_build_judge_system_prompt_includes_version() -> None:
    prompt = build_judge_system_prompt("v1.2.3")
    assert "v1.2.3" in prompt


def test_build_judge_item_prompt_rejects_unknown_item() -> None:
    try:
        build_judge_item_prompt(
            scoring_text="Client: ...",
            item="not_an_item",
            juror_votes=[0, 1, 2],
            juror_evidence=["x"],
        )
    except ValueError as exc:
        assert "Unknown PHQ-8 item" in str(exc)
    else:
        raise AssertionError("Expected ValueError for unknown PHQ-8 item")


def test_judge_agent_end_to_end_with_testmodel() -> None:
    output = {
        "item": "sleep",
        "final_score": 2,
        "confidence": 0.8,
        "rationale": "Test rationale.",
    }
    model = TestModel(custom_output_args=output)

    agent = build_judge_agent(model=model, prompt_version="v1")
    prompt = build_judge_item_prompt(
        scoring_text="Client: I'm sleeping poorly.",
        item="sleep",
        juror_votes=[0, 0, 3, 3, 2, 2],
        juror_evidence=["Evidence 1", "Evidence 2"],
    )

    result = agent.run_sync(prompt)
    resolved = result.data if hasattr(result, "data") else result.output
    assert isinstance(resolved, JudgeItemResolution)
    assert resolved.item == "sleep"
    assert resolved.final_score == 2


def test_judge_item_resolution_rejects_invalid_item_name() -> None:
    with pytest.raises(ValidationError):
        JudgeItemResolution.model_validate(
            {
                "item": "anxiety",
                "final_score": 2,
                "confidence": 0.9,
                "rationale": "nope",
            }
        )
