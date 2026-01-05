"""Deterministic dialogue-view extraction."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from vibe_check.constants import (
    MAX_BRACKET_CHARS,
    MAX_SPEAKER_PREFIX_CHARS,
    MAX_UTTERANCE_CHARS,
    MAX_UTTERANCE_WORDS,
    STRIP_GENERATION_ARTIFACT_PATTERNS,
)
from vibe_check.schemas.views import DialogueViews

if TYPE_CHECKING:
    from vibe_check.schemas.input import SQPsychConvDialogue

_SPEAKER_RE = re.compile(r"^(?P<speaker>Therapist|Client)\s*:\s*(?P<text>.*)$", re.IGNORECASE)
_OTHER_PREFIX_RE = re.compile(rf"^\s*[^:]{{1,{MAX_SPEAKER_PREFIX_CHARS}}}\s*:\s+")
_META_DOUBLEQUOTE_SUFFIX_RE = re.compile(
    r'""\s+(?=(this|that|check|finalizing|putting|example|alright|ok|okay|need)\b)',
    re.IGNORECASE,
)
_BRACKETED_RE = re.compile(r"\[(?P<inner>[^\[\]]+)\]")
_WORD_RE = re.compile(r"\S+")
_GENERATION_ARTIFACT_RE = re.compile("|".join(STRIP_GENERATION_ARTIFACT_PATTERNS), re.IGNORECASE)

Speaker = Literal["therapist", "client"]


@dataclass(frozen=True)
class PreprocessingDiagnostics:
    meta_text_removed_count: int = 0
    truncated_utterance_count: int = 0
    unknown_speaker_count: int = 0
    orphan_line_count: int = 0

    @property
    def has_unknown_speaker(self) -> bool:
        return (self.unknown_speaker_count + self.orphan_line_count) > 0


def parse_utterances(dialogue_text: str) -> list[tuple[Speaker, str]]:
    """Parse dialogue into (speaker, text) tuples."""
    utterances, _diagnostics = parse_utterances_with_diagnostics(dialogue_text)
    return utterances


def parse_utterances_with_diagnostics(
    dialogue_text: str,
) -> tuple[list[tuple[Speaker, str]], PreprocessingDiagnostics]:
    utterances: list[tuple[Speaker, str]] = []
    current_speaker: Speaker | None = None
    current_lines: list[str] = []
    meta_text_removed_count = 0
    truncated_utterance_count = 0
    unknown_speaker_count = 0
    orphan_line_count = 0

    def _strip_bracketed_meta(text: str) -> tuple[str, bool]:
        """Remove long bracketed meta instructions while preserving short stage directions."""

        def replace(match: re.Match[str]) -> str:
            inner = match.group("inner")
            lowered = inner.lower()
            if len(inner) >= MAX_BRACKET_CHARS:
                return ""
            if any(
                token in lowered
                for token in ("guideline", "instructions", "the user", "format", "word limit")
            ):
                return ""
            return match.group(0)

        cleaned = _BRACKETED_RE.sub(replace, text)
        return cleaned, cleaned != text

    def _truncate_doublequote_suffix(text: str) -> tuple[str, bool]:
        match = _META_DOUBLEQUOTE_SUFFIX_RE.search(text)
        if match is None:
            return text, False
        return text[: match.start()].rstrip(), True

    def _looks_like_meta(text: str) -> bool:
        lowered = text.strip().lower()
        if lowered.startswith(","):
            return True
        if "no markdown" in lowered:
            return True
        if "under 64 words" in lowered or "word limit" in lowered:
            return True
        if "check the guidelines" in lowered or "checks guidelines" in lowered:
            return True
        if "avoid repetition" in lowered:
            return True
        if "draft a response" in lowered:
            return True
        return "conversation history" in lowered or "the user" in lowered

    def _truncate_to_max_words(text: str, max_words: int) -> tuple[str, bool]:
        if max_words < 1:
            return "", True
        matches = list(_WORD_RE.finditer(text))
        if len(matches) <= max_words:
            return text, False
        end = matches[max_words - 1].end()
        return text[:end].rstrip(), True

    def _truncate_to_max_chars(text: str, max_chars: int) -> tuple[str, bool]:
        if max_chars < 1:
            return "", True
        if len(text) <= max_chars:
            return text, False
        return text[:max_chars].rstrip(), True

    def _strip_generation_artifacts(text: str) -> tuple[str, bool]:
        cleaned = _GENERATION_ARTIFACT_RE.sub("", text)
        if cleaned == text:
            return text, False
        # Avoid accumulating whitespace at removal boundaries.
        cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
        cleaned = re.sub(r"[ \t]+\n", "\n", cleaned)
        cleaned = re.sub(r"\n[ \t]+", "\n", cleaned)
        cleaned = re.sub(r"\s+([,.;:!?])", r"\1", cleaned)
        cleaned = re.sub(r"\.\.(?=\s|$)", ".", cleaned)
        cleaned = cleaned.strip()
        return cleaned, True

    def _sanitize_utterance_text(text: str) -> tuple[str, bool, bool]:
        """Strip obvious generation artifacts from speaker-labeled utterances."""
        cleaned, artifacts_removed = _strip_generation_artifacts(text.strip())
        cleaned, bracket_removed = _strip_bracketed_meta(cleaned)
        cleaned, suffix_trimmed = _truncate_doublequote_suffix(cleaned)
        meta_removed = artifacts_removed or bracket_removed or suffix_trimmed
        cleaned = cleaned.strip()
        if not cleaned:
            return "", meta_removed, False

        if _looks_like_meta(cleaned):
            return "", True, False

        word_truncated = False
        char_truncated = False
        if len(cleaned) > MAX_UTTERANCE_CHARS or _word_count(cleaned) > MAX_UTTERANCE_WORDS:
            cleaned, word_truncated = _truncate_to_max_words(cleaned, MAX_UTTERANCE_WORDS)
            cleaned, char_truncated = _truncate_to_max_chars(cleaned, MAX_UTTERANCE_CHARS)

        return cleaned, meta_removed, word_truncated or char_truncated

    def flush() -> None:
        nonlocal current_speaker, current_lines
        nonlocal meta_text_removed_count, truncated_utterance_count
        if current_speaker is None:
            current_lines = []
            return
        text = "\n".join(current_lines).strip()
        if text:
            cleaned, meta_removed, was_truncated = _sanitize_utterance_text(text)
            if meta_removed:
                meta_text_removed_count += 1
            if was_truncated:
                truncated_utterance_count += 1
            if cleaned:
                utterances.append((current_speaker, cleaned))
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
            unknown_speaker_count += 1
            if current_speaker is None:
                continue
            continue

        if current_speaker is None:
            orphan_line_count += 1
            continue

        current_lines.append(raw_line.strip())

    flush()
    return utterances, PreprocessingDiagnostics(
        meta_text_removed_count=meta_text_removed_count,
        truncated_utterance_count=truncated_utterance_count,
        unknown_speaker_count=unknown_speaker_count,
        orphan_line_count=orphan_line_count,
    )


def _word_count(text: str) -> int:
    return len(text.split())


def preprocess_dialogue(dialogue: SQPsychConvDialogue) -> DialogueViews:
    """Extract all deterministic text views from a dialogue."""
    utterances, diagnostics = parse_utterances_with_diagnostics(dialogue.dialogue)

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
        truncated_utterance_count=diagnostics.truncated_utterance_count,
        meta_text_removed_count=diagnostics.meta_text_removed_count,
        unknown_speaker_count=diagnostics.unknown_speaker_count,
        orphan_line_count=diagnostics.orphan_line_count,
        has_empty_client_text=(len(client_texts) == 0 or not client_only_text),
        has_unknown_speaker=diagnostics.has_unknown_speaker,
    )
