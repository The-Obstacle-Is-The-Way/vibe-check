from __future__ import annotations

import json
from pathlib import Path

from pydantic_ai import Agent
from pydantic_ai.models.test import TestModel

from vibe_check.schemas.scoring import PHQ8Assessment, PHQ8Report
from vibe_check.scoring.juror import JurorScorer
from vibe_check.scoring.prompting import build_juror_system_prompt


def test_juror_scorer_end_to_end_with_testmodel() -> None:
    fixture_path = Path("tests/fixtures/juror_outputs/juror_ok.json")
    raw = json.loads(fixture_path.read_text(encoding="utf-8"))

    # Calculate expected total score
    total = 0
    items = [
        "anhedonia",
        "depressed_mood",
        "sleep",
        "fatigue",
        "appetite",
        "guilt",
        "concentration",
        "psychomotor",
    ]
    for item in items:
        total += raw[item]["score"]
    raw["total_score"] = total

    # Use custom_output_args for structured output simulation
    model = TestModel(custom_output_args=raw)

    agent = Agent(
        model=model, output_type=PHQ8Assessment, system_prompt=build_juror_system_prompt("v1")
    )
    scorer = JurorScorer(agent=agent, model_id="fake-model", run_number=1, prompt_version="v1")

    report = scorer.score("Client: I'm tired.\nTherapist: Tell me more.")
    assert isinstance(report, PHQ8Report)
    assert report.model_id == "fake-model"
    assert report.run_number == 1
    assert report.total_score == total
    assert report.usage is not None
