"""Run configuration models for batch execution (SPEC-06)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

    from vibe_check.graph.single_dialogue import DialogueViewName


@dataclass(frozen=True)
class RunConfig:
    input_path: Path
    output_dir: Path
    checkpoint_db: str
    prompt_version: str
    dialogue_view: DialogueViewName = "client_qa"
    limit: int | None = None
    max_concurrency: int = 1
