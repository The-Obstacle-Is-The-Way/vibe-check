"""SQLite job ledger for batch runs (file_id/status/errors/tokens)."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Literal, cast

if TYPE_CHECKING:
    from pathlib import Path

    from vibe_check.schemas.scoring import TokenUsage

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
    input_tokens: int
    output_tokens: int
    reasoning_tokens: int
    total_tokens: int


class JobLedger:
    """A minimal SQLite-backed ledger for batch processing.

    Persists connection for performance (WAL mode) and handles token aggregation.
    """

    def __init__(self, path: Path) -> None:
        self._path = path
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: sqlite3.Connection | None = None

    def __enter__(self) -> JobLedger:
        self._conn = sqlite3.connect(self._path, timeout=30.0)
        # Enable WAL mode for better concurrency/durability
        self._conn.execute("PRAGMA journal_mode=WAL;")
        self._conn.execute("PRAGMA synchronous=NORMAL;")
        # Initialize schema if needed
        self._initialize_schema()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            raise RuntimeError("JobLedger must be used as a context manager")
        return self._conn

    def _initialize_schema(self) -> None:
        with self.conn:
            self.conn.execute(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    file_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    attempts INTEGER NOT NULL DEFAULT 0,
                    error_code TEXT NULL,
                    error_message TEXT NULL,
                    updated_at TEXT NOT NULL,
                    input_tokens INTEGER DEFAULT 0,
                    output_tokens INTEGER DEFAULT 0,
                    reasoning_tokens INTEGER DEFAULT 0,
                    total_tokens INTEGER DEFAULT 0
                )
                """
            )
            # Migration: Check for missing columns if table existed
            columns = {row[1] for row in self.conn.execute("PRAGMA table_info(jobs)").fetchall()}
            if "total_tokens" not in columns:
                self.conn.execute("ALTER TABLE jobs ADD COLUMN input_tokens INTEGER DEFAULT 0")
                self.conn.execute("ALTER TABLE jobs ADD COLUMN output_tokens INTEGER DEFAULT 0")
                self.conn.execute("ALTER TABLE jobs ADD COLUMN reasoning_tokens INTEGER DEFAULT 0")
                self.conn.execute("ALTER TABLE jobs ADD COLUMN total_tokens INTEGER DEFAULT 0")

    def initialize(self, file_ids: list[str]) -> None:
        """Seed the ledger with pending jobs if they don't exist."""
        now = _utc_now_iso()
        with self.conn:
            self.conn.executemany(
                """
                INSERT OR IGNORE INTO jobs (file_id, status, attempts, updated_at)
                VALUES (?, 'pending', 0, ?)
                """,
                [(fid, now) for fid in file_ids],
            )

    def reset_running_items(self) -> int:
        """Reset any 'running' items to 'pending' (crash recovery)."""
        with self.conn:
            cursor = self.conn.execute(
                """
                UPDATE jobs
                SET status = 'pending',
                    updated_at = ?
                WHERE status = 'running'
                """,
                (_utc_now_iso(),),
            )
            return cursor.rowcount

    def list_all(self) -> list[str]:
        rows = self.conn.execute("SELECT file_id FROM jobs ORDER BY file_id").fetchall()
        return [r[0] for r in rows]

    def list_pending(self) -> list[str]:
        rows = self.conn.execute(
            "SELECT file_id FROM jobs WHERE status = 'pending' ORDER BY file_id"
        ).fetchall()
        return [r[0] for r in rows]

    def get_status(self, file_id: str) -> Status:
        row = self.conn.execute(
            "SELECT status FROM jobs WHERE file_id = ?",
            (file_id,),
        ).fetchone()
        if row is None:
            raise KeyError(file_id)
        return cast("Status", row[0])

    def get_attempts(self, file_id: str) -> int:
        row = self.conn.execute(
            "SELECT attempts FROM jobs WHERE file_id = ?",
            (file_id,),
        ).fetchone()
        if row is None:
            raise KeyError(file_id)
        return int(row[0])

    def mark_running(self, file_id: str) -> None:
        with self.conn:
            status_row = self.conn.execute(
                "SELECT status FROM jobs WHERE file_id = ?",
                (file_id,),
            ).fetchone()
            if status_row is None:
                raise KeyError(file_id)
            if status_row[0] == "done":
                return

            self.conn.execute(
                """
                UPDATE jobs
                SET status = 'running',
                    attempts = attempts + 1,
                    updated_at = ?
                WHERE file_id = ?
                """,
                (_utc_now_iso(), file_id),
            )

    def mark_done(self, file_id: str, token_usage: TokenUsage | None = None) -> None:
        usage_values = (0, 0, 0, 0)
        if token_usage:
            usage_values = (
                token_usage.input_tokens or 0,
                token_usage.output_tokens or 0,
                token_usage.reasoning_tokens or 0,
                token_usage.total_tokens or 0,
            )

        with self.conn:
            self.conn.execute(
                """
                UPDATE jobs
                SET status = 'done',
                    error_code = NULL,
                    error_message = NULL,
                    updated_at = ?,
                    input_tokens = ?,
                    output_tokens = ?,
                    reasoning_tokens = ?,
                    total_tokens = ?
                WHERE file_id = ?
                """,
                (_utc_now_iso(), *usage_values, file_id),
            )

    def mark_failed(self, file_id: str, *, error_code: str, error_message: str) -> None:
        with self.conn:
            self.conn.execute(
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

    def get_aggregated_tokens(self) -> dict[str, int]:
        row = self.conn.execute(
            """
            SELECT
                SUM(input_tokens),
                SUM(output_tokens),
                SUM(reasoning_tokens),
                SUM(total_tokens)
            FROM jobs
            WHERE status = 'done'
            """
        ).fetchone()

        return {
            "input_tokens": row[0] or 0,
            "output_tokens": row[1] or 0,
            "reasoning_tokens": row[2] or 0,
            "total_tokens": row[3] or 0,
        }
