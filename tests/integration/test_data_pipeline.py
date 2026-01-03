from __future__ import annotations

import pytest

from vibe_check.data import load_corpus, preprocess_dialogue, validate_corpus


@pytest.mark.integration
def test_full_pipeline_with_real_data() -> None:
    corpus = load_corpus("data/sqpsychconv/qwen-2.5")
    assert len(corpus) == 2090

    report = validate_corpus(corpus)
    assert report.duplicate_count == 0
    assert report.split_leakage == 0
    assert report.is_valid is True

    assert all(d.computed_split is not None for d in corpus)

    active436 = next(d for d in corpus if d.file_id == "active436")
    views = preprocess_dialogue(active436)
    assert views.client_only_text
    assert views.client_qa_text
    assert views.client_utterance_count > 0


@pytest.mark.integration
def test_condition_distribution() -> None:
    corpus = load_corpus("data/sqpsychconv/qwen-2.5")
    report = validate_corpus(corpus)

    assert report.mdd_count == 912
    assert report.control_count == 1178


@pytest.mark.integration
def test_artifact_detection_on_synthetic_data() -> None:
    """Test that artifact detection works with synthetic data.

    Note: qwen-2.5 is high-quality and may not have the artifacts that qwq had.
    This test uses a synthetic dialogue to verify the artifact detection pipeline
    integrates correctly with the preprocessing system.
    """
    from vibe_check.schemas.input import SQPsychConvDialogue

    # Synthetic dialogue with known artifacts (meta instructions, preamble)
    dialogue = SQPsychConvDialogue(
        file_id="synthetic_test",
        condition="mdd",
        client_model="test",
        therapist_model="test",
        dialogue=(
            "System: This is a test conversation.\n"  # Unknown speaker (preamble)
            "Therapist: Hello, how are you?\n"
            "Client: I'm feeling down.\n"
        ),
    )
    views = preprocess_dialogue(dialogue)
    # The preamble line with "System:" triggers has_unknown_speaker
    assert views.has_unknown_speaker is True
    # But the valid dialogue is still extracted
    assert views.client_utterance_count == 1
    assert "feeling down" in views.client_only_text
