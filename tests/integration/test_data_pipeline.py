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
def test_known_bad_preamble_is_flagged() -> None:
    corpus = load_corpus("data/sqpsychconv/qwen-2.5")
    active82 = next(d for d in corpus if d.file_id == "active82")
    views = preprocess_dialogue(active82)
    assert views.has_unknown_speaker is True
