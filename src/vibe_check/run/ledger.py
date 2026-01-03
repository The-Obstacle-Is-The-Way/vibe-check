"""SQLite job ledger for batch runs (file_id/status/errors only)."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Literal, cast

if TYPE_CHECKING:
    from pathlib import Path

Status = Literal["pending", "running", "done", "failed"]


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


@dataclass(frozen=True)
class LedgerRow:
    file_id: str
    status: Status
    attempts: int
    error_code: str | None
    error_message: str | None
    updated_at: str


class JobLedger:
    """A minimal SQLite-backed ledger for batch processing."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._path)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        return conn

    def initialize(self, file_ids: list[str]) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    file_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    attempts INTEGER NOT NULL DEFAULT 0,
                    error_code TEXT NULL,
                    error_message TEXT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            now = _utc_now_iso()
            for file_id in file_ids:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO jobs (file_id, status, attempts, updated_at)
                    VALUES (?, 'pending', 0, ?)
                    """,
                    (file_id, now),
                )

    def list_all(self) -> list[str]:
        with self._connect() as conn:
            rows = conn.execute("SELECT file_id FROM jobs ORDER BY file_id").fetchall()
        return [r[0] for r in rows]

    def list_pending(self) -> list[str]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT file_id FROM jobs WHERE status = 'pending' ORDER BY file_id"
            ).fetchall()
        return [r[0] for r in rows]

    def get_status(self, file_id: str) -> Status:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT status FROM jobs WHERE file_id = ?",
                (file_id,),
            ).fetchone()
        if row is None:
            raise KeyError(file_id)
        status = str(row[0])
        if status not in {"pending", "running", "done", "failed"}:
            raise ValueError(f"Unexpected status for {file_id}: {status!r}")
        return cast("Status", status)

    def get_attempts(self, file_id: str) -> int:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT attempts FROM jobs WHERE file_id = ?",
                (file_id,),
            ).fetchone()
        if row is None:
            raise KeyError(file_id)
        return int(row[0])

    def mark_running(self, file_id: str) -> None:
        with self._connect() as conn:
            status = conn.execute(
                "SELECT status FROM jobs WHERE file_id = ?",
                (file_id,),
            ).fetchone()
            if status is None:
                raise KeyError(file_id)
            if status[0] == "done":
                return
            conn.execute(
                """
                UPDATE jobs
                SET status = 'running',
                    attempts = attempts + 1,
                    updated_at = ?
                WHERE file_id = ?
                """,
                (_utc_now_iso(), file_id),
            )

    def mark_done(self, file_id: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE jobs
                SET status = 'done',
                    error_code = NULL,
                    error_message = NULL,
                    updated_at = ?
                WHERE file_id = ?
                """,
                (_utc_now_iso(), file_id),
            )

    def mark_failed(self, file_id: str, *, error_code: str, error_message: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE jobs
                SET status = 'failed',
                    error_code = ?,
                    error_message = ?,
                    updated_at = ?
                WHERE file_id = ?
                """,
                (error_code, error_message[:500], _utc_now_iso(), file_id),
            )
