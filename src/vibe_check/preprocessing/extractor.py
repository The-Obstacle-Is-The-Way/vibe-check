"""Deterministic dialogue-view extraction."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Literal

from vibe_check.schemas.views import DialogueViews

if TYPE_CHECKING:
    from vibe_check.schemas.input import SQPsychConvDialogue

_SPEAKER_RE = re.compile(r"^(?P<speaker>Therapist|Client)\s*:\s*(?P<text>.*)$", re.IGNORECASE)
_OTHER_PREFIX_RE = re.compile(r"^\s*[^:]{1,32}\s*:\s+")

Speaker = Literal["therapist", "client"]


def parse_utterances(dialogue_text: str) -> list[tuple[Speaker, str]]:
    """Parse dialogue into (speaker, text) tuples."""
    utterances, _had_unknown = parse_utterances_with_diagnostics(dialogue_text)
    return utterances


def parse_utterances_with_diagnostics(dialogue_text: str) -> tuple[list[tuple[Speaker, str]], bool]:
    utterances: list[tuple[Speaker, str]] = []
    current_speaker: Speaker | None = None
    current_lines: list[str] = []
    had_unknown = False

    def flush() -> None:
        nonlocal current_speaker, current_lines
        if current_speaker is None:
            current_lines = []
            return
        text = "\n".join(current_lines).strip()
        if text:
            utterances.append((current_speaker, text))
        current_speaker = None
        current_lines = []

    for raw_line in dialogue_text.splitlines():
        if not raw_line.strip():
            continue

        candidate = raw_line.lstrip()
        match = _SPEAKER_RE.match(candidate)
        if match:
            flush()
            speaker_raw = match.group("speaker").lower()
            current_speaker = "therapist" if speaker_raw.startswith("ther") else "client"
            text = match.group("text").strip()
            current_lines = [text] if text else []
            continue

        if _OTHER_PREFIX_RE.match(candidate):
            had_unknown = True
            if current_speaker is None:
                continue
            continue

        if current_speaker is None:
            had_unknown = True
            continue

        current_lines.append(raw_line.strip())

    flush()
    return utterances, had_unknown


def _word_count(text: str) -> int:
    return len(text.split())


def preprocess_dialogue(dialogue: SQPsychConvDialogue) -> DialogueViews:
    """Extract all deterministic text views from a dialogue."""
    utterances, had_unknown = parse_utterances_with_diagnostics(dialogue.dialogue)

    dialogue_clean_lines = [f"{speaker.title()}: {text}" for speaker, text in utterances]
    dialogue_clean = "\n".join(dialogue_clean_lines).strip()

    client_texts = [text for speaker, text in utterances if speaker == "client"]
    therapist_texts = [text for speaker, text in utterances if speaker == "therapist"]

    client_only_text = "\n".join(client_texts).strip()

    client_qa_lines: list[str] = []
    last_therapist: str | None = None
    in_client_block = False
    for speaker, text in utterances:
        if speaker == "therapist":
            last_therapist = text
            in_client_block = False
            continue

        if not in_client_block and last_therapist is not None:
            client_qa_lines.append(f"Therapist: {last_therapist}")
            in_client_block = True
        client_qa_lines.append(f"Client: {text}")

    client_qa_text = "\n".join(client_qa_lines).strip()

    short_answer_count = sum(1 for t in client_texts if _word_count(t) < 5)

    return DialogueViews(
        file_id=dialogue.file_id,
        dialogue_clean=dialogue_clean,
        client_only_text=client_only_text,
        client_qa_text=client_qa_text,
        client_utterance_count=len(client_texts),
        therapist_utterance_count=len(therapist_texts),
        short_answer_count=short_answer_count,
        has_empty_client_text=(len(client_texts) == 0 or not client_only_text),
        has_unknown_speaker=had_unknown,
    )
