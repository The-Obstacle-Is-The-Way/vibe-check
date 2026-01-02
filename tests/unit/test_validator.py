from __future__ import annotations

from vibe_check.data.validator import validate_corpus
from vibe_check.schemas.input import SQPsychConvDialogue


def test_validate_corpus_duplicates_by_file_id() -> None:
    dialogues = [
        SQPsychConvDialogue(
            file_id="x",
            condition="mdd",
            client_model="a",
            therapist_model="b",
            dialogue="Therapist: Hi\nClient: Hello",
        ),
        SQPsychConvDialogue(
            file_id="x",
            condition="mdd",
            client_model="a",
            therapist_model="b",
            dialogue="Therapist: Hi\nClient: Hello",
        ),
    ]
    report = validate_corpus(dialogues)
    assert report.duplicate_count == 1
    assert report.is_valid is False


def test_validate_corpus_duplicate_content_hashes() -> None:
    dialogues = [
        SQPsychConvDialogue(
            file_id="x",
            condition="mdd",
            client_model="a",
            therapist_model="b",
            dialogue="Therapist: Hi\nClient: Hello",
        ),
        SQPsychConvDialogue(
            file_id="y",
            condition="control",
            client_model="a",
            therapist_model="b",
            dialogue="Therapist: Hi\nClient: Hello",
        ),
    ]
    report = validate_corpus(dialogues)
    assert len(report.duplicate_content_hashes) == 1


def test_validate_corpus_unknown_speaker_detection() -> None:
    dialogues = [
        SQPsychConvDialogue(
            file_id="x",
            condition="mdd",
            client_model="a",
            therapist_model="b",
            dialogue="Preamble...\nTherapist: Hi\nClient: Hello",
        )
    ]
    report = validate_corpus(dialogues)
    assert report.unknown_speaker_count == 1
