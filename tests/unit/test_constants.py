from __future__ import annotations

import re

from vibe_check.constants import phq8_rubric_hash


def test_phq8_rubric_hash_is_deterministic_and_hex() -> None:
    h1 = phq8_rubric_hash()
    h2 = phq8_rubric_hash()
    assert h1 == h2
    assert re.fullmatch(r"[0-9a-f]{64}", h1) is not None
