from __future__ import annotations

from vibe_check.preprocessing.extractor import parse_utterances, preprocess_dialogue
from vibe_check.schemas.input import SQPsychConvDialogue


def test_parse_utterances_basic() -> None:
    text = "Therapist: Hello\nClient: Hi there"
    result = parse_utterances(text)
    assert result == [("therapist", "Hello"), ("client", "Hi there")]


def test_parse_utterances_multiline() -> None:
    text = "Therapist: How are you?\nClient: I'm okay.\nNot great, but okay."
    result = parse_utterances(text)
    assert len(result) == 2
    assert "Not great" in result[1][1]


def test_client_qa_context() -> None:
    dialogue = SQPsychConvDialogue(
        file_id="test",
        condition="mdd",
        client_model="test",
        therapist_model="test",
        dialogue="Therapist: How is your sleep?\nClient: Terrible.",
    )
    views = preprocess_dialogue(dialogue)

    assert views.client_only_text == "Terrible."
    assert "sleep" in views.client_qa_text.lower()
    assert "Terrible" in views.client_qa_text


def test_client_qa_blocks_include_single_prompt() -> None:
    dialogue = SQPsychConvDialogue(
        file_id="test",
        condition="mdd",
        client_model="test",
        therapist_model="test",
        dialogue=(
            "Therapist: Q1?\nClient: A1.\nClient: A2.\nTherapist: Q2?\nClient: A3.\nClient: A4."
        ),
    )
    views = preprocess_dialogue(dialogue)
    assert views.client_qa_text.count("Therapist:") == 2


def test_semantic_void_detection() -> None:
    dialogue = SQPsychConvDialogue(
        file_id="test",
        condition="mdd",
        client_model="test",
        therapist_model="test",
        dialogue="Therapist: Rate 1-10?\nClient: 8.",
    )
    views = preprocess_dialogue(dialogue)
    assert views.short_answer_count >= 1


def test_unlabeled_preamble_is_dropped_and_flagged() -> None:
    dialogue = SQPsychConvDialogue(
        file_id="test",
        condition="mdd",
        client_model="test",
        therapist_model="test",
        dialogue="Preamble instructions...\nTherapist: Hi\nClient: Hello",
    )
    views = preprocess_dialogue(dialogue)
    assert views.has_unknown_speaker is True
    assert views.dialogue_clean.startswith("Therapist: Hi")


def test_speaker_labeled_meta_is_dropped_and_flagged() -> None:
    dialogue = SQPsychConvDialogue(
        file_id="test",
        condition="mdd",
        client_model="test",
        therapist_model="test",
        dialogue="Therapist: Hi\nTherapist:, no markdown.\nClient: Hello",
    )
    views = preprocess_dialogue(dialogue)
    assert views.has_unknown_speaker is True
    assert "no markdown" not in views.dialogue_clean.lower()
    assert views.client_only_text == "Hello"


def test_doublequote_meta_suffix_is_trimmed() -> None:
    dialogue = SQPsychConvDialogue(
        file_id="test",
        condition="mdd",
        client_model="test",
        therapist_model="test",
        dialogue='Client: Hello?"" This uses meta commentary and should be removed.',
    )
    views = preprocess_dialogue(dialogue)
    assert views.has_unknown_speaker is True
    assert views.client_only_text == "Hello?"
