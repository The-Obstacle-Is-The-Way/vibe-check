from __future__ import annotations

from dataclasses import FrozenInstanceError
from typing import TYPE_CHECKING, Any, cast

import pytest

from vibe_check.run.config import RunConfig

if TYPE_CHECKING:
    from pathlib import Path


def test_run_config_defaults_and_frozen(tmp_path: Path) -> None:
    cfg = RunConfig(
        input_path=tmp_path / "input",
        output_dir=tmp_path / "out",
        checkpoint_db="sqlite:///tmp/checkpoints.db",
        prompt_version="v1.0.0",
    )
    assert cfg.dialogue_view == "client_qa"
    assert cfg.limit is None
    assert cfg.max_concurrency == 1

    with pytest.raises(FrozenInstanceError):
        cast("Any", cfg).prompt_version = "v2"
