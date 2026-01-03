from __future__ import annotations

from typing import TYPE_CHECKING

from vibe_check.run.ledger import JobLedger

if TYPE_CHECKING:
    from pathlib import Path


def test_ledger_status_transitions_are_idempotent(tmp_path: Path) -> None:
    db_path = tmp_path / "ledger.sqlite"
    with JobLedger(db_path) as ledger:
        ledger.initialize(["a", "b"])

        assert set(ledger.list_pending()) == {"a", "b"}

        ledger.mark_running("a")
        ledger.mark_done("a")
        ledger.mark_done("a")
        assert ledger.get_status("a") == "done"

        ledger.mark_running("b")
        ledger.mark_failed("b", error_code="boom", error_message="test error")
        assert ledger.get_status("b") == "failed"

        assert ledger.list_pending() == []


def test_ledger_attempts_increment_on_each_run(tmp_path: Path) -> None:
    db_path = tmp_path / "ledger.sqlite"
    with JobLedger(db_path) as ledger:
        ledger.initialize(["x"])

        assert ledger.get_attempts("x") == 0
        ledger.mark_running("x")
        assert ledger.get_attempts("x") == 1
        ledger.mark_failed("x", error_code="boom", error_message="x")
        ledger.mark_running("x")
        assert ledger.get_attempts("x") == 2
