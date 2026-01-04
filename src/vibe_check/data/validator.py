"""Corpus integrity checks."""

from __future__ import annotations

import hashlib
from collections import Counter, defaultdict
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field

from vibe_check.data.splitter import compute_split
from vibe_check.preprocessing.extractor import parse_utterances_with_diagnostics

if TYPE_CHECKING:
    from collections.abc import Iterable

    from vibe_check.schemas.input import SQPsychConvDialogue


class CorpusIntegrityReport(BaseModel):
    """Results of corpus validation checks."""

    model_config = ConfigDict(extra="forbid")

    total_dialogues: int
    unique_file_ids: int
    duplicate_count: int = Field(ge=0, description="Should be 0")

    train_count: int
    dev_count: int
    test_count: int
    split_leakage: int = Field(ge=0, description="Overlapping file_ids across splits, should be 0")

    mdd_count: int
    control_count: int

    empty_dialogue_count: int = Field(ge=0)
    unknown_speaker_count: int = Field(ge=0)

    duplicate_content_hashes: list[str] = Field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return self.duplicate_count == 0 and self.split_leakage == 0


def _content_hashes(dialogues: Iterable[SQPsychConvDialogue]) -> dict[str, set[str]]:
    by_hash: dict[str, set[str]] = defaultdict(set)
    for d in dialogues:
        utterances, _had_unknown, _truncated = parse_utterances_with_diagnostics(d.dialogue)
        clean = "\n".join(
            f"{speaker.title()}: {text}" for speaker, text in utterances if text.strip()
        ).strip()
        digest = hashlib.sha256(clean.encode("utf-8")).hexdigest()
        by_hash[digest].add(d.file_id)
    return by_hash


def validate_corpus(dialogues: list[SQPsychConvDialogue]) -> CorpusIntegrityReport:
    """Run all corpus integrity checks."""
    total = len(dialogues)
    file_ids = [d.file_id for d in dialogues]
    unique_file_ids = len(set(file_ids))
    duplicate_count = total - unique_file_ids

    file_to_splits: dict[str, set[str]] = defaultdict(set)
    split_counts: Counter[str] = Counter()
    condition_counts: Counter[str] = Counter()
    empty_dialogue_count = 0
    unknown_speaker_count = 0

    for d in dialogues:
        if not d.dialogue.strip():
            empty_dialogue_count += 1

        split = d.computed_split or compute_split(d.file_id)
        file_to_splits[d.file_id].add(split)
        split_counts[split] += 1
        condition_counts[d.condition] += 1

        _utterances, had_unknown, _truncated = parse_utterances_with_diagnostics(d.dialogue)
        if had_unknown:
            unknown_speaker_count += 1

    split_leakage = sum(1 for splits in file_to_splits.values() if len(splits) > 1)

    by_hash = _content_hashes(dialogues)
    duplicate_content_hashes = sorted([h for h, ids in by_hash.items() if len(ids) > 1])

    return CorpusIntegrityReport(
        total_dialogues=total,
        unique_file_ids=unique_file_ids,
        duplicate_count=duplicate_count,
        train_count=split_counts["train"],
        dev_count=split_counts["dev"],
        test_count=split_counts["test"],
        split_leakage=split_leakage,
        mdd_count=condition_counts["mdd"],
        control_count=condition_counts["control"],
        empty_dialogue_count=empty_dialogue_count,
        unknown_speaker_count=unknown_speaker_count,
        duplicate_content_hashes=duplicate_content_hashes,
    )
