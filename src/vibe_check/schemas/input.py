"""Input data models."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

SplitName = Literal["train", "dev", "test"]


class SQPsychConvDialogue(BaseModel):
    """A single dialogue from the SQPsychConv dataset."""

    model_config = ConfigDict(extra="forbid")

    file_id: str = Field(min_length=1, description="Unique identifier, e.g., 'active436'")
    condition: Literal["mdd", "control"] = Field(description="MDD or control group")
    client_model: str = Field(min_length=1, description="Model used for client, e.g., 'qwen25'")
    therapist_model: str = Field(min_length=1, description="Model used for therapist")
    dialogue: str = Field(description="Raw dialogue text with speaker labels")

    computed_split: SplitName | None = Field(
        default=None,
        description="Deterministic split based on file_id hash",
    )
