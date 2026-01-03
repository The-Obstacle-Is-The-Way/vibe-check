"""Export schemas for downstream consumers (SPEC-08)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from vibe_check.constants import SeverityBucket  # noqa: TC001 - Required at runtime for Pydantic


class ScoredDialogueExport(BaseModel):
    """Single dialogue export record (Public Contract)."""

    model_config = ConfigDict(extra="forbid")

    dialogue_id: str = Field(min_length=1)
    condition: Literal["mdd", "control"]

    phq8_item_1: int = Field(ge=0, le=3)
    phq8_item_2: int = Field(ge=0, le=3)
    phq8_item_3: int = Field(ge=0, le=3)
    phq8_item_4: int = Field(ge=0, le=3)
    phq8_item_5: int = Field(ge=0, le=3)
    phq8_item_6: int = Field(ge=0, le=3)
    phq8_item_7: int = Field(ge=0, le=3)
    phq8_item_8: int = Field(ge=0, le=3)

    phq8_total: int = Field(ge=0, le=24)
    severity_bucket: SeverityBucket

    client_qa_text: str

    juror_votes: dict[str, list[int]]
    arbitration_triggered: dict[str, bool]

    run_id: str
    prompt_version: str

    @model_validator(mode="after")
    def _validate_total(self) -> ScoredDialogueExport:
        total = (
            self.phq8_item_1
            + self.phq8_item_2
            + self.phq8_item_3
            + self.phq8_item_4
            + self.phq8_item_5
            + self.phq8_item_6
            + self.phq8_item_7
            + self.phq8_item_8
        )
        if self.phq8_total != total:
            raise ValueError(f"phq8_total={self.phq8_total} does not match item sum={total}")
        return self
