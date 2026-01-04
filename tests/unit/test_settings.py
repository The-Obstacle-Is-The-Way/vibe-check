from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from vibe_check.settings import Settings


def _env_example_keys(repo_root: Path) -> set[str]:
    env_path = repo_root / ".env.example"
    keys: set[str] = set()
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key = line.split("=", 1)[0].strip()
        if key:
            keys.add(key)
    return keys


def test_env_example_includes_arbitration_thresholds() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    keys = _env_example_keys(repo_root)
    assert "ARBITRATION_MAX_PROB_THRESHOLD" in keys
    assert "ARBITRATION_ENTROPY_THRESHOLD" in keys


def test_settings_google_api_key_accepts_gemini_api_key_alias(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")
    settings = Settings()
    assert settings.google_api_key == "test-gemini-key"


def test_settings_runs_per_model_rejects_values_above_two(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("RUNS_PER_MODEL", "3")
    with pytest.raises(ValidationError):
        Settings()
