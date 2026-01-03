from __future__ import annotations

from typing import Literal, cast

import pytest
from pydantic import ValidationError

from vibe_check.schemas.input import SQPsychConvDialogue

Condition = Literal["mdd", "control"]


def test_dialogue_valid() -> None:
    d = SQPsychConvDialogue(
        file_id="test123",
        condition="mdd",
        client_model="qwen25",
        therapist_model="qwen25",
        dialogue="Therapist: Hello\nClient: Hi",
    )
    assert d.file_id == "test123"
    assert d.computed_split is None


def test_dialogue_invalid_condition() -> None:
    with pytest.raises(ValidationError):
        SQPsychConvDialogue(
            file_id="test123",
            condition=cast("Condition", "unknown"),
            client_model="qwen25",
            therapist_model="qwen25",
            dialogue="Therapist: Hello\nClient: Hi",
        )
