"""Preprocessed dialogue-view models."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class DialogueViews(BaseModel):
    """Multiple text views extracted from a single dialogue."""

    model_config = ConfigDict(extra="forbid")

    file_id: str = Field(min_length=1)

    dialogue_clean: str = Field(
        description="Normalized speaker labels + whitespace, no semantic rewriting",
    )
    client_only_text: str = Field(
        description="Client utterances only (WARNING: semantic void risk)",
    )
    client_qa_text: str = Field(
        description="Client utterances + preceding therapist question for context",
    )

    client_utterance_count: int = Field(ge=0)
    therapist_utterance_count: int = Field(ge=0)
    short_answer_count: int = Field(
        ge=0,
        description="Count of very short client responses (<5 words)",
    )

    has_empty_client_text: bool = False
    has_unknown_speaker: bool = False
