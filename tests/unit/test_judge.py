from __future__ import annotations

import pytest
from pydantic import ValidationError
from pydantic_ai.models.test import TestModel

from vibe_check.constants import PHQ8_RUBRIC, PHQ8_SCORE_SCALE, PHQ8_TIME_FRAME
from vibe_check.judge.agent import build_judge_agent, build_judge_agent_v2
from vibe_check.judge.prompting import (
    build_judge_item_prompt,
    build_judge_item_prompt_v2,
    build_judge_system_prompt,
)
from vibe_check.judge.schema import JudgeItemResolution, JudgeItemResolutionNA


def test_build_judge_system_prompt_includes_version() -> None:
    prompt = build_judge_system_prompt("v1.2.3")
    assert "v1.2.3" in prompt


def test_build_judge_system_prompt_embeds_phq8_rubric() -> None:
    prompt = build_judge_system_prompt("v1.2.3")
    assert PHQ8_TIME_FRAME in prompt
    for line in PHQ8_SCORE_SCALE.splitlines():
        assert line in prompt
    for definition in PHQ8_RUBRIC.values():
        assert definition in prompt


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


def test_build_judge_item_prompt_includes_item_definition_and_scale() -> None:
    prompt = build_judge_item_prompt(
        scoring_text="Client: I'm sleeping poorly.",
        item="sleep",
        juror_votes=[0, 0, 3, 3, 2, 2],
        juror_evidence=["Evidence 1", "Evidence 2"],
    )
    assert PHQ8_RUBRIC["sleep"] in prompt
    assert "Apply the scoring scale strictly" in prompt
    assert "0=Not at all" in prompt
    assert "3=Nearly every day" in prompt


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


def test_judge_agent_v2_end_to_end_allows_not_mentioned() -> None:
    output = {
        "item": "sleep",
        "discussed": False,
        "final_score": None,
        "assertion": "not_mentioned",
        "confidence": None,
        "evidence": [],
        "rationale": "Sleep not discussed.",
    }
    model = TestModel(custom_output_args=output)

    agent = build_judge_agent_v2(model=model, prompt_version="v2.0.0-clinical")
    prompt = build_judge_item_prompt_v2(
        scoring_text="Client: ...",
        item="sleep",
        juror_votes=[None, None, None],
        juror_assertions=["not_mentioned", "not_mentioned", "not_mentioned"],
        juror_evidence=[],
    )

    result = agent.run_sync(prompt)
    resolved = result.data if hasattr(result, "data") else result.output
    assert isinstance(resolved, JudgeItemResolutionNA)
    assert resolved.item == "sleep"
    assert resolved.assertion == "not_mentioned"
    assert resolved.final_score is None
