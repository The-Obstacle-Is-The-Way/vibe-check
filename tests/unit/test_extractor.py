from __future__ import annotations

from vibe_check.constants import MAX_UTTERANCE_CHARS, MAX_UTTERANCE_WORDS
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
    assert views.orphan_line_count == 1
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
    assert views.has_unknown_speaker is False
    assert views.meta_text_removed_count == 1
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
    assert views.has_unknown_speaker is False
    assert views.meta_text_removed_count == 1
    assert views.client_only_text == "Hello?"


def test_long_utterance_is_truncated_not_dropped() -> None:
    too_many_words = "word " * (MAX_UTTERANCE_WORDS + 5)
    dialogue = SQPsychConvDialogue(
        file_id="test",
        condition="mdd",
        client_model="test",
        therapist_model="test",
        dialogue=f"Client: {too_many_words}",
    )
    views = preprocess_dialogue(dialogue)
    assert views.client_utterance_count == 1
    assert views.truncated_utterance_count == 1
    assert 0 < len(views.client_only_text.split()) <= MAX_UTTERANCE_WORDS


def test_long_utterance_char_cap_is_applied() -> None:
    too_many_chars = "x" * (MAX_UTTERANCE_CHARS + 10)
    dialogue = SQPsychConvDialogue(
        file_id="test",
        condition="mdd",
        client_model="test",
        therapist_model="test",
        dialogue=f"Client: {too_many_chars}",
    )
    views = preprocess_dialogue(dialogue)
    assert views.client_utterance_count == 1
    assert views.truncated_utterance_count == 1
    assert 0 < len(views.client_only_text) <= MAX_UTTERANCE_CHARS


def test_generation_artifacts_are_stripped() -> None:
    dialogue = SQPsychConvDialogue(
        file_id="test",
        condition="mdd",
        client_model="test",
        therapist_model="test",
        dialogue=(
            "Therapist: Hello, Mr. [Client's Name]. [Please confirm the date and time.]\n"
            "Client: Thanks. [/END]\n"
            "Client: [Keep silent]\n"
            "Client: [Sigh]\n"
            "Therapist: Let's meet [insert preferred date] [Next week].\n"
            "Client: Inhale.. hold.. exhale. [Repeats a few times]\n"
            "Therapist: Sounds good. [19/20]\n"
            "Client: Great. [1/8]\n"
            "Therapist: [Take care, and I'll see you then.]\n"
            "Client: Okay.\n"
        ),
    )
    views = preprocess_dialogue(dialogue)

    assert "[/END]" not in views.dialogue_clean
    assert "[Sigh]" not in views.dialogue_clean
    assert "[19/20]" not in views.dialogue_clean
    assert "[1/8]" not in views.dialogue_clean
    assert "insert preferred date" not in views.dialogue_clean.lower()
    assert "next week" not in views.dialogue_clean.lower()
    assert "client's name" not in views.dialogue_clean.lower()
    assert "keep silent" not in views.dialogue_clean.lower()
    assert "confirm the date and time" not in views.dialogue_clean.lower()
    assert "repeats a few times" not in views.dialogue_clean.lower()
    assert "take care" not in views.dialogue_clean.lower()

    # Verify whitespace is properly normalized after artifact removal
    assert "  " not in views.dialogue_clean  # No double spaces
    assert "Mr.." not in views.dialogue_clean  # No double-dot artifacts
